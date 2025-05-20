"""
MCP server for Odoo integration

Provides MCP tools and resources for interacting with Odoo ERP systems
including generic data analysis capabilities
"""

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from .core.instance_manager import InstanceManager
from .analysis import register_analysis_tools
from .discovery_tools import register_discovery_tools
from .visualization import register_visualization_tools
from .multi_instance import register_multi_instance_tools
from .main_tools import register_main_tools


@dataclass
class AppContext:
    """Application context for the MCP server"""
    instance_manager: InstanceManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Application lifespan for initialization and cleanup
    """
    # Initialize instance manager
    instance_manager = InstanceManager()

    try:
        # Initialize tools with the instance manager
        app_context = AppContext(instance_manager=instance_manager)
        
        # Register all tools
        register_main_tools(server, instance_manager)
        register_analysis_tools(server, app_context)
        register_discovery_tools(server, app_context)
        register_visualization_tools(server, app_context)
        register_multi_instance_tools(server, app_context)
        
        yield app_context
    finally:
        # Cleanup connections
        instance_manager.disconnect_all()


# Create MCP server
mcp = FastMCP(
    "Odoo MCP Server",
    description="MCP Server for interacting with Odoo ERP systems",
    dependencies=["requests"],
    lifespan=app_lifespan,
)


@mcp.resource(
    "odoo://instances", description="List all available Odoo instances"
)
def get_instances_resource() -> str:
    """Lists all available Odoo instances"""
    from .core.config_manager import ConfigManager
    config_manager = ConfigManager()
    instances = config_manager.list_available_instances()
    return json.dumps({
        "instances": instances, 
        "count": len(instances)
    }, indent=2)


@mcp.resource(
    "odoo://models", description="List all available models in the Odoo system"
)
def get_models() -> str:
    """
    Lists all available models in the Odoo system
    """
    from .odoo_client import get_odoo_client
    odoo_client = get_odoo_client()
    models = odoo_client.get_models()
    return json.dumps(models, indent=2)


@mcp.resource(
    "odoo://model/{model_name}",
    description="Get detailed information about a specific model including fields",
)
def get_model_info(model_name: str) -> str:
    """
    Get information about a specific model

    Parameters:
        model_name: Name of the Odoo model (e.g., 'res.partner')
    """
    from .odoo_client import get_odoo_client
    odoo_client = get_odoo_client()
    try:
        # Get model info
        model_info = odoo_client.get_model_info(model_name)

        # Get field definitions
        fields = odoo_client.get_model_fields(model_name)
        model_info["fields"] = fields

        return json.dumps(model_info, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.resource(
    "odoo://record/{model_name}/{record_id}",
    description="Get detailed information of a specific record by ID",
)
def get_record(model_name: str, record_id: str) -> str:
    """
    Get a specific record by ID

    Parameters:
        model_name: Name of the Odoo model (e.g., 'res.partner')
        record_id: ID of the record
    """
    from .odoo_client import get_odoo_client
    odoo_client = get_odoo_client()
    try:
        record_id_int = int(record_id)
        record = odoo_client.read_records(model_name, [record_id_int])
        if not record:
            return json.dumps(
                {"error": f"Record not found: {model_name} ID {record_id}"}, indent=2
            )
        return json.dumps(record[0], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.resource(
    "odoo://search/{model_name}/{domain}",
    description="Search for records matching the domain",
)
def search_records_resource(model_name: str, domain: str) -> str:
    """
    Search for records that match a domain

    Parameters:
        model_name: Name of the Odoo model (e.g., 'res.partner')
        domain: Search domain in JSON format (e.g., '[["name", "ilike", "test"]]')
    """
    from .odoo_client import get_odoo_client
    odoo_client = get_odoo_client()
    try:
        # Parse domain from JSON string
        domain_list = json.loads(domain)

        # Set a reasonable default limit
        limit = 10

        # Perform search_read for efficiency
        results = odoo_client.search_read(model_name, domain_list, limit=limit)

        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


class RecordResponse(BaseModel):
    """Response model for search_records tool."""
    success: bool = Field(description="Indicates if the operation was successful")
    records: Optional[List[Dict]] = Field(
        default=None, description="List of records found"
    )
    count: Optional[int] = Field(default=None, description="Total count of records (if requested)")
    error: Optional[str] = Field(default=None, description="Error message, if any")
    instance: Optional[str] = Field(default=None, description="Instance used for the operation")


class CreateRecordResponse(BaseModel):
    """Response model for create_record tool."""
    success: bool = Field(description="Indicates if the record was created successfully")
    id: Optional[int] = Field(default=None, description="ID of the created record")
    is_master_data: bool = Field(default=False, description="Whether this is master data")
    similar_records: Optional[List[Dict]] = Field(
        default=None, description="Similar records if found"
    )
    message: Optional[str] = Field(default=None, description="Information message")
    error: Optional[str] = Field(default=None, description="Error message, if any")
    instance: Optional[str] = Field(default=None, description="Instance used for the operation")


# Entry point for the MCP server
if __name__ == "__main__":
    import os
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Run the server
    uvicorn.run(
        "hadoopt_odoo_mcp.server:mcp",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
