"""
Model discovery tools registration for Odoo MCP
"""

import json
from typing import Dict, List, Any, Optional, Union

from mcp.server.fastmcp import Context, FastMCP

from .model_discovery import ModelDiscovery


def register_discovery_tools(mcp: FastMCP, app_context):
    """Register model discovery tools with the MCP server"""
    instance_manager = app_context.instance_manager
    
    @mcp.tool(description="Discover Odoo models by description")
    def discover_models_by_description(
        ctx: Context,
        description: str,
        limit: int = 10,
        threshold: float = 0.3,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find models that match a description
        
        Parameters:
            description: Description or keywords to search for
            limit: Maximum number of models to return
            threshold: Minimum match score (0-1)
            instance_name: Optional name of the instance to use (default: active instance)
            
        Returns:
            Dictionary with matching models and scores
        """
        instance_name = instance_name or instance_manager.active_instance
        odoo_client = instance_manager.get_client(instance_name)
        
        if not odoo_client:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not found.",
                "available_instances": instance_manager.get_available_instances()
            }
        
        try:
            model_discovery = ModelDiscovery(odoo_client)
            models = model_discovery.discover_models_by_description(
                description, limit, threshold
            )
            
            return {
                "success": True,
                "models": models,
                "count": len(models),
                "description": description,
                "query": description,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "description": description,
                "instance": instance_name
            }
    
    @mcp.tool(description="Get detailed field information for a model")
    def get_model_field_info(
        ctx: Context,
        model_name: str,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a model's fields
        
        Parameters:
            model_name: Name of the model
            instance_name: Optional name of the instance to use (default: active instance)
            
        Returns:
            Dictionary with categorized field information
        """
        instance_name = instance_name or instance_manager.active_instance
        odoo_client = instance_manager.get_client(instance_name)
        
        if not odoo_client:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not found.",
                "available_instances": instance_manager.get_available_instances()
            }
        
        try:
            model_discovery = ModelDiscovery(odoo_client)
            field_info = model_discovery.get_model_field_info(model_name)
            
            # Make sure we have a valid response
            if "error" in field_info and not field_info.get("fields", {}):
                return {
                    "success": False,
                    "error": field_info["error"],
                    "model": model_name,
                    "instance": instance_name
                }
            
            return {
                "success": True,
                "instance": instance_name,
                **field_info
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": model_name,
                "instance": instance_name
            }
    
    @mcp.tool(description="Suggest models for a specific task")
    def suggest_models_for_task(
        ctx: Context,
        task_description: str,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Suggest models that would be useful for a specific task
        
        Parameters:
            task_description: Description of the task
            instance_name: Optional name of the instance to use (default: active instance)
            
        Returns:
            Dictionary with suggested models and explanations
        """
        instance_name = instance_name or instance_manager.active_instance
        odoo_client = instance_manager.get_client(instance_name)
        
        if not odoo_client:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not found.",
                "available_instances": instance_manager.get_available_instances()
            }
        
        try:
            model_discovery = ModelDiscovery(odoo_client)
            suggestions = model_discovery.suggest_models_for_task(task_description)
            
            # Group suggestions by category
            categories = {}
            for suggestion in suggestions:
                # Extract category from model name (first part before dot)
                category = suggestion["model"].split('.')[0] if '.' in suggestion["model"] else "other"
                
                if category not in categories:
                    categories[category] = []
                    
                categories[category].append(suggestion)
            
            return {
                "success": True,
                "suggestions": suggestions,
                "categories": categories,
                "count": len(suggestions),
                "task": task_description,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task": task_description,
                "instance": instance_name
            }
    
    @mcp.tool(description="Get schema of Odoo models with relationships")
    def discover_schema(
        ctx: Context,
        model_pattern: Optional[str] = None,
        include_fields: bool = True,
        include_relations: bool = True,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Discover data model schema and relationships
        
        Parameters:
            model_pattern: Optional pattern to filter model names (e.g., 'sale.*')
            include_fields: Whether to include field definitions
            include_relations: Whether to include model relationships
            instance_name: Optional name of the instance to use (default: active instance)
            
        Returns:
            Dictionary with model schema information
        """
        instance_name = instance_name or instance_manager.active_instance
        odoo_client = instance_manager.get_client(instance_name)
        
        if not odoo_client:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not found.",
                "available_instances": instance_manager.get_available_instances()
            }
        
        try:
            # Get all models matching the pattern
            all_models = odoo_client.get_models(pattern=model_pattern)
            model_names = all_models.get("model_names", [])
            
            if not model_names:
                return {
                    "success": True,
                    "message": f"No models found matching pattern: {model_pattern}",
                    "models": {},
                    "instance": instance_name
                }
            
            # Initialize model discovery
            model_discovery = ModelDiscovery(odoo_client)
            
            # Process schema data
            schema = {}
            relations = []
            
            for model_name in model_names:
                try:
                    # Get basic model info
                    model_info = odoo_client.get_model_info(model_name)
                    
                    schema_entry = {
                        "name": model_name,
                        "display_name": model_info.get("name", model_name),
                        "description": model_info.get("description", "")
                    }
                    
                    # Add fields if requested
                    if include_fields:
                        fields = odoo_client.get_model_fields(model_name)
                        field_info = {}
                        
                        for field_name, field_data in fields.items():
                            # Simplify field info
                            field_info[field_name] = {
                                "type": field_data.get("type"),
                                "string": field_data.get("string", field_name),
                                "required": field_data.get("required", False)
                            }
                            
                            # Add relation info if it's a relational field
                            relation = field_data.get("relation")
                            if relation and include_relations:
                                field_info[field_name]["relation"] = relation
                                relation_type = field_data.get("type")
                                
                                # Add to relations list
                                relations.append({
                                    "from": model_name,
                                    "to": relation,
                                    "type": relation_type,
                                    "field": field_name
                                })
                        
                        schema_entry["fields"] = field_info
                    
                    schema[model_name] = schema_entry
                except Exception as e:
                    # Skip models with access errors
                    continue
            
            return {
                "success": True,
                "models": schema,
                "relations": relations if include_relations else [],
                "count": len(schema),
                "pattern": model_pattern,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "pattern": model_pattern,
                "instance": instance_name
            }
    
    # Add MCP resource for model discovery API
    @mcp.resource(
        "odoo://discover/{description}",
        description="Discover models by description"
    )
    def discover_models_resource(description: str) -> str:
        """
        Discover models by description
        
        Parameters:
            description: Description to search for
        """
        # Get Odoo client directly since we're outside the tool context
        from .odoo_client import get_odoo_client
        odoo_client = get_odoo_client()
        model_discovery = ModelDiscovery(odoo_client)
        
        try:
            models = model_discovery.discover_models_by_description(description)
            return json.dumps({"success": True, "models": models, "query": description}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e), "query": description}, indent=2)
            
    # Add MCP resource for field information
    @mcp.resource(
        "odoo://model/{model_name}/fields",
        description="Get detailed field information for a model"
    )
    def model_fields_resource(model_name: str) -> str:
        """
        Get detailed field information for a model
        
        Parameters:
            model_name: Name of the model
        """
        # Get Odoo client directly
        from .odoo_client import get_odoo_client
        odoo_client = get_odoo_client()
        model_discovery = ModelDiscovery(odoo_client)
        
        try:
            field_info = model_discovery.get_model_field_info(model_name)
            return json.dumps({"success": True, **field_info}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e), "model": model_name}, indent=2)
