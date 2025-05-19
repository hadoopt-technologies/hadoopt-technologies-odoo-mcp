"""
Enhanced utilities for the Odoo MCP Server
"""

import logging
import re
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

class OdooEnhancedUtils:
    """Enhanced utilities for Odoo interactions"""
    
    def __init__(self, odoo_client):
        """Initialize with an Odoo client"""
        self.odoo = odoo_client
        self._company_cache = {}
        self._field_cache = {}
        self._model_type_cache = {}
        self._relation_cache = {}
        
    def check_multi_company(self) -> Dict[str, Any]:
        """
        Check if Odoo is configured for multi-company
        
        Returns:
            Dict with:
            - is_multi_company: Boolean indicating multi-company setup
            - companies: List of company records
            - user_companies: List of companies the current user belongs to
            - allowed_company_ids: IDs of companies the user can access
        """
        try:
            # Check cache first
            if 'multi_company_info' in self._company_cache:
                return self._company_cache['multi_company_info']
                
            # Get all companies
            companies = self.odoo.search_read(
                "res.company", 
                [], 
                fields=["id", "name", "parent_id"]
            )
            
            # Get current user info with allowed companies
            user_info = self.odoo.execute_method(
                "res.users", 
                "read", 
                [self.odoo.uid], 
                {"fields": ["company_id", "company_ids", "name"]}
            )[0]
            
            # Check if multi-company is active
            is_multi_company = len(companies) > 1
            
            # Get allowed company IDs for current user
            allowed_company_ids = user_info.get("company_ids", [])
            
            # Get user's companies
            user_companies = []
            if allowed_company_ids:
                user_companies = self.odoo.read_records(
                    "res.company", 
                    allowed_company_ids,
                    fields=["id", "name"]
                )
            
            # Current company
            current_company = None
            if user_info.get("company_id"):
                current_company = user_info["company_id"]
            
            result = {
                "is_multi_company": is_multi_company,
                "companies": companies,
                "user_companies": user_companies,
                "allowed_company_ids": allowed_company_ids,
                "current_company": current_company,
                "user_info": user_info
            }
            
            # Cache the result
            self._company_cache['multi_company_info'] = result
            
            return result
        except Exception as e:
            logger.error(f"Error checking multi-company: {str(e)}")
            return {
                "is_multi_company": False,
                "companies": [],
                "user_companies": [],
                "allowed_company_ids": [],
                "current_company": None,
                "error": str(e)
            }
    
    def check_record_access(self, model: str, record_id: int) -> Dict[str, Any]:
        """
        Check if current user has access to a specific record
        
        Args:
            model: Model name
            record_id: Record ID
            
        Returns:
            Dict with access information
        """
        try:
            # Check model access rights first
            model_access = self.odoo.execute_method(
                "ir.model.access", 
                "check", 
                [model, "read", False]
            )
            
            if not model_access:
                return {
                    "has_access": False,
                    "reason": "No model read access",
                    "model": model
                }
            
            # Check record rules by trying to read the record
            try:
                record = self.odoo.read_records(model, [record_id])
                has_access = bool(record)
            except Exception:
                has_access = False
                
            return {
                "has_access": has_access,
                "model": model,
                "record_id": record_id
            }
        except Exception as e:
            logger.error(f"Error checking record access: {str(e)}")
            return {
                "has_access": False,
                "error": str(e),
                "model": model,
                "record_id": record_id
            }
    
    def find_similar_records(
        self,
        model: str,
        search_text: str,
        fields: List[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find records similar to search text to handle typos
        
        Args:
            model: Model name
            search_text: Text to search for
            fields: Fields to search in (default: name)
            limit: Maximum records to return
            
        Returns:
            List of similar records
        """
        try:
            # Default to name field if none provided
            if not fields:
                # Get field info
                model_fields = self.odoo.get_model_fields(model)
                
                # Start with common name fields
                fields = []
                for field_name in ["name", "display_name", "complete_name"]:
                    if field_name in model_fields:
                        fields.append(field_name)
                        
                # If no name-like fields found, add other char fields
                if not fields:
                    for field, info in model_fields.items():
                        if info.get("type") == "char" and field not in fields:
                            fields.append(field)
                            if len(fields) >= 2:  # Limit to 2 fields for performance
                                break
            
            if not fields:
                return []
            
            # Build domain with OR conditions
            domain = ["&", ("active", "in", [True, False])]  # Include archived records
            
            # Add field conditions
            field_conditions = []
            for field in fields:
                field_conditions.append([field, "=", search_text])  # Exact match
                field_conditions.append([field, "ilike", search_text])  # Case-insensitive contains
            
            # Add the field conditions with OR
            if field_conditions:
                domain.append("|")  # Start OR chain
                for i in range(len(field_conditions) - 1):
                    domain.append(field_conditions[i])
                    if i < len(field_conditions) - 2:
                        domain.append("|")
                domain.append(field_conditions[-1])
            
            # Search using the domain
            records = self.odoo.search_read(model, domain, limit=limit)
            return records
        except Exception as e:
            logger.error(f"Error finding similar records: {str(e)}")
            return []
    
    def check_archived_status(self, model: str, record_id: int) -> Dict[str, Any]:
        """
        Check if a record is archived
        
        Args:
            model: Model name
            record_id: Record ID
            
        Returns:
            Dict with archive information
        """
        try:
            # Check if model has active field
            model_fields = self.odoo.get_model_fields(model)
            
            if "active" not in model_fields:
                return {
                    "can_be_archived": False,
                    "is_archived": False,
                    "model": model,
                    "record_id": record_id
                }
            
            # Check record's active status
            record = self.odoo.read_records(model, [record_id], fields=["active"])
            
            if not record:
                return {
                    "error": "Record not found",
                    "model": model,
                    "record_id": record_id
                }
            
            is_archived = not record[0].get("active", True)
            
            return {
                "can_be_archived": True,
                "is_archived": is_archived,
                "model": model,
                "record_id": record_id
            }
        except Exception as e:
            logger.error(f"Error checking archived status: {str(e)}")
            return {
                "error": str(e),
                "model": model,
                "record_id": record_id
            }
    
    def _get_models_referencing(self, model: str) -> Set[str]:
        """
        Get models that reference this model (have relations pointing to it)
        
        Args:
            model: Model name
            
        Returns:
            Set of model names that reference this model
        """
        # Check cache first
        cache_key = f"refs_to_{model}"
        if cache_key in self._relation_cache:
            return self._relation_cache[cache_key]
            
        try:
            # Get all models
            models_info = self.odoo.get_models()
            models = models_info.get("model_names", [])
            
            # Find models that reference the target model
            referencing_models = set()
            
            for other_model in models:
                # Skip system models and the model itself
                if other_model.startswith('ir.') or other_model == model:
                    continue
                    
                try:
                    # Get fields for this model
                    fields = self.odoo.get_model_fields(other_model)
                    
                    # Check for relation fields pointing to our model
                    for field_name, field_info in fields.items():
                        if field_info.get("relation") == model:
                            referencing_models.add(other_model)
                            break
                except Exception:
                    # Skip models we can't read
                    continue
            
            # Cache the result
            self._relation_cache[cache_key] = referencing_models
            return referencing_models
        except Exception as e:
            logger.error(f"Error getting models referencing {model}: {str(e)}")
            return set()
    
    def _count_relations_to(self, model: str) -> int:
        """
        Count how many other models have relations pointing to this model
        
        Args:
            model: Model name
            
        Returns:
            Number of models with relations to this model
        """
        referencing_models = self._get_models_referencing(model)
        return len(referencing_models)
    
    def _count_relations_from(self, model: str) -> Dict[str, int]:
        """
        Count relation types this model has pointing to other models
        
        Args:
            model: Model name
            
        Returns:
            Dictionary with counts of relation types
        """
        try:
            # Get fields for this model
            fields = self.odoo.get_model_fields(model)
            
            counts = {
                "many2one": 0,
                "one2many": 0,
                "many2many": 0
            }
            
            # Count relation fields by type
            for field_name, field_info in fields.items():
                field_type = field_info.get("type")
                if field_type in counts:
                    counts[field_type] += 1
            
            return counts
        except Exception as e:
            logger.error(f"Error counting relations from {model}: {str(e)}")
            return {"many2one": 0, "one2many": 0, "many2many": 0}
    
    def is_master_data(self, model: str) -> bool:
        """
        Dynamically determine if a model is master data based on its structure and relationships
        
        Args:
            model: Model name
            
        Returns:
            Boolean indicating if it's master data
        """
        # Check cache first
        if model in self._model_type_cache:
            return self._model_type_cache[model] == 'master'
            
        try:
            # Common known master data patterns
            if model in ['res.company', 'res.partner', 'res.users', 'res.currency']:
                self._model_type_cache[model] = 'master'
                return True
            
            # Dynamic detection based on model structure and relationships
            model_fields = self.odoo.get_model_fields(model)
            
            # Calculate master data score based on different indicators
            master_score = 0
            transactional_score = 0
            
            # Check for name-like fields (strong master data indicator)
            if any(field in model_fields for field in ['name', 'code', 'reference']):
                master_score += 3
            
            # Check for typical master data fields
            if 'active' in model_fields:
                master_score += 1
            if 'sequence' in model_fields:
                master_score += 1
            if 'company_id' in model_fields:
                master_score += 1
                
            # Check for typical transactional fields
            if any(field in model_fields for field in [
                'date', 'datetime', 'create_date', 'date_order', 'state'
            ]):
                transactional_score += 2
                
            # Check relations pointing to and from this model
            incoming_relations = self._count_relations_to(model)
            outgoing_relations = self._count_relations_from(model)
            
            # Master data typically has:
            # - Many incoming relations (other models reference it)
            # - Few outgoing many2one relations (doesn't depend on many other models)
            # - Few one2many relations (doesn't have many child collections)
            if incoming_relations > 3:
                master_score += 3
                
            if outgoing_relations["many2one"] > 5:
                transactional_score += 2
                
            if outgoing_relations["one2many"] > 3:
                transactional_score += 2
                
            # Use machine-readable naming pattern
            if "." in model:
                prefix = model.split('.')[0]
                
                # Common transactional prefixes
                if prefix in ['sale', 'purchase', 'account', 'stock', 'pos', 'mrp', 'project']:
                    transactional_score += 1
                    
                # Common suffix patterns indicate different types
                suffix = model.split('.')[-1]
                if suffix in ['line', 'move', 'entry', 'invoice', 'order', 'operation', 'picking']:
                    transactional_score += 2
                elif suffix in ['type', 'tag', 'category', 'group', 'config', 'template', 'rule']:
                    master_score += 2
            
            # Check record count (master data usually has fewer records)
            try:
                count = self.odoo.execute_method(model, "search_count", [])
                if count > 1000:
                    transactional_score += 2
                elif count < 100:
                    master_score += 1
            except Exception:
                # Skip this check if we can't get the count
                pass
                
            # Calculate result based on scores
            is_master = master_score > transactional_score
            
            # Cache the result
            self._model_type_cache[model] = 'master' if is_master else 'transactional'
            return is_master
            
        except Exception as e:
            logger.error(f"Error determining if model is master data: {str(e)}")
            
            # Fall back to checking model name patterns
            master_data_keywords = [
                "config", "setting", "parameter", "template", "type", "category",
                "tag", "stage", "status", "state", "rule", "group", "team"
            ]
            
            transactional_keywords = [
                "order", "invoice", "payment", "move", "line", "transaction", "entry",
                "journal", "operation", "request", "ticket", "session", "shift"
            ]
            
            # Check for master data keywords in the model name
            for keyword in master_data_keywords:
                if keyword in model:
                    self._model_type_cache[model] = 'master'
                    return True
            
            # Check for transactional keywords in the model name        
            for keyword in transactional_keywords:
                if keyword in model:
                    self._model_type_cache[model] = 'transactional'
                    return False
            
            # Default to transactional if we can't determine
            self._model_type_cache[model] = 'transactional'
            return False
    
    def get_company_field_name(self, model: str) -> Optional[str]:
        """
        Get the company field name for a model
        
        Args:
            model: Model name
            
        Returns:
            Name of the company field or None
        """
        # Check cache first
        if model in self._field_cache and 'company_field' in self._field_cache[model]:
            return self._field_cache[model]['company_field']
            
        try:
            # Get model fields
            fields = self.odoo.get_model_fields(model)
            
            # Check for common company fields
            company_field_names = ["company_id", "company_ids"]
            
            for field_name in company_field_names:
                if field_name in fields:
                    field_info = fields[field_name]
                    # Verify it's a company relation
                    if field_info.get("relation") == "res.company":
                        # Cache the result
                        if model not in self._field_cache:
                            self._field_cache[model] = {}
                        self._field_cache[model]['company_field'] = field_name
                        return field_name
            
            # Cache negative result
            if model not in self._field_cache:
                self._field_cache[model] = {}
            self._field_cache[model]['company_field'] = None
            return None
            
        except Exception as e:
            logger.error(f"Error getting company field: {str(e)}")
            return None
