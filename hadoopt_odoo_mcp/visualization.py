"""
Visualization tools for Odoo MCP server.

Provides visualization and reporting capabilities for Odoo data.
"""
import json
from typing import Dict, List, Any, Optional, Union
from mcp.server.fastmcp import Context, FastMCP


class DataVisualization:
    """
    Class to handle data visualization for Odoo models
    """
    def __init__(self, odoo_client):
        """
        Initialize DataVisualization with an Odoo client

        Args:
            odoo_client: Odoo client for data retrieval
        """
        self._odoo_client = odoo_client

    def generate_visualization(
        self, 
        model: str, 
        visualization_type: str = 'bar', 
        fields: Optional[Union[List[str], str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a visualization for a given Odoo model.
        
        Args:
            model: Odoo model to visualize
            visualization_type: Type of visualization (bar, pie, line)
            fields: Fields to include in visualization
        
        Returns:
            Visualization data or error information
        """
        try:
            # Handle fields as string or list
            parsed_fields = None
            if fields:
                if isinstance(fields, str):
                    parsed_fields = fields.split(',')
                else:
                    parsed_fields = fields
            
            # Default fields if not provided
            if not parsed_fields:
                # Get model fields and select appropriate ones for visualization
                model_fields = self._odoo_client.get_model_fields(model)
                
                # Try to find name field and a numeric field
                name_field = next((f for f in model_fields if f in ['name', 'display_name']), None)
                numeric_fields = [f for f in model_fields if model_fields[f].get('type') in ['integer', 'float', 'monetary']]
                
                if name_field and numeric_fields:
                    parsed_fields = [name_field, numeric_fields[0]]
                elif name_field:
                    parsed_fields = [name_field]
                else:
                    # Just use the first field and 'id'
                    parsed_fields = ['id', list(model_fields.keys())[0] if model_fields else 'id']
            
            # Retrieve records
            records = self._odoo_client.search_read(model, [], fields=parsed_fields, limit=100)
            
            # Process data for visualization
            processed_data = self._process_visualization_data(
                records, visualization_type, parsed_fields
            )
            
            return {
                'success': True,
                'visualization_type': visualization_type,
                'model': model,
                'fields': parsed_fields,
                'data': processed_data,
                'raw_data': records[:10]  # Include a sample of raw data
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'model': model,
                'visualization_type': visualization_type
            }
    
    def _process_visualization_data(
        self, 
        records: List[Dict], 
        visualization_type: str, 
        fields: List[str]
    ) -> Dict[str, Any]:
        """
        Process raw Odoo data into visualization-friendly format
        
        Args:
            records: Raw records from Odoo
            visualization_type: Type of visualization
            fields: Fields used in the visualization
            
        Returns:
            Processed data for visualization
        """
        if not records or not fields:
            return {'labels': [], 'datasets': []}
        
        if visualization_type in ['bar', 'line', 'pie']:
            # For these chart types, we need labels and values
            label_field = fields[0]
            value_field = fields[1] if len(fields) > 1 else 'id'
            
            labels = [str(r.get(label_field, '')) for r in records]
            values = [float(r.get(value_field, 0)) if r.get(value_field) is not None else 0 for r in records]
            
            return {
                'labels': labels,
                'datasets': [
                    {
                        'label': value_field,
                        'data': values
                    }
                ]
            }
        elif visualization_type == 'scatter':
            # For scatter plots, we need x and y values
            x_field = fields[0]
            y_field = fields[1] if len(fields) > 1 else 'id'
            
            points = [
                {
                    'x': float(r.get(x_field, 0)) if r.get(x_field) is not None else 0,
                    'y': float(r.get(y_field, 0)) if r.get(y_field) is not None else 0
                }
                for r in records
            ]
            
            return {
                'datasets': [
                    {
                        'label': f'{x_field} vs {y_field}',
                        'data': points
                    }
                ]
            }
        else:
            # Default format
            return {'data': records}

    def analyze_distribution(
        self, 
        model: str, 
        field: str, 
        distribution_type: str = 'frequency'
    ) -> Dict[str, Any]:
        """
        Analyze distribution of a specific field in an Odoo model.
        
        Args:
            model: Odoo model to analyze
            field: Field to analyze distribution
            distribution_type: Type of distribution analysis
        
        Returns:
            Distribution analysis results
        """
        try:
            # Get field information to determine its type
            field_info = self._odoo_client.get_model_fields(model, [field])
            if not field_info or field not in field_info:
                return {
                    'success': False,
                    'error': f"Field '{field}' not found in model '{model}'"
                }
            
            field_type = field_info[field].get('type')
            
            # Retrieve field values
            records = self._odoo_client.search_read(model, [], fields=[field])
            
            if distribution_type == 'frequency':
                distribution = self._calculate_frequency_distribution(records, field, field_type)
            elif distribution_type == 'histogram' and field_type in ['integer', 'float', 'monetary']:
                distribution = self._calculate_numeric_histogram(records, field)
            else:
                distribution = self._calculate_frequency_distribution(records, field, field_type)
            
            return {
                'success': True,
                'model': model,
                'field': field,
                'field_type': field_type,
                'distribution_type': distribution_type,
                'total_records': len(records),
                'distribution': distribution
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'model': model,
                'field': field
            }
    
    def _calculate_frequency_distribution(
        self, 
        records: List[Dict], 
        field: str,
        field_type: str
    ) -> Dict:
        """
        Calculate frequency distribution for categorical data
        
        Args:
            records: List of records
            field: Field to analyze
            field_type: Odoo field type
            
        Returns:
            Frequency distribution data
        """
        distribution = {}
        null_count = 0
        
        for record in records:
            value = record.get(field)
            
            # Handle different field types
            if value is None or value == False:
                null_count += 1
                continue
                
            # For many2one relations, use the name
            if field_type == 'many2one' and isinstance(value, tuple) and len(value) == 2:
                value = value[1]  # Use display name
            
            # Convert value to string for dict key
            str_value = str(value)
            distribution[str_value] = distribution.get(str_value, 0) + 1
        
        # Add null/empty count if any
        if null_count > 0:
            distribution['None/Empty'] = null_count
            
        # Sort by frequency (descending)
        sorted_dist = {k: v for k, v in sorted(
            distribution.items(), 
            key=lambda item: item[1], 
            reverse=True
        )}
        
        return sorted_dist
    
    def _calculate_numeric_histogram(
        self, 
        records: List[Dict], 
        field: str
    ) -> Dict:
        """
        Calculate histogram bins for numeric data
        
        Args:
            records: List of records
            field: Field to analyze
            
        Returns:
            Histogram data with bins
        """
        # Extract numeric values
        values = []
        for record in records:
            value = record.get(field)
            if value is not None and value is not False:
                try:
                    values.append(float(value))
                except (ValueError, TypeError):
                    pass
        
        if not values:
            return {}
            
        # Calculate min, max, and determine bins
        min_value = min(values)
        max_value = max(values)
        
        # Determine number of bins based on data size
        num_bins = min(10, len(set(values)))
        if max_value == min_value:
            # All values are the same
            return {str(min_value): len(values)}
            
        bin_width = (max_value - min_value) / num_bins
        
        # Initialize bins
        bins = {f"{min_value + i*bin_width:.2f} - {min_value + (i+1)*bin_width:.2f}": 0 
                for i in range(num_bins)}
        
        # Count values in each bin
        for value in values:
            # Handle edge case for max value
            if value == max_value:
                bin_index = num_bins - 1
            else:
                bin_index = min(int((value - min_value) / bin_width), num_bins - 1)
                
            bin_key = f"{min_value + bin_index*bin_width:.2f} - {min_value + (bin_index+1)*bin_width:.2f}"
            bins[bin_key] += 1
            
        return bins


def register_visualization_tools(mcp: FastMCP, app_context):
    """
    Register visualization-related tools to the MCP server.
    
    Args:
        mcp: The FastMCP server instance to register tools with
        app_context: Application context containing instance manager
    """
    instance_manager = app_context.instance_manager
    
    @mcp.tool(description="Generate visualization for Odoo data")
    def generate_data_visualization(
        ctx: Context,
        model: str,
        visualization_type: str = 'bar',
        fields: Optional[str] = None,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a visualization for a given Odoo model.
        
        Args:
            ctx: Context provided by MCP server
            model: Odoo model to visualize
            visualization_type: Type of visualization (bar, pie, line, scatter)
            fields: Comma-separated list of fields to include
            instance_name: Optional name of the instance to use (default: active instance)
            
        Returns:
            Visualization data or error information
        """
        instance_name = instance_name or instance_manager.active_instance
        odoo_client = instance_manager.get_client(instance_name)
        
        if not odoo_client:
            return {
                'success': False,
                'error': f"Instance '{instance_name}' not found.",
                'available_instances': instance_manager.get_available_instances()
            }
        
        try:
            visualizer = DataVisualization(odoo_client)
            result = visualizer.generate_visualization(
                model, 
                visualization_type, 
                fields
            )
            
            # Add instance information to result
            result['instance'] = instance_name
            
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'instance': instance_name
            }

    @mcp.tool(description="Analyze data distribution")
    def analyze_data_distribution(
        ctx: Context,
        model: str,
        field: str,
        distribution_type: str = 'frequency',
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze distribution of a specific field in an Odoo model.
        
        Args:
            ctx: Context provided by MCP server
            model: Odoo model to analyze
            field: Field to analyze distribution
            distribution_type: Type of distribution analysis (frequency, histogram)
            instance_name: Optional name of the instance to use (default: active instance)
            
        Returns:
            Distribution analysis results
        """
        instance_name = instance_name or instance_manager.active_instance
        odoo_client = instance_manager.get_client(instance_name)
        
        if not odoo_client:
            return {
                'success': False,
                'error': f"Instance '{instance_name}' not found.",
                'available_instances': instance_manager.get_available_instances()
            }
        
        try:
            visualizer = DataVisualization(odoo_client)
            result = visualizer.analyze_distribution(
                model, 
                field, 
                distribution_type
            )
            
            # Add instance information to result
            result['instance'] = instance_name
            
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'instance': instance_name
            }
