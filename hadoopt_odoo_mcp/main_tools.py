"""
Main tools for Odoo MCP

Registers the main tools for search, create, update, delete operations
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from .core.instance_manager import InstanceManager


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


def register_main_tools(mcp: FastMCP, instance_manager: InstanceManager):
    """Register main tools with the MCP server"""
    
    @mcp.tool(description="Execute a custom method on an Odoo model")
    def execute_method(
        ctx: Context,
        model: str,
        method: str,
        args: List = None,
        kwargs: Optional[Dict[str, Any]] = None,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a custom method on an Odoo model

        Parameters:
            model: The model name (e.g., 'res.partner')
            method: Method name to execute
            args: Positional arguments
            kwargs: Keyword arguments
            instance_name: Optional instance name to use

        Returns:
            Dictionary containing:
            - success: Boolean indicating success
            - result: Result of the method (if success)
            - error: Error message (if failure)
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            
            if not client:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "available_instances": instance_manager.get_available_instances(),
                    "instance": instance_name
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
        include_archived: bool = False,
        instance_name: Optional[str] = None
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
            instance_name: Optional instance name to use
            
        Returns:
            RecordResponse containing the matching records and count if requested
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the clients for this instance
            client = instance_manager.get_client(instance_name)
            utils = instance_manager.get_utils(instance_name)
            
            if not client or not utils:
                return RecordResponse(
                    success=False,
                    error=f"Failed to connect to Odoo instance '{instance_name}'",
                    instance=instance_name
                )
            
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
                        final_domain.append(["company_id", "=", company_id])
                    elif company_field == "company_ids":
                        final_domain.append(["company_ids", "in", [company_id]])
            
            # Handle archived records
            if not include_archived:
                # Check if model has active field for archiving
                model_fields = client.get_model_fields(model)
                if "active" in model_fields:
                    final_domain.append(["active", "=", True])
            
            # Count total if requested
            count = None
            if count_total:
                count = client.execute_method(model, "search_count", final_domain)
            
            # Search for records
            records = client.search_read(
                model, final_domain, fields=fields, limit=limit, offset=offset, order=order
            )
            
            return RecordResponse(
                success=True, 
                records=records, 
                count=count, 
                instance=instance_name
            )
        except Exception as e:
            return RecordResponse(
                success=False, 
                error=str(e), 
                instance=instance_name
            )


    @mcp.tool(description="Create a record in any Odoo model with duplicate detection")
    def create_record(
        ctx: Context,
        model: str,
        values: Dict[str, Any],
        company_id: Optional[int] = None,
        check_for_similar: bool = True,
        instance_name: Optional[str] = None
    ) -> CreateRecordResponse:
        """
        Create a record in any Odoo model with multi-company and duplicate detection
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            values: Dictionary of field values
            company_id: Specific company ID for the new record
            check_for_similar: Whether to check for similar existing records
            instance_name: Optional instance name to use
            
        Returns:
            CreateRecordResponse containing the result of the creation
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            utils = instance_manager.get_utils(instance_name)
            
            if not client or not utils:
                return CreateRecordResponse(
                    success=False,
                    error=f"Failed to connect to Odoo instance '{instance_name}'",
                    instance=instance_name
                )
            
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
                    message="Similar records found - please confirm if you want to create a new record",
                    instance=instance_name
                )
            
            # Otherwise, create the record
            record_id = client.create_record(model, values)
            
            return CreateRecordResponse(
                success=True,
                id=record_id,
                is_master_data=is_master_data,
                similar_records=similar_records,
                instance=instance_name
            )
        except Exception as e:
            is_master = False
            if utils:
                try:
                    is_master = utils.is_master_data(model)
                except:
                    pass
            
            return CreateRecordResponse(
                success=False,
                error=str(e),
                is_master_data=is_master,
                instance=instance_name
            )


    @mcp.tool(description="Update a record in any Odoo model")
    def update_record(
        ctx: Context,
        model: str,
        record_id: int,
        values: Dict[str, Any],
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a record in any Odoo model
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            record_id: ID of the record to update
            values: Dictionary of field values to update
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary containing result of the operation
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            
            if not client:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            result = client.update_record(model, record_id, values)
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


    @mcp.tool(description="Delete a record from any Odoo model")
    def delete_record(
        ctx: Context,
        model: str,
        record_id: int,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete a record from any Odoo model
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            record_id: ID of the record to delete
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary containing result of the operation
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            
            if not client:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            result = client.delete_record(model, record_id)
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


    @mcp.tool(description="Get information about a model")
    def get_model_metadata(
        ctx: Context,
        model: str,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get information about an Odoo model
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary containing model metadata
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            
            if not client:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            # Get model info
            model_info = client.get_model_info(model)
            
            # Get field definitions
            fields = client.get_model_fields(model)
            
            # Check if this is master data
            utils = instance_manager.get_utils(instance_name)
            is_master_data = utils.is_master_data(model) if utils else False
            
            return {
                "success": True,
                "model": model,
                "model_info": model_info,
                "fields": fields,
                "is_master_data": is_master_data,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }


    @mcp.tool(description="Check if a record is archived")
    def check_archived_status(
        ctx: Context,
        model: str,
        record_id: int,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a record is archived
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            record_id: ID of the record to check
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary indicating if the record is archived
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            
            if not client:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            # Check if model has active field
            fields = client.get_model_fields(model)
            
            if "active" not in fields:
                return {
                    "success": True,
                    "model": model,
                    "record_id": record_id,
                    "supports_archiving": False,
                    "instance": instance_name
                }
            
            # Read the record's active field
            record = client.read_records(model, [record_id], ["active"])
            
            if not record:
                return {
                    "success": False,
                    "error": f"Record not found: {model} ID {record_id}",
                    "instance": instance_name
                }
            
            archived = not record[0].get("active", True)
            
            return {
                "success": True,
                "model": model,
                "record_id": record_id,
                "supports_archiving": True,
                "archived": archived,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }


    @mcp.tool(description="Check if user has access to a specific record")
    def check_record_access(
        ctx: Context,
        model: str,
        record_id: int,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if the current user has access to a specific record
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            record_id: ID of the record to check
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary indicating access rights
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the client for this instance
            client = instance_manager.get_client(instance_name)
            
            if not client:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            # Check access rights for this record
            access_rights = client.execute_method(
                model, "check_access_rights", 
                ["read", "write", "create", "unlink"], 
                {"raise_exception": False}
            )
            
            # Check access rule for this specific record
            try:
                rule_check = client.execute_method(
                    model, "check_access_rule", [[record_id]], {"operation": "read"}
                )
                record_accessible = True
            except Exception:
                record_accessible = False
            
            # Try to read the record
            try:
                record = client.read_records(model, [record_id], ["id"])
                readable = len(record) > 0
            except Exception:
                readable = False
            
            return {
                "success": True,
                "model": model,
                "record_id": record_id,
                "access_rights": {
                    "read": access_rights[0],
                    "write": access_rights[1],
                    "create": access_rights[2],
                    "unlink": access_rights[3]
                },
                "record_accessible": record_accessible,
                "readable": readable,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }


    @mcp.tool(description="Find similar records to handle typos")
    def find_similar_records(
        ctx: Context,
        model: str,
        search_text: str,
        fields: List[str] = None,
        limit: int = 5,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find records similar to the search text
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            search_text: Text to search for
            fields: Optional fields to search in (default: name, display_name)
            limit: Maximum number of records to return
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary containing similar records
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the utils for this instance
            utils = instance_manager.get_utils(instance_name)
            
            if not utils:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            # Find similar records
            similar_records = utils.find_similar_records(
                model, search_text, fields=fields, limit=limit
            )
            
            return {
                "success": True,
                "model": model,
                "search_text": search_text,
                "similar_records": similar_records,
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }


    @mcp.tool(description="Check if a model is master or transactional data")
    def check_data_type(
        ctx: Context,
        model: str,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a model is master data or transactional data
        
        Parameters:
            model: The model name (e.g., 'res.partner')
            instance_name: Optional instance name to use
            
        Returns:
            Dictionary indicating if the model is master data
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the utils for this instance
            utils = instance_manager.get_utils(instance_name)
            
            if not utils:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            # Check if this is master data
            is_master_data = utils.is_master_data(model)
            
            return {
                "success": True,
                "model": model,
                "is_master_data": is_master_data,
                "data_type": "master" if is_master_data else "transactional",
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }


    @mcp.tool(description="Get multi-company information and available companies")
    def get_company_info(
        ctx: Context,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get information about the multi-company setup
        
        Parameters:
            instance_name: Optional instance name to use
        
        Returns:
            Dictionary with company information
        """
        # Use specific instance if provided, otherwise use active instance
        instance_name = instance_name or instance_manager.active_instance
        
        try:
            # Get the utils for this instance
            utils = instance_manager.get_utils(instance_name)
            
            if not utils:
                return {
                    "success": False,
                    "error": f"Failed to connect to Odoo instance '{instance_name}'",
                    "instance": instance_name
                }
            
            company_info = utils.check_multi_company()
            
            return {
                "success": True,
                "is_multi_company": company_info["is_multi_company"],
                "companies": company_info["companies"],
                "current_company": company_info["current_company"],
                "allowed_companies": company_info["user_companies"],
                "instance": instance_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }


    # Register the tools with the MCP server
    tools = {
        "execute_method": execute_method,
        "search_records": search_records,
        "create_record": create_record,
        "update_record": update_record,
        "delete_record": delete_record,
        "get_model_metadata": get_model_metadata,
        "check_archived_status": check_archived_status,
        "check_record_access": check_record_access,
        "find_similar_records": find_similar_records,
        "check_data_type": check_data_type,
        "get_company_info": get_company_info
    }
    
    return tools
