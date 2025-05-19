"""
Model discovery tools for finding Odoo models by description
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class ModelDiscovery:
    """Tools for discovering and exploring Odoo models by description"""
    
    def __init__(self, odoo_client):
        """Initialize with an Odoo client"""
        self.odoo = odoo_client
        self._model_info_cache = {}
        self._relation_graph = {}
        
    def discover_models_by_description(
        self,
        description: str,
        limit: int = 10,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find models that match a description
        
        Args:
            description: Description or keywords to search for
            limit: Maximum number of models to return
            threshold: Minimum match score (0-1)
            
        Returns:
            List of matching models with scores
        """
        try:
            # Get all models if not already cached
            if not self._model_info_cache:
                all_models = self.odoo.get_models()
                model_details = all_models.get("models_details", {})
                
                # Enhance with additional data for better matching
                for model_name, info in model_details.items():
                    try:
                        # Get model info for description
                        model_info = self.odoo.get_model_info(model_name)
                        description_text = model_info.get("description", "")
                        
                        # Store enhanced info
                        self._model_info_cache[model_name] = {
                            "name": model_name,
                            "display_name": info.get("name", ""),
                            "description": description_text,
                            "modules": model_info.get("modules", "")
                        }
                    except Exception:
                        # If we can't get detailed info, use what we have
                        self._model_info_cache[model_name] = {
                            "name": model_name,
                            "display_name": info.get("name", ""),
                            "description": "",
                            "modules": ""
                        }
            
            # Preprocess the search description
            search_terms = self._preprocess_text(description)
            
            # Score each model
            scored_models = []
            for model_name, info in self._model_info_cache.items():
                # Generate text to match against
                match_text = f"{info['name']} {info['display_name']} {info['description']} {info['modules']}"
                match_terms = self._preprocess_text(match_text)
                
                # Calculate match score using both term matching and sequence similarity
                term_score = self._calculate_term_match_score(search_terms, match_terms)
                sequence_score = self._calculate_sequence_similarity(description.lower(), match_text.lower())
                
                # Combine scores, giving more weight to term matching
                score = (term_score * 0.7) + (sequence_score * 0.3)
                
                if score >= threshold:
                    scored_models.append({
                        "model": model_name,
                        "name": info["display_name"],
                        "description": info["description"],
                        "score": score
                    })
            
            # Sort by score (highest first) and limit results
            return sorted(scored_models, key=lambda x: x["score"], reverse=True)[:limit]
            
        except Exception as e:
            logger.error(f"Error discovering models by description: {str(e)}")
            return []
    
    def _preprocess_text(self, text: str) -> List[str]:
        """
        Preprocess text for better matching
        
        Args:
            text: Text to preprocess
            
        Returns:
            List of normalized terms
        """
        if not text:
            return []
            
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Remove common words
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
                      'in', 'on', 'at', 'to', 'for', 'with', 'by', 'of', 'this', 'that',
                      'these', 'those', 'it', 'its', 'from', 'as', 'has', 'have', 'had'}
        words = [word for word in words if word not in stop_words and len(word) > 1]
        
        return words
    
    def _calculate_term_match_score(self, search_terms: List[str], model_terms: List[str]) -> float:
        """
        Calculate match score between search terms and model terms
        
        Args:
            search_terms: Preprocessed search terms
            model_terms: Preprocessed model terms
            
        Returns:
            Match score (0-1)
        """
        if not search_terms or not model_terms:
            return 0.0
            
        # Count matching terms
        matches = 0
        for term in search_terms:
            if term in model_terms:
                matches += 1
            else:
                # Check for partial matches
                for model_term in model_terms:
                    if len(term) > 3 and len(model_term) > 3:
                        if term in model_term:
                            matches += 0.8  # Strong partial match (substring)
                            break
                        elif model_term in term:
                            matches += 0.6  # Moderate partial match
                            break
                        elif self._calculate_sequence_similarity(term, model_term) > 0.8:
                            matches += 0.5  # Fuzzy match (high similarity)
                            break
                        elif self._calculate_sequence_similarity(term, model_term) > 0.6:
                            matches += 0.3  # Weak fuzzy match (moderate similarity)
                            break
        
        # Calculate score based on both match quality and coverage
        return matches / len(search_terms) if search_terms else 0.0
    
    def _calculate_sequence_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using SequenceMatcher"""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _get_related_models(self, model_name: str, fields: Dict) -> Dict[str, List[str]]:
        """
        Get models that are related to the current model
        
        Args:
            model_name: Name of the model
            fields: Fields dictionary
            
        Returns:
            Dictionary with related models by relation type
        """
        related = {
            "many2one": [],   # Models this model references (this -> other)
            "one2many": [],   # Models that reference this model (other -> this)
            "many2many": []   # Models with many-to-many relationship
        }
        
        # Find outgoing relations (many2one, many2many)
        for field_name, field_info in fields.items():
            field_type = field_info.get("type")
            relation = field_info.get("relation")
            
            if relation and field_type in ["many2one", "many2many"]:
                if field_type == "many2one" and relation not in related["many2one"]:
                    related["many2one"].append(relation)
                elif field_type == "many2many" and relation not in related["many2many"]:
                    related["many2many"].append(relation)
        
        # Find incoming relations (models that reference this model)
        # This requires checking other models, which could be expensive,
        # so only do this if we don't have it cached
        if model_name not in self._relation_graph:
            # For efficiency, batch-check models we know have outgoing relations
            models_to_check = set()
            
            # Try to get all models with potential relations
            try:
                # Get all models
                all_models = self.odoo.get_models().get("model_names", [])
                
                # Get a sample of records from the current model
                sample_id = self.odoo.execute_method(model_name, "search", [], {"limit": 1})
                
                if sample_id:
                    # Check which models might reference this one
                    for other_model in all_models:
                        # Skip system models and the model itself
                        if other_model.startswith('ir.') or other_model == model_name:
                            continue
                        
                        # Check if this other model might reference our model
                        try:
                            other_fields = self.odoo.get_model_fields(other_model)
                            for field_name, field_info in other_fields.items():
                                if field_info.get("relation") == model_name:
                                    if field_info.get("type") == "one2many":
                                        if other_model not in related["one2many"]:
                                            related["one2many"].append(other_model)
                                    elif field_info.get("type") == "many2many":
                                        if other_model not in related["many2many"]:
                                            related["many2many"].append(other_model)
                        except Exception:
                            # Skip models we can't read
                            continue
            except Exception as e:
                logger.warning(f"Error finding related models: {e}")
            
            # Cache the results
            self._relation_graph[model_name] = related
        else:
            # Use cached relations
            related = self._relation_graph[model_name]
        
        return related
    
    def get_model_field_info(self, model_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a model's fields
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with field information
        """
        try:
            # Get field definitions
            fields = self.odoo.get_model_fields(model_name)
            
            # Categorize fields
            categorized_fields = {
                "identification": [],
                "descriptive": [],
                "numeric": [],
                "date": [],
                "boolean": [],
                "selection": [],
                "relational": [],
                "other": []
            }
            
            for field_name, field_info in fields.items():
                field_type = field_info.get("type")
                
                # Create base field info
                field_data = {
                    "name": field_name,
                    "type": field_type,
                    "string": field_info.get("string", field_name),
                    "required": field_info.get("required", False),
                    "readonly": field_info.get("readonly", False),
                    "store": field_info.get("store", True),
                    "help": field_info.get("help", "")
                }
                
                # Add to appropriate category
                if field_name in ['id', 'name', 'code', 'reference', 'sequence']:
                    categorized_fields["identification"].append(field_data)
                elif field_type in ["char", "text", "html"]:
                    field_data["size"] = field_info.get("size", 0)
                    categorized_fields["descriptive"].append(field_data)
                elif field_type in ["integer", "float", "monetary"]:
                    if field_type == "float":
                        field_data["digits"] = field_info.get("digits", (16, 2))
                    categorized_fields["numeric"].append(field_data)
                elif field_type in ["date", "datetime"]:
                    categorized_fields["date"].append(field_data)
                elif field_type == "boolean":
                    categorized_fields["boolean"].append(field_data)
                elif field_type == "selection":
                    field_data["selection"] = field_info.get("selection", [])
                    categorized_fields["selection"].append(field_data)
                elif field_type in ["many2one", "one2many", "many2many"]:
                    field_data["relation"] = field_info.get("relation", "")
                    field_data["relation_field"] = field_info.get("relation_field", "")
                    field_data["domain"] = field_info.get("domain", [])
                    categorized_fields["relational"].append(field_data)
                else:
                    categorized_fields["other"].append(field_data)
            
            # Add model metadata
            try:
                model_info = self.odoo.get_model_info(model_name)
                metadata = {
                    "name": model_info.get("name", model_name),
                    "description": model_info.get("description", ""),
                    "modules": model_info.get("modules", ""),
                    "state": model_info.get("state", "")
                }
            except Exception:
                metadata = {"name": model_name}
            
            # Find related models
            related_models = self._get_related_models(model_name, fields)
            
            return {
                "model": model_name,
                "metadata": metadata,
                "fields": categorized_fields,
                "related_models": related_models,
                "total_fields": len(fields)
            }
        except Exception as e:
            logger.error(f"Error getting model field info: {str(e)}")
            return {
                "model": model_name,
                "error": str(e)
            }
    
    def suggest_models_for_task(self, task_description: str) -> List[Dict[str, Any]]:
        """
        Suggest models that would be useful for a specific task
        
        Args:
            task_description: Description of the task
            
        Returns:
            List of suggested models with explanations
        """
        # Find potentially relevant models
        models = self.discover_models_by_description(task_description, limit=5)
        
        # Analyze task to identify required functionality
        task_terms = self._preprocess_text(task_description)
        
        # Check for common task patterns
        has_reporting = any(term in task_terms for term in ["report", "analysis", "analytics", "statistics", "metrics"])
        has_inventory = any(term in task_terms for term in ["inventory", "stock", "warehouse", "product", "item"])
        has_sales = any(term in task_terms for term in ["sale", "order", "customer", "client", "revenue"])
        has_purchase = any(term in task_terms for term in ["purchase", "vendor", "supplier", "buy", "procurement"])
        has_accounting = any(term in task_terms for term in ["invoice", "payment", "accounting", "finance", "tax"])
        has_manufacturing = any(term in task_terms for term in ["manufacturing", "production", "bom", "work order"])
        has_hr = any(term in task_terms for term in ["employee", "hr", "attendance", "leave", "payroll"])
        has_crm = any(term in task_terms for term in ["crm", "lead", "opportunity", "pipeline", "customer relationship"])
        has_project = any(term in task_terms for term in ["project", "task", "milestone", "deadline", "timesheet"])
        
        # Add common models based on task patterns
        suggestions = []
        
        # Add discovered models
        for model in models:
            suggestions.append({
                "model": model["model"],
                "name": model["name"],
                "relevance": f"Matched based on description with {model['score']:.2f} relevance score",
                "score": model["score"],
                "description": model.get("description", "")
            })
        
        # Add task-specific suggestions
        task_specific_models = []
        
        if has_reporting:
            task_specific_models.extend([
                ("ir.actions.report", "Reports", "Required for generating reports"),
                ("ir.ui.view", "Views", "Used for defining report templates")
            ])
        
        if has_inventory:
            task_specific_models.extend([
                ("stock.move", "Stock Moves", "Records movement of inventory items"),
                ("stock.picking", "Transfers", "Represents inventory transfers"),
                ("stock.location", "Locations", "Defines warehouse locations"),
                ("stock.warehouse", "Warehouses", "Manages warehouse configuration"),
                ("product.product", "Products", "Product variants"),
                ("product.template", "Product Templates", "Product templates")
            ])
        
        if has_sales:
            task_specific_models.extend([
                ("sale.order", "Sales Orders", "Manages customer orders"),
                ("sale.order.line", "Sales Order Lines", "Individual line items in sales orders"),
                ("res.partner", "Customers", "Customer information")
            ])
        
        if has_purchase:
            task_specific_models.extend([
                ("purchase.order", "Purchase Orders", "Manages vendor orders"),
                ("purchase.order.line", "Purchase Order Lines", "Individual line items in purchase orders"),
                ("product.supplierinfo", "Vendor Pricelists", "Supplier price information")
            ])
        
        if has_accounting:
            task_specific_models.extend([
                ("account.move", "Journal Entries", "Accounting journal entries"),
                ("account.invoice", "Invoices", "Customer and vendor invoices"),
                ("account.payment", "Payments", "Customer and vendor payments"),
                ("account.tax", "Taxes", "Tax configuration")
            ])
        
        if has_manufacturing:
            task_specific_models.extend([
                ("mrp.bom", "Bills of Materials", "Product manufacturing recipes"),
                ("mrp.production", "Manufacturing Orders", "Production work orders"),
                ("mrp.workcenter", "Work Centers", "Production resources")
            ])
        
        if has_hr:
            task_specific_models.extend([
                ("hr.employee", "Employees", "Employee information"),
                ("hr.contract", "Employee Contracts", "Employee contract details"),
                ("hr.attendance", "Attendances", "Employee attendance records"),
                ("hr.leave", "Time Off", "Employee leave requests")
            ])
        
        if has_crm:
            task_specific_models.extend([
                ("crm.lead", "Leads/Opportunities", "Sales pipeline management"),
                ("crm.team", "Sales Teams", "Team organization for CRM"),
                ("crm.stage", "CRM Stages", "Pipeline stages")
            ])
        
        if has_project:
            task_specific_models.extend([
                ("project.project", "Projects", "Project information"),
                ("project.task", "Tasks", "Project tasks"),
                ("account.analytic.line", "Timesheets", "Time tracking")
            ])
        
        # Add task-specific models if not already in suggestions
        for model, name, relevance in task_specific_models:
            if not any(s["model"] == model for s in suggestions):
                suggestions.append({
                    "model": model,
                    "name": name,
                    "relevance": relevance,
                    "score": 0.65
                })
        
        # Sort by score
        suggestions = sorted(suggestions, key=lambda x: x.get("score", 0), reverse=True)
        
        return suggestions[:10]  # Limit to top 10
