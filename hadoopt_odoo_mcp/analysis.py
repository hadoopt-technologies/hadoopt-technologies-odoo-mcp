"""
Generic analysis tools for Odoo data
"""

import math
import statistics
import traceback
from typing import Any, Dict, List, Optional, Union, Tuple

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Response model for the analyze_model_data tool."""
    
    success: bool = Field(description="Indicates if the analysis was successful")
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Analysis results"
    )
    error: Optional[str] = Field(default=None, description="Error message, if any")
    traceback: Optional[str] = Field(default=None, description="Error traceback, if any")


def _get_numeric_values(records: List[Dict], field: str) -> List[float]:
    """Extract valid numeric values from records for a given field"""
    values = []
    for record in records:
        if field in record and record[field] is not None:
            try:
                # Handle both numeric types and strings that can be converted
                value = float(record[field])
                values.append(value)
            except (ValueError, TypeError):
                # Skip non-numeric values
                pass
    return values


def _calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """Calculate percentiles for a list of numeric values"""
    if not values:
        return {}
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    return {
        "25th": sorted_values[int(n * 0.25)] if n > 4 else None,
        "50th": sorted_values[int(n * 0.5)] if n > 2 else None,
        "75th": sorted_values[int(n * 0.75)] if n > 4 else None,
        "90th": sorted_values[int(n * 0.9)] if n > 10 else None
    }


def _format_float(value: float) -> Union[float, str]:
    """Format float values for better readability"""
    if value is None:
        return None
    
    # Keep integers as integers
    if value == int(value):
        return int(value)
    
    # Format with limited decimal places based on magnitude
    if abs(value) < 0.01:
        return f"{value:.6f}"
    elif abs(value) < 1:
        return f"{value:.4f}"
    else:
        return round(value, 2)


def register_analysis_tools(mcp):
    """Register analysis tools with the MCP server"""
    
    @mcp.tool(description="Analyze data from any Odoo model")
    def analyze_model_data(
        ctx: Context,
        model: str,
        domain: List = None,
        fields: List[str] = None,
        group_by: List[str] = None,
        measures: List[str] = None,
        time_range: Dict = None,
        analysis_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Generic analysis tool for any Odoo model
        
        Parameters:
            model: The model name (e.g., 'product.product', 'sale.order')
            domain: Search domain to filter records
            fields: Fields to retrieve for analysis
            group_by: Fields to group by
            measures: Numeric fields to calculate statistics on
            time_range: Dict with 'field', 'start' and 'end' for time-based analysis
            analysis_type: Type of analysis ('summary', 'trend', 'distribution')
        """
        odoo = ctx.request_context.lifespan_context.odoo
        utils = ctx.request_context.lifespan_context.utils
        
        try:
            domain = domain or []
            
            # If measures not specified, try to discover appropriate numeric fields
            if not measures:
                # Get field information
                model_fields = odoo.get_model_fields(model)
                measures = []
                for field_name, field_info in model_fields.items():
                    if field_info.get("type") in ["integer", "float", "monetary"]:
                        measures.append(field_name)
                
                # Limit to 5 most relevant measures to avoid performance issues
                if len(measures) > 5:
                    # Prioritize common value fields
                    priority_fields = ["amount", "price", "cost", "value", "total", "quantity", "qty"]
                    
                    # Move priority fields to the front
                    for pattern in priority_fields:
                        for field in list(measures):  # Create a copy to avoid modification during iteration
                            if pattern in field.lower() and field in measures:
                                measures.remove(field)
                                measures.insert(0, field)
                    
                    # Trim to 5 fields
                    measures = measures[:5]
            
            # Apply time range if specified
            if time_range and 'field' in time_range and 'start' in time_range and 'end' in time_range:
                domain.append((time_range['field'], '>=', time_range['start']))
                domain.append((time_range['field'], '<=', time_range['end']))
            
            # Determine fields to fetch
            fetch_fields = set()
            if fields:
                fetch_fields.update(fields)
            if group_by:
                fetch_fields.update(group_by)
            if measures:
                fetch_fields.update(measures)
            if time_range and 'field' in time_range:
                fetch_fields.add(time_range['field'])
            
            # Get the data using the updated search_read method
            records = odoo.search_read(model, domain, fields=list(fetch_fields) if fetch_fields else None)
            
            if not records:
                return {"success": True, "result": {"message": "No records found", "count": 0}}
            
            # Basic stats for all records
            result = {"count": len(records)}
            
            # Handling different analysis types
            if analysis_type == "summary":
                # Summary statistics for numeric fields
                if measures:
                    stats = {}
                    for measure in measures:
                        values = _get_numeric_values(records, measure)
                        
                        if values:
                            # Basic statistics
                            calc_stats = {
                                "min": _format_float(min(values)),
                                "max": _format_float(max(values)),
                                "avg": _format_float(sum(values) / len(values)),
                                "sum": _format_float(sum(values)),
                                "count": len(values)
                            }
                            
                            # Add advanced statistics if we have enough values
                            if len(values) > 1:
                                # Add median
                                calc_stats["median"] = _format_float(statistics.median(values))
                                
                                # Add standard deviation
                                try:
                                    calc_stats["std_dev"] = _format_float(statistics.stdev(values))
                                except statistics.StatisticsError:
                                    # Handle case where all values are identical
                                    calc_stats["std_dev"] = 0
                                
                                # Add percentiles for more datapoints
                                if len(values) > 4:
                                    percentiles = _calculate_percentiles(values)
                                    for key, val in percentiles.items():
                                        if val is not None:
                                            calc_stats[key] = _format_float(val)
                            
                            stats[measure] = calc_stats
                    result["statistics"] = stats
                
                # Group by analysis
                if group_by:
                    grouped_data = {}
                    for field in group_by:
                        groups = {}
                        for record in records:
                            # Handle many2one fields which are tuples (id, name)
                            key = record.get(field)
                            if isinstance(key, tuple) and len(key) > 1:
                                key = key[1]  # Use the name
                            elif key is False or key is None:
                                key = "Undefined"
                            
                            # Convert key to string for JSON compatibility
                            key_str = str(key)
                                
                            if key_str not in groups:
                                groups[key_str] = {"count": 0}
                            groups[key_str]["count"] += 1
                            
                            # Calculate metrics for each group
                            if measures:
                                for measure in measures:
                                    value = record.get(measure)
                                    if value is not None and value is not False:
                                        try:
                                            value = float(value)
                                            if "measures" not in groups[key_str]:
                                                groups[key_str]["measures"] = {}
                                            if measure not in groups[key_str]["measures"]:
                                                groups[key_str]["measures"][measure] = {
                                                    "sum": 0, "count": 0, "values": []
                                                }
                                            groups[key_str]["measures"][measure]["sum"] += value
                                            groups[key_str]["measures"][measure]["count"] += 1
                                            groups[key_str]["measures"][measure]["values"].append(value)
                                        except (ValueError, TypeError):
                                            # Skip non-numeric values
                                            pass
                        
                        # Calculate averages and other statistics
                        for group_key, group in groups.items():
                            if "measures" in group:
                                for measure, m_data in group["measures"].items():
                                    if m_data["count"] > 0:
                                        m_data["avg"] = _format_float(m_data["sum"] / m_data["count"])
                                        m_data["sum"] = _format_float(m_data["sum"])
                                        
                                        # Add more statistics if we have multiple values
                                        values = m_data.pop("values", [])  # Remove raw values after processing
                                        if len(values) > 1:
                                            m_data["min"] = _format_float(min(values))
                                            m_data["max"] = _format_float(max(values))
                                            
                                            try:
                                                m_data["median"] = _format_float(statistics.median(values))
                                            except statistics.StatisticsError:
                                                pass
                                                
                                            try:
                                                m_data["std_dev"] = _format_float(statistics.stdev(values))
                                            except statistics.StatisticsError:
                                                pass
                        
                        # Sort groups by count (descending)
                        grouped_data[field] = dict(sorted(
                            groups.items(), 
                            key=lambda x: x[1]["count"], 
                            reverse=True
                        ))
                    result["grouped_data"] = grouped_data
                    
            elif analysis_type == "trend":
                # Time-based trend analysis
                if time_range and 'field' in time_range:
                    date_field = time_range['field']
                    trend_data = {}
                    
                    # Group records by time period
                    for record in records:
                        if date_field in record and record[date_field]:
                            # Handle different date formats
                            if isinstance(record[date_field], str):
                                # Extract date part only for datetime strings (YYYY-MM-DD HH:MM:SS)
                                date_parts = record[date_field].split(' ')
                                date_str = date_parts[0] if len(date_parts) > 1 else record[date_field]
                                
                                # Convert date to YYYY-MM format for monthly trends
                                if analysis_type == "trend" and len(date_str) >= 10:
                                    date_str = date_str[:7]  # YYYY-MM
                            else:
                                date_str = str(record[date_field])
                            
                            if date_str not in trend_data:
                                trend_data[date_str] = {"count": 0}
                            trend_data[date_str]["count"] += 1
                            
                            # Calculate metrics for each period
                            if measures:
                                for measure in measures:
                                    value = record.get(measure)
                                    if value is not None and value is not False:
                                        try:
                                            value = float(value)
                                            if "measures" not in trend_data[date_str]:
                                                trend_data[date_str]["measures"] = {}
                                            if measure not in trend_data[date_str]["measures"]:
                                                trend_data[date_str]["measures"][measure] = []
                                            trend_data[date_str]["measures"][measure].append(value)
                                        except (ValueError, TypeError):
                                            # Skip non-numeric values
                                            pass
                    
                    # Calculate statistics for each period
                    for date_str, date_data in trend_data.items():
                        if "measures" in date_data:
                            for measure, values in date_data["measures"].items():
                                if values:
                                    date_data["measures"][measure] = {
                                        "sum": _format_float(sum(values)),
                                        "avg": _format_float(sum(values) / len(values)),
                                        "min": _format_float(min(values)),
                                        "max": _format_float(max(values)),
                                        "count": len(values)
                                    }
                                    
                                    # Add median for 3+ values
                                    if len(values) >= 3:
                                        date_data["measures"][measure]["median"] = _format_float(statistics.median(values))
                    
                    # Sort by date
                    result["trend_data"] = dict(sorted(trend_data.items()))
                    
                    # Calculate period-over-period changes
                    trend_periods = list(result["trend_data"].keys())
                    if len(trend_periods) > 1:
                        changes = {}
                        for i in range(1, len(trend_periods)):
                            current_period = trend_periods[i]
                            previous_period = trend_periods[i-1]
                            
                            current_data = result["trend_data"][current_period]
                            previous_data = result["trend_data"][previous_period]
                            
                            # Initialize changes for this period
                            period_changes = {
                                "count_change": current_data["count"] - previous_data["count"],
                                "count_change_pct": (
                                    (current_data["count"] - previous_data["count"]) / previous_data["count"] * 100
                                    if previous_data["count"] > 0 else None
                                )
                            }
                            
                            # Calculate changes for measures
                            if "measures" in current_data and "measures" in previous_data:
                                measure_changes = {}
                                for measure in current_data["measures"]:
                                    if measure in previous_data["measures"]:
                                        curr_sum = current_data["measures"][measure]["sum"]
                                        prev_sum = previous_data["measures"][measure]["sum"]
                                        
                                        sum_change = curr_sum - prev_sum
                                        sum_change_pct = (
                                            (curr_sum - prev_sum) / prev_sum * 100
                                            if prev_sum != 0 else None
                                        )
                                        
                                        measure_changes[measure] = {
                                            "sum_change": _format_float(sum_change),
                                            "sum_change_pct": _format_float(sum_change_pct) if sum_change_pct is not None else None
                                        }
                                        
                                period_changes["measures"] = measure_changes
                            
                            changes[f"{previous_period}_to_{current_period}"] = period_changes
                        
                        result["period_changes"] = changes
            
            elif analysis_type == "distribution":
                # Distribution analysis for measures
                if measures:
                    distributions = {}
                    for measure in measures:
                        values = _get_numeric_values(records, measure)
                        
                        if values:
                            # Get min and max for the range
                            min_val = min(values)
                            max_val = max(values)
                            
                            if min_val == max_val:
                                # All values are the same
                                distributions[measure] = {str(min_val): len(values)}
                            else:
                                # Determine number of bins based on data size (Sturges' formula)
                                n = len(values)
                                num_bins = max(5, min(20, int(1 + 3.322 * math.log10(n))))
                                
                                bin_width = (max_val - min_val) / num_bins
                                
                                # Initialize bins
                                bins = {}
                                for i in range(num_bins):
                                    lower = min_val + i * bin_width
                                    upper = min_val + (i + 1) * bin_width
                                    # Format with fewer decimal places for readability
                                    if bin_width < 0.1:
                                        bin_label = f"{lower:.3f} - {upper:.3f}"
                                    elif bin_width < 1:
                                        bin_label = f"{lower:.2f} - {upper:.2f}"
                                    else:
                                        bin_label = f"{int(lower) if lower == int(lower) else lower:.1f} - {int(upper) if upper == int(upper) else upper:.1f}"
                                    bins[bin_label] = 0
                                
                                # Count values in each bin
                                for val in values:
                                    for i in range(num_bins):
                                        lower = min_val + i * bin_width
                                        upper = min_val + (i + 1) * bin_width
                                        if (lower <= val < upper) or (i == num_bins - 1 and val == upper):
                                            if bin_width < 0.1:
                                                bin_label = f"{lower:.3f} - {upper:.3f}"
                                            elif bin_width < 1:
                                                bin_label = f"{lower:.2f} - {upper:.2f}"
                                            else:
                                                bin_label = f"{int(lower) if lower == int(lower) else lower:.1f} - {int(upper) if upper == int(upper) else upper:.1f}"
                                            bins[bin_label] += 1
                                            break
                                
                                # Add basic statistics
                                basic_stats = {
                                    "min": _format_float(min_val),
                                    "max": _format_float(max_val),
                                    "mean": _format_float(sum(values) / len(values)),
                                    "median": _format_float(statistics.median(values)),
                                    "count": len(values)
                                }
                                
                                # Add standard deviation if we have enough values
                                if len(values) > 1:
                                    basic_stats["std_dev"] = _format_float(statistics.stdev(values))
                                
                                # Add quartiles if we have enough values
                                if len(values) >= 4:
                                    percentiles = _calculate_percentiles(values)
                                    for key, val in percentiles.items():
                                        if val is not None:
                                            basic_stats[key] = _format_float(val)
                                
                                distributions[measure] = {
                                    "histogram": bins,
                                    "statistics": basic_stats
                                }
                    
                    result["distributions"] = distributions
            
            # Add model metadata
            try:
                model_info = odoo.get_model_info(model)
                if model_info and not isinstance(model_info, dict) or "error" not in model_info:
                    result["model_info"] = {
                        "name": model_info.get("name", model),
                        "description": model_info.get("description", ""),
                        "is_master_data": utils.is_master_data(model)
                    }
            except Exception:
                # Skip model info if we can't get it
                pass
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
    
    @mcp.tool(description="Analyze sales data")
    def analyze_sales(
        ctx: Context,
        date_from: str,
        date_to: str,
        salesperson_id: Optional[int] = None,
        metrics: List[str] = None,
        group_by: List[str] = None,
        analysis_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Specialized analysis tool for sales data
        
        Parameters:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            salesperson_id: Optional salesperson ID to filter sales
            metrics: Sales metrics to analyze (e.g., 'amount_total', 'amount_untaxed')
            group_by: Fields to group sales by (e.g., 'partner_id', 'user_id')
            analysis_type: Type of analysis ('summary', 'trend', 'distribution')
        """
        # Default metrics if none provided
        metrics = metrics or ["amount_total", "amount_untaxed", "amount_tax"]
        group_by = group_by or ["partner_id"]
        
        # Create domain for filtering
        domain = [
            ("date_order", ">=", date_from),
            ("date_order", "<=", date_to)
        ]
        if salesperson_id:
            domain.append(("user_id", "=", salesperson_id))
        
        # Time range for trend analysis
        time_range = {
            "field": "date_order",
            "start": date_from,
            "end": date_to
        }
        
        # Get needed fields for analysis
        fields = list(set(metrics + group_by + ["date_order"]))
        
        # Use the generic analysis tool
        return analyze_model_data(
            ctx,
            model="sale.order",
            domain=domain,
            fields=fields,
            group_by=group_by,
            measures=metrics,
            time_range=time_range,
            analysis_type=analysis_type
        )
