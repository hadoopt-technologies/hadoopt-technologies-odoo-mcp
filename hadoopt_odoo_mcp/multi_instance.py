"""
Multi-instance tools for Odoo MCP

Provides tools for working with multiple Odoo instances
"""

from typing import Dict, List, Any, Optional
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from .core.instance_manager import InstanceManager


class InstanceResponse(BaseModel):
    """Response model for instance operations."""
    success: bool = Field(description="Indicates if the operation was successful")
    message: Optional[str] = Field(default=None, description="Information message")
    instance: Optional[str] = Field(default=None, description="Current active instance")
    available_instances: Optional[List[str]] = Field(default=None, description="List of available instances")
    error: Optional[str] = Field(default=None, description="Error message, if any")
    

def register_multi_instance_tools(mcp: FastMCP, app_context):
    """Register multi-instance tools with the MCP server"""
    instance_manager = app_context.instance_manager
    
    @mcp.tool(description="List available Odoo instances")
    def list_instances(ctx: Context) -> Dict[str, Any]:
        """
        List all available Odoo instances configured in the system
        
        Returns:
            Dictionary with list of available instances
        """
        # Refresh available instances to ensure we have the latest list
        instance_manager.refresh_instances()
        
        return {
            "success": True,
            "instances": instance_manager.get_available_instances(),
            "active_instance": instance_manager.active_instance,
            "count": len(instance_manager.get_available_instances())
        }

    @mcp.tool(description="Switch active Odoo instance")
    def switch_instance(ctx: Context, instance_name: str) -> Dict[str, Any]:
        """
        Switch to a different Odoo instance
        
        Parameters:
            instance_name: Name of the instance to switch to
        
        Returns:
            Dictionary with result of the operation
        """
        # Refresh available instances
        instance_manager.refresh_instances()
        available_instances = instance_manager.get_available_instances()
        
        if instance_name not in available_instances:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not found. Available instances: {', '.join(available_instances)}",
                "available_instances": available_instances
            }
        
        # Switch active instance
        if not instance_manager.switch_instance(instance_name):
            return {
                "success": False,
                "error": f"Failed to connect to instance '{instance_name}'",
                "available_instances": available_instances
            }
        
        return {
            "success": True,
            "message": f"Switched to Odoo instance '{instance_name}'",
            "instance": instance_name
        }

    @mcp.tool(description="Get information about an Odoo instance")
    def get_instance_info(ctx: Context, instance_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about an Odoo instance
        
        Parameters:
            instance_name: Optional name of the instance to get info about (default: active instance)
        
        Returns:
            Dictionary with instance information
        """
        instance_name = instance_name or instance_manager.active_instance
        
        # Get instance info
        instance_info = instance_manager.get_instance_info(instance_name)
        
        if not instance_info.get("success", False):
            available_instances = instance_manager.get_available_instances()
            return {
                "success": False,
                "error": instance_info.get("error", f"Instance '{instance_name}' not found or not connected"),
                "available_instances": available_instances
            }
        
        return instance_info
    
    @mcp.tool(description="Create a new Odoo instance configuration")
    def add_instance(ctx: Context, instance_name: str, url: str, db: str, 
                    username: str, password: str) -> Dict[str, Any]:
        """
        Add a new Odoo instance configuration
        
        Parameters:
            instance_name: Name for the new instance
            url: Odoo server URL
            db: Database name
            username: Username for authentication
            password: Password for authentication
        
        Returns:
            Dictionary with result of the operation
        """
        # Check if instance already exists
        available_instances = instance_manager.get_available_instances()
        if instance_name in available_instances:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' already exists.",
                "available_instances": available_instances
            }
        
        # Add instance
        success = instance_manager.add_instance(
            instance_name=instance_name,
            url=url,
            db=db,
            username=username,
            password=password
        )
        
        if not success:
            return {
                "success": False,
                "error": f"Failed to add instance '{instance_name}'. Check logs for details.",
                "available_instances": instance_manager.get_available_instances()
            }
        
        return {
            "success": True,
            "message": f"Instance '{instance_name}' added successfully.",
            "instance": instance_name,
            "available_instances": instance_manager.get_available_instances()
        }
    
    @mcp.tool(description="Remove an Odoo instance configuration")
    def remove_instance(ctx: Context, instance_name: str) -> Dict[str, Any]:
        """
        Remove an Odoo instance configuration
        
        Parameters:
            instance_name: Name of the instance to remove
        
        Returns:
            Dictionary with result of the operation
        """
        # Check if instance exists
        available_instances = instance_manager.get_available_instances()
        if instance_name not in available_instances:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not found. Available instances: {', '.join(available_instances)}",
                "available_instances": available_instances
            }
        
        # Prevent removing the only instance
        if len(available_instances) == 1:
            return {
                "success": False,
                "error": "Cannot remove the only available instance.",
                "available_instances": available_instances
            }
        
        # Prevent removing active instance
        if instance_name == instance_manager.active_instance:
            return {
                "success": False,
                "error": "Cannot remove the active instance. Switch to another instance first.",
                "active_instance": instance_manager.active_instance,
                "available_instances": available_instances
            }
            
        # Remove instance
        success = instance_manager.remove_instance(instance_name)
        
        if not success:
            return {
                "success": False,
                "error": f"Failed to remove instance '{instance_name}'. Check logs for details.",
                "available_instances": instance_manager.get_available_instances()
            }
        
        return {
            "success": True,
            "message": f"Instance '{instance_name}' removed successfully.",
            "available_instances": instance_manager.get_available_instances()
        }
    
    @mcp.tool(description="Execute a method on an Odoo model with instance specification")
    def execute_method_on_instance(ctx: Context, instance_name: str, model: str, 
                                  method: str, args: Optional[List] = None, 
                                  kwargs: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a method on an Odoo model on a specific instance
        
        Parameters:
            instance_name: Name of the instance to use
            model: Model name (e.g., 'res.partner')
            method: Method name to execute
            args: Optional list of positional arguments
            kwargs: Optional dictionary of keyword arguments
        
        Returns:
            Dictionary with result of the operation
        """
        # Get the client for this instance
        try:
            with instance_manager.instance_context(instance_name) as client:
                if not client:
                    return {
                        "success": False,
                        "error": f"Failed to connect to instance '{instance_name}'",
                        "available_instances": instance_manager.get_available_instances()
                    }
                
                args = args or []
                kwargs = kwargs or {}
                
                result = client.execute_method(model, method, *args, **kwargs)
                return {
                    "success": True,
                    "result": result,
                    "instance": instance_name
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }
    
    # Create model-specific multi-instance tools
    @mcp.tool(description="Search for records in any Odoo instance with multi-company and archiving support")
    def search_records_in_instance(
        ctx: Context,
        instance_name: str,
        model: str,
        domain: Optional[List] = None,
        fields: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order: Optional[str] = None,
        include_archived: bool = False,
        company_id: Optional[int] = None,
        count_total: bool = False
    ) -> Dict[str, Any]:
        """
        Search for records in a specific Odoo instance
        
        Parameters:
            instance_name: Name of the instance to use
            model: Name of the model to search in
            domain: Search domain as a list of tuples
            fields: List of fields to return
            limit: Maximum number of records to return
            offset: Number of records to skip
            order: Sort order
            include_archived: Whether to include archived records
            company_id: Company ID to filter by
            count_total: Whether to return the total count of matching records
            
        Returns:
            Dictionary with search results
        """
        # Use the instance context manager for cleaner handling
        try:
            with instance_manager.instance_context(instance_name) as client:
                if not client:
                    return {
                        "success": False,
                        "error": f"Failed to connect to instance '{instance_name}'",
                        "available_instances": instance_manager.get_available_instances()
                    }
                
                utils = instance_manager.get_utils(instance_name)
                
                # Apply company filter if specified
                search_domain = domain or []
                if company_id is not None:
                    # Check if the model has company_id field
                    fields_info = client.get_model_fields(model)
                    if "company_id" in fields_info:
                        search_domain.append(("company_id", "=", company_id))
                
                # Handle archived records if needed
                if not include_archived and "active" in client.get_model_fields(model):
                    search_domain.append(("active", "=", True))
                
                # Perform count if requested
                total_count = None
                if count_total:
                    total_count = client.execute_method(model, "search_count", search_domain)
                
                # Perform search
                records = client.search_read(
                    model, search_domain, fields=fields, limit=limit, 
                    offset=offset, order=order
                )
                
                result = {
                    "success": True,
                    "records": records,
                    "model": model,
                    "instance": instance_name
                }
                
                if total_count is not None:
                    result["count"] = total_count
                
                return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }

    # Register the multi-instance tools with the proper models to the main MCP 
    # by adding wrappers to handle instance context properly
    instance_context_tools = {
        "search_records_in_instance": search_records_in_instance,
        "execute_method_on_instance": execute_method_on_instance,
        "list_instances": list_instances,
        "switch_instance": switch_instance,
        "get_instance_info": get_instance_info,
        "add_instance": add_instance,
        "remove_instance": remove_instance
    }
    
    # Return the registered tools for reference
    return instance_context_tools