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

from .odoo_client import OdooClient, get_odoo_client
from .analysis import register_analysis_tools
from .enhanced_utils import OdooEnhancedUtils
from .discovery_tools import register_discovery_tools
from .visualization import register_visualization_tools


@dataclass
class AppContext:
    """Application context for the MCP server"""
    odoo: OdooClient
    utils: OdooEnhancedUtils


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Application lifespan for initialization and cleanup
    """
    # Initialize Odoo client on startup
    odoo_client = get_odoo_client()
    utils = OdooEnhancedUtils(odoo_client)

    try:
        yield AppContext(odoo=odoo_client, utils=utils)
    finally:
        # No cleanup needed for Odoo client
        pass


# Create MCP server
mcp = FastMCP(
    "Odoo MCP Server",
    description="MCP Server for interacting with Odoo ERP systems",
    dependencies=["requests"],
    lifespan=app_lifespan,
)

# Register tools
register_analysis_tools(mcp)
register_discovery_tools(mcp)
register_visualization_tools(mcp)


@mcp.resource(
    "odoo://models", description="List all available models in the Odoo system"
)
def get_models() -> str:
    """Lists all available models in the Odoo system"""
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


@mcp.tool(description="Execute a custom method on an Odoo model")
def execute_method(
    ctx: Context,
    model: str,
    method: str,
    args: List = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute a custom method on an Odoo model

    Parameters:
        model: The model name (e.g., 'res.partner')
        method: Method name to execute
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Dictionary containing:
        - success: Boolean indicating success
        - result: Result of the method (if success)
        - error: Error message (if failure)
    """
    odoo = ctx.request_context.lifespan_context.odoo
    try:
        args = args or []
        kwargs = kwargs or {}
        result = odoo.execute_method(model, method, *args, **kwargs)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Search for records in any Odoo model with multi-company and archiving support")
def search_records(
    ctx: Context,
    model: str,
    domain: List = None,
    fields: List[str] = None,
    limit: int = 100,
    offset: int = 0,
    order: str = None,
    count_total: bool = False,
    company_id: Optional[int] = None,
    include_archived: bool = False
) -> RecordResponse:
    """
    Search for records in any Odoo model with multi-company and archiving support
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        domain: Search domain (e.g., [['name', 'ilike', 'test']])
        fields: List of field names to return (None for all)
        limit: Maximum number of records to return
        offset: Number of records to skip
        order: Sorting criteria (e.g., 'name ASC, id DESC')
        count_total: Whether to count total matching records
        company_id: Specific company ID to filter by (for multi-company)
        include_archived: Whether to include archived records
        
    Returns:
        RecordResponse containing the matching records and count if requested
    """
    odoo = ctx.request_context.lifespan_context.odoo
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        domain = domain or []
        final_domain = list(domain)  # Create a copy
        
        # Check if the model has company field for multi-company support
        company_field = utils.get_company_field_name(model)
        
        # If it's a multi-company environment and model supports companies
        if company_field and company_id:
            company_info = utils.check_multi_company()
            
            # If a specific company is requested and it's in allowed companies
            if company_id in company_info.get("allowed_company_ids", []):
                # Add company filter based on field type
                if company_field == "company_id":
                    final_domain.append([company_field, "=", company_id])
                elif company_field == "company_ids":
                    final_domain.append([company_field, "in", [company_id]])
        
        # Handle archived records
        if not include_archived:
            # Check if model has active field for archiving
            model_fields = odoo.get_model_fields(model)
            if "active" in model_fields:
                final_domain.append(["active", "=", True])
        
        # Count total if requested
        count = None
        if count_total:
            count = odoo.execute_method(model, "search_count", final_domain)
        
        # Search for records
        records = odoo.search_read(
            model, final_domain, fields=fields, limit=limit, offset=offset, order=order
        )
        
        return RecordResponse(success=True, records=records, count=count)
    except Exception as e:
        return RecordResponse(success=False, error=str(e))


@mcp.tool(description="Create a record in any Odoo model with duplicate detection")
def create_record(
    ctx: Context,
    model: str,
    values: Dict[str, Any],
    company_id: Optional[int] = None,
    check_for_similar: bool = True
) -> CreateRecordResponse:
    """
    Create a record in any Odoo model with multi-company and duplicate detection
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        values: Dictionary of field values
        company_id: Specific company ID for the new record
        check_for_similar: Whether to check for similar existing records
        
    Returns:
        CreateRecordResponse containing the result of the creation
    """
    odoo = ctx.request_context.lifespan_context.odoo
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        # Check if this is master data
        is_master_data = utils.is_master_data(model)
        
        # Check for company field
        company_field = utils.get_company_field_name(model)
        
        # Add company_id to values if specified and model supports it
        if company_id and company_field:
            if company_field == "company_id":
                values[company_field] = company_id
            elif company_field == "company_ids":
                values[company_field] = [(6, 0, [company_id])]  # Command 6: replace with list
        
        # Check for similar records if requested and if the model has a name field
        similar_records = []
        if check_for_similar and is_master_data:
            # Try to find by name or a similar name field
            name_value = None
            for field in ["name", "display_name", "description"]:
                if field in values:
                    name_value = values[field]
                    break
            
            if name_value:
                similar_records = utils.find_similar_records(model, name_value)
        
        # If similar records found for master data, return them without creating
        if similar_records and is_master_data:
            return CreateRecordResponse(
                success=True,
                id=None,
                is_master_data=is_master_data,
                similar_records=similar_records,
                message="Similar records found - please confirm if you want to create a new record"
            )
        
        # Otherwise, create the record
        record_id = odoo.create_record(model, values)
        
        return CreateRecordResponse(
            success=True,
            id=record_id,
            is_master_data=is_master_data,
            similar_records=similar_records
        )
    except Exception as e:
        return CreateRecordResponse(
            success=False,
            error=str(e),
            is_master_data=utils.is_master_data(model)
        )


@mcp.tool(description="Update a record in any Odoo model")
def update_record(
    ctx: Context,
    model: str,
    record_id: int,
    values: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update a record in any Odoo model
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        record_id: ID of the record to update
        values: Dictionary of field values to update
        
    Returns:
        Dictionary containing result of the operation
    """
    odoo = ctx.request_context.lifespan_context.odoo
    
    try:
        result = odoo.update_record(model, record_id, values)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete a record from any Odoo model")
def delete_record(
    ctx: Context,
    model: str,
    record_id: int
) -> Dict[str, Any]:
    """
    Delete a record from any Odoo model
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        record_id: ID of the record to delete
        
    Returns:
        Dictionary containing result of the operation
    """
    odoo = ctx.request_context.lifespan_context.odoo
    
    try:
        result = odoo.delete_record(model, record_id)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Process multiple records in batches")
def batch_process_records(
    ctx: Context,
    model: str,
    domain: List,
    operation: str,
    values: Optional[Dict[str, Any]] = None,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Process multiple records in batches for better performance
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        domain: Search domain to filter records
        operation: Operation ('update', 'delete', 'archive', 'unarchive')
        values: Dictionary of field values for update operation
        batch_size: Size of each batch
        
    Returns:
        Dictionary with operation results
    """
    odoo = ctx.request_context.lifespan_context.odoo
    
    try:
        # Get record IDs
        record_ids = odoo.execute_method(model, "search", domain)
        total_count = len(record_ids)
        
        if total_count == 0:
            return {
                "success": True,
                "message": "No records found matching the domain",
                "processed": 0,
                "total": 0
            }
            
        processed_count = 0
        
        # Process records in batches
        for i in range(0, total_count, batch_size):
            batch_ids = record_ids[i:i+batch_size]
            
            if operation == 'update' and values:
                # Update batch
                try:
                    odoo.execute_method(model, "write", [batch_ids, values])
                    processed_count += len(batch_ids)
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "processed": processed_count,
                        "total": total_count
                    }
                    
            elif operation == 'delete':
                # Delete batch
                try:
                    odoo.execute_method(model, "unlink", [batch_ids])
                    processed_count += len(batch_ids)
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "processed": processed_count,
                        "total": total_count
                    }
                    
            elif operation == 'archive':
                # Archive batch - check if model has active field
                model_fields = odoo.get_model_fields(model)
                if "active" in model_fields:
                    try:
                        odoo.execute_method(model, "write", [batch_ids, {"active": False}])
                        processed_count += len(batch_ids)
                    except Exception as e:
                        return {
                            "success": False,
                            "error": str(e),
                            "processed": processed_count,
                            "total": total_count
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Model {model} does not support archiving",
                        "processed": 0,
                        "total": total_count
                    }
                    
            elif operation == 'unarchive':
                # Unarchive batch - check if model has active field
                model_fields = odoo.get_model_fields(model)
                if "active" in model_fields:
                    try:
                        odoo.execute_method(model, "write", [batch_ids, {"active": True}])
                        processed_count += len(batch_ids)
                    except Exception as e:
                        return {
                            "success": False,
                            "error": str(e),
                            "processed": processed_count,
                            "total": total_count
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Model {model} does not support archiving",
                        "processed": 0,
                        "total": total_count
                    }
            else:
                return {
                    "success": False,
                    "error": f"Invalid operation: {operation}",
                    "processed": 0,
                    "total": total_count
                }
                
        return {
            "success": True,
            "operation": operation,
            "model": model,
            "processed": processed_count,
            "total": total_count
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool(description="Get multi-company information")
def get_company_info(ctx: Context) -> Dict[str, Any]:
    """
    Get information about the multi-company setup
    
    Returns:
        Dictionary with company information
    """
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        company_info = utils.check_multi_company()
        return {
            "success": True,
            "is_multi_company": company_info["is_multi_company"],
            "companies": company_info["companies"],
            "current_company": company_info["current_company"],
            "allowed_companies": company_info["user_companies"]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool(description="Check if user has access to a specific record")
def check_record_access(
    ctx: Context,
    model: str,
    record_id: int
) -> Dict[str, Any]:
    """
    Check if the current user has access to a specific record
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        record_id: ID of the record to check
        
    Returns:
        Dictionary with access information
    """
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        access_info = utils.check_record_access(model, record_id)
        return {
            "success": True,
            **access_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool(description="Check if a record is archived")
def check_archived_status(
    ctx: Context,
    model: str,
    record_id: int
) -> Dict[str, Any]:
    """
    Check if a record is archived
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        record_id: ID of the record to check
        
    Returns:
        Dictionary with archive information
    """
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        archived_info = utils.check_archived_status(model, record_id)
        return {
            "success": True,
            **archived_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool(description="Find similar records to handle typos")
def find_similar_records(
    ctx: Context,
    model: str,
    search_text: str,
    fields: List[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Find records similar to search text to handle typos
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        search_text: Text to search for
        fields: Fields to search in (default: name, display_name)
        limit: Maximum records to return
        
    Returns:
        Dictionary with similar records
    """
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        records = utils.find_similar_records(model, search_text, fields, limit)
        return {
            "success": True,
            "records": records,
            "count": len(records)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool(description="Check if a model is master data")
def check_data_type(
    ctx: Context,
    model: str
) -> Dict[str, Any]:
    """
    Check if a model is considered master data or transactional data
    
    Parameters:
        model: The model name (e.g., 'res.partner')
        
    Returns:
        Dictionary with data type information
    """
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        is_master = utils.is_master_data(model)
        
        return {
            "success": True,
            "model": model,
            "is_master_data": is_master,
            "is_transactional_data": not is_master
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
