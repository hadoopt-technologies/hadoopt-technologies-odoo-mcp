"""
Enhanced search and create tools for Odoo MCP
"""

import logging
from typing import Any, Dict, List, Optional, Union

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import response models from generic_server
from .generic_server import OdooResponse, RecordResponse, CreateRecordResponse

def enhanced_search_records(
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
    Enhanced search for records with multi-company and archiving support
    
    Parameters:
        ctx: MCP Context
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
        RecordResponse: Contains matching records and count if requested
    """
    odoo = ctx.request_context.lifespan_context.odoo
    utils = ctx.request_context.lifespan_context.utils
    
    try:
        domain = domain or []
        final_domain = list(domain)  # Create a copy to avoid modifying the original
        
        # Check if the model has company field for multi-company support
        company_field = utils.get_company_field_name(model)
        
        # If it's a multi-company environment and model supports companies
        if company_field:
            company_info = utils.check_multi_company()
            
            # If a specific company is requested and it's in the allowed companies
            if company_id and company_id in company_info.get("allowed_company_ids", []):
                # Add company filter - handle both single and multi-company fields
                if company_field == "company_id":
                    final_domain.append([company_field, "=", company_id])
                elif company_field == "company_ids":
                    final_domain.append([company_field, "in", [company_id]])
            # If no specific company but we're in multi-company, limit to allowed companies
            elif company_info.get("is_multi_company") and company_info.get("allowed_company_ids"):
                allowed_ids = company_info.get("allowed_company_ids")
                if company_field == "company_id":
                    final_domain.append([company_field, "in", allowed_ids])
                elif company_field == "company_ids":
                    final_domain.append([company_field, "in", allowed_ids])
        
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
        
        # Use the updated search_read method that handles parameters correctly
        records = odoo.search_read(
            model, final_domain, fields=fields, limit=limit, offset=offset, order=order
        )
        
        return RecordResponse(success=True, records=records, count=count)
    except Exception as e:
        logger.error(f"Error searching records: {str(e)}")
        return RecordResponse(success=False, error=str(e))


def enhanced_create_record(
    ctx: Context,
    model: str,
    values: Dict[str, Any],
    company_id: Optional[int] = None,
    check_for_similar: bool = True
) -> Dict[str, Any]:
    """
    Enhanced create record with multi-company and duplicate detection
    
    Parameters:
        ctx: MCP Context
        model: The model name (e.g., 'res.partner')
        values: Dictionary of field values
        company_id: Specific company ID for the new record
        check_for_similar: Whether to check for similar existing records
        
    Returns:
        Dict containing:
        - success: Boolean indicating success
        - id: ID of the created record (if success)
        - error: Error message (if failure)
        - is_master_data: Whether this is master data
        - similar_records: Any similar records found (for potential duplicates)
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
        # If no company specified but multi-company, use current company
        elif company_field:
            company_info = utils.check_multi_company()
            current_company = company_info.get("current_company")
            if current_company:
                if company_field == "company_id":
                    values[company_field] = current_company[0]
                elif company_field == "company_ids":
                    values[company_field] = [(6, 0, [current_company[0]])]
        
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
            return {
                "success": True,
                "id": None,
                "is_master_data": is_master_data,
                "similar_records": similar_records,
                "message": "Similar records found - please confirm if you want to create a new record"
            }
        
        # Otherwise, create the record
        record_id = odoo.create_record(model, values)
        
        return {
            "success": True,
            "id": record_id,
            "is_master_data": is_master_data,
            "similar_records": similar_records
        }
    except Exception as e:
        logger.error(f"Error creating record: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "is_master_data": utils.is_master_data(model)
        }
