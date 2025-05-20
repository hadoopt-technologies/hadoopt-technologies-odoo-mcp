"""
Flexible Odoo XML-RPC client for MCP integration
"""

import re
import socket
import urllib.parse
import http.client
import xmlrpc.client
import logging
import time
from typing import Any, Dict, List, Optional, Union, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OdooClient:
    """Generic client for interacting with any Odoo instance via XML-RPC"""

    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
        timeout: int = 30,
        verify_ssl: bool = True,
        cache_enabled: bool = True,
        cache_ttl: int = 300,
    ):
        """Initialize the Odoo client with connection parameters"""
        # Ensure URL has a protocol
        if not re.match(r"^https?://", url):
            url = f"http://{url}"

        # Remove trailing slash from URL if present
        url = url.rstrip("/")

        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None

        # Connection settings
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Set up connections
        self._common = None
        self._models = None

        # Cache settings
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self._cache = {} if cache_enabled else None
        self._cache_timestamps = {} if cache_enabled else None

        # Parse hostname for logging
        parsed_url = urllib.parse.urlparse(self.url)
        self.hostname = parsed_url.netloc

        # Connect to Odoo
        self._connect()

    def _connect(self):
        """Initialize the XML-RPC connection and authenticate"""
        is_https = self.url.startswith("https://")
        connect = OdooConnect(
            timeout=self.timeout, use_https=is_https, verify_ssl=self.verify_ssl
        )

        logger.info(f"Connecting to Odoo at: {self.url}")

        # Set up endpoints
        self._common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common", transport=connect
        )
        self._models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object", transport=connect
        )

        # Authenticate and get user ID
        try:
            self.uid = self._common.authenticate(
                self.db, self.username, self.password, {}
            )
            if not self.uid:
                raise ValueError("Authentication failed: Invalid credentials")
            logger.info(f"Authentication successful, user ID: {self.uid}")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise ValueError(f"Failed to authenticate with Odoo: {str(e)}")

    def _execute(self, model: str, method: str, *args, **kwargs) -> Any:
        """Execute a method on an Odoo model"""
        # Check for cache hit (only for read methods)
        if self.cache_enabled and method in ["search", "read", "search_read", "fields_get"]:
            cache_key = f"{model}:{method}:{str(args)}:{str(kwargs)}"
            if cache_key in self._cache:
                # Check if cache is still valid
                if time.time() - self._cache_timestamps[cache_key] < self.cache_ttl:
                    return self._cache[cache_key]

        # Sanitize kwargs to avoid dict adaptation issues
        sanitized_kwargs = {}
        for key, value in kwargs.items():
            # Ensure numeric values are actual numbers, not dicts
            if key in ['offset', 'limit'] and value is not None:
                sanitized_kwargs[key] = int(value)
            else:
                sanitized_kwargs[key] = value
                
        # Execute the method
        try:
            result = self._models.execute_kw(
                self.db, self.uid, self.password, model, method, args, sanitized_kwargs
            )
        except Exception as e:
            logger.error(f"Error in execute_kw for {model}.{method}: {e}")
            raise

        # Cache the result if appropriate
        if self.cache_enabled and method in ["search", "read", "search_read", "fields_get"]:
            cache_key = f"{model}:{method}:{str(args)}:{str(kwargs)}"
            self._cache[cache_key] = result
            self._cache_timestamps[cache_key] = time.time()

        return result

    def execute_method(self, model: str, method: str, *args, **kwargs) -> Any:
        """
        Execute an arbitrary method on any Odoo model

        Args:
            model: The model name (e.g., 'res.partner')
            method: Method name to execute
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method

        Returns:
            Result of the method execution
        """
        return self._execute(model, method, *args, **kwargs)

    def get_models(self, pattern: str = None) -> Dict:
        """
        Get a list of all available models, optionally filtered by pattern

        Args:
            pattern: Optional regex pattern to filter model names

        Returns:
            Dictionary with model information
        """
        try:
            # Get all model IDs
            model_ids = self._execute("ir.model", "search", [])

            if not model_ids:
                return {
                    "model_names": [],
                    "models_details": {},
                    "error": "No models found",
                }

            # Read model data
            result = self._execute("ir.model", "read", model_ids, ["model", "name"])

            # Filter models by pattern if provided
            if pattern:
                regex = re.compile(pattern)
                filtered_results = [r for r in result if regex.search(r["model"])]
                models = sorted([rec["model"] for rec in filtered_results])
                models_details = {
                    rec["model"]: {"name": rec.get("name", "")}
                    for rec in filtered_results
                }
            else:
                # Extract and sort model names alphabetically
                models = sorted([rec["model"] for rec in result])
                models_details = {
                    rec["model"]: {"name": rec.get("name", "")}
                    for rec in result
                }

            return {
                "model_names": models,
                "models_details": models_details,
            }
        except Exception as e:
            logger.error(f"Error retrieving models: {str(e)}")
            return {"model_names": [], "models_details": {}, "error": str(e)}

    def get_model_info(self, model_name: str) -> Dict:
        """Get detailed information about a specific model"""
        try:
            # Get basic model info without including 'fields' in the request
            result = self._execute(
                "ir.model",
                "search_read",
                [("model", "=", model_name)],
                {"fields": ["name", "model", "description", "modules", "state"]}
            )

            if not result:
                return {"error": f"Model {model_name} not found"}

            model_info = result[0]

            # Get access rights
            access_rights = self._execute(
                "ir.model.access",
                "search_read",
                [("model_id.model", "=", model_name)],
                {"fields": ["name", "perm_read", "perm_write", "perm_create", "perm_unlink"]},
            )
            model_info["access_rights"] = access_rights

            return model_info
        except Exception as e:
            logger.error(f"Error retrieving model info: {str(e)}")
            return {"error": str(e)}

    def get_model_fields(self, model_name: str, attributes: List[str] = None) -> Dict:
        """
        Get field definitions for a specific model

        Args:
            model_name: Model name (e.g., 'res.partner')
            attributes: Optional list of field attributes to retrieve

        Returns:
            Dictionary mapping field names to their definitions
        """
        try:
            if attributes:
                fields = self._execute(model_name, "fields_get", attributes=attributes)
            else:
                fields = self._execute(model_name, "fields_get")
            return fields
        except Exception as e:
            logger.error(f"Error retrieving fields: {str(e)}")
            return {"error": str(e)}

    def search_read(
        self,
        model_name: str,
        domain: List = None,
        fields: List[str] = None,
        offset: int = 0,
        limit: int = None,
        order: str = None
    ) -> List[Dict]:
        """
        More robust search_read method with improved XML-RPC compatibility
        
        Args:
            model_name: Model name (e.g., 'res.partner')
            domain: Search domain (e.g., [('is_company', '=', True)])
            fields: List of field names to return (None for all)
            offset: Number of records to skip
            limit: Maximum number of records to return
            order: Sorting criteria (e.g., 'name ASC, id DESC')

        Returns:
            List of dictionaries with the matching records
        """
        try:
            # Normalize domain to ensure proper XML-RPC formatting
            if domain is None:
                domain = []
            
            # Ensure domain is a list of lists
            if len(domain) > 0 and not all(isinstance(item, list) for item in domain if not isinstance(item, str)):
                raise ValueError("Domain must be a list of lists or logical operators")
            
            # Normalize fields to handle None case
            fields = fields or []
            
            kwargs = {}
            if fields:
                kwargs['fields'] = fields
            if offset > 0:
                kwargs['offset'] = int(offset)
            if limit is not None:
                kwargs['limit'] = int(limit)
            if order:
                kwargs['order'] = order
            
            # Call search_read directly
            try:
                records = self._execute(model_name, 'search_read', domain, **kwargs)
                return records
            except Exception as e:
                logger.error(f"Direct search_read error: {e}")
                
                # Fallback to separate search and read
                search_kwargs = {}
                if offset > 0:
                    search_kwargs['offset'] = int(offset)
                if limit is not None:
                    search_kwargs['limit'] = int(limit)
                if order:
                    search_kwargs['order'] = order
                
                record_ids = self._execute(model_name, 'search', domain, **search_kwargs)
                
                # If no records found, return empty list
                if not record_ids:
                    return []
                
                # Read records
                read_kwargs = {}
                if fields:
                    read_kwargs['fields'] = fields
                
                records = self._execute(model_name, 'read', record_ids, **read_kwargs)
                return records
        
        except Exception as e:
            logger.error(f"Search_read error: {e}")
            return []

    def read_records(
        self,
        model_name: str,
        ids: List[int],
        fields: List[str] = None
    ) -> List[Dict]:
        """
        Read data of records by IDs

        Args:
            model_name: Model name (e.g., 'res.partner')
            ids: List of record IDs to read
            fields: List of field names to return (None for all)

        Returns:
            List of dictionaries with the requested records
        """
        try:
            kwargs = {}
            if fields is not None:
                kwargs["fields"] = fields

            result = self._execute(model_name, "read", ids, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Error reading records: {str(e)}")
            return []

    def create_record(self, model_name: str, values: Dict) -> int:
        """
        Create a new record in Odoo

        Args:
            model_name: Model name (e.g., 'res.partner')
            values: Dictionary of field values

        Returns:
            ID of the created record
        """
        try:
            result = self._execute(model_name, "create", values)
            return result
        except Exception as e:
            logger.error(f"Error creating record: {str(e)}")
            raise ValueError(f"Failed to create record: {str(e)}")

    def update_record(self, model_name: str, record_id: int, values: Dict) -> bool:
        """
        Update an existing record in Odoo

        Args:
            model_name: Model name (e.g., 'res.partner')
            record_id: ID of the record to update
            values: Dictionary of field values to update

        Returns:
            True if successful
        """
        try:
            result = self._execute(model_name, "write", [record_id], values)
            return result
        except Exception as e:
            logger.error(f"Error updating record: {str(e)}")
            raise ValueError(f"Failed to update record: {str(e)}")

    def delete_record(self, model_name: str, record_id: int) -> bool:
        """
        Delete a record from Odoo

        Args:
            model_name: Model name (e.g., 'res.partner')
            record_id: ID of the record to delete

        Returns:
            True if successful
        """
        try:
            result = self._execute(model_name, "unlink", [record_id])
            return result
        except Exception as e:
            logger.error(f"Error deleting record: {str(e)}")
            raise ValueError(f"Failed to delete record: {str(e)}")

    def clear_cache(self, model: str = None, method: str = None):
        """
        Clear the client cache, optionally for specific model/method

        Args:
            model: Optional model name to clear cache for
            method: Optional method name to clear cache for
        """
        if not self.cache_enabled:
            return

        if model and method:
            pattern = f"{model}:{method}:"
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._cache[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
        elif model:
            pattern = f"{model}:"
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_remove:
                del self._cache[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

    def invalidate_old_cache(self, max_age: int = None):
        """
        Invalidate cache entries older than max_age seconds

        Args:
            max_age: Maximum age in seconds (default: use instance ttl)
        """
        if not self.cache_enabled:
            return

        current_time = time.time()
        max_age = max_age or self.cache_ttl

        keys_to_remove = []
        for key, timestamp in self._cache_timestamps.items():
            if current_time - timestamp > max_age:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            if key in self._cache:
                del self._cache[key]
            del self._cache_timestamps[key]


class OdooConnect(xmlrpc.client.Transport):

    def __init__(
        self,
        timeout: int = 30,
        use_https: bool = True,
        verify_ssl: bool = True,
        max_redirects: int = 5
    ):
        super().__init__()
        self.timeout = timeout
        self.use_https = use_https
        self.verify_ssl = verify_ssl
        self.max_redirects = max_redirects

        if use_https and not verify_ssl:
            import ssl
            self.context = ssl._create_unverified_context()

    def make_connection(self, host):
        if self.use_https and not self.verify_ssl:
            connection = http.client.HTTPSConnection(
                host, timeout=self.timeout, context=self.context
            )
        else:
            if self.use_https:
                connection = http.client.HTTPSConnection(host, timeout=self.timeout)
            else:
                connection = http.client.HTTPConnection(host, timeout=self.timeout)
        return connection

    def request(self, host, handler, request_body, verbose):
        """Send HTTP request with retry for redirects"""
        redirects = 0
        while redirects < self.max_redirects:
            try:
                return super().request(host, handler, request_body, verbose)
            except xmlrpc.client.ProtocolError as err:
                if err.errcode in (301, 302, 303, 307, 308) and err.headers.get("location"):
                    redirects += 1
                    location = err.headers.get("location")
                    parsed = urllib.parse.urlparse(location)
                    if parsed.netloc:
                        host = parsed.netloc
                    handler = parsed.path
                    if parsed.query:
                        handler += "?" + parsed.query
                else:
                    raise
            except Exception as e:
                logger.error(f"Error during request: {str(e)}")
                raise

        raise xmlrpc.client.ProtocolError(host + handler, 310, "Too many redirects", {})


# Client access through instance manager
def get_odoo_client(instance_name: str = "default") -> OdooClient:
    """
    Get a configured Odoo client instance from the instance manager
    
    Args:
        instance_name: Name of the Odoo instance to connect to
        
    Returns:
        OdooClient: A configured Odoo client instance
    """
    from .core.instance_manager import InstanceManager
    
    # Get the instance manager
    instance_manager = InstanceManager()
    
    # Get the client for this instance
    return instance_manager.get_client(instance_name)


def list_available_instances() -> List[str]:
    """
    List all available Odoo instances
    
    Returns:
        List of instance names
    """
    from .core.instance_manager import InstanceManager
    
    # Get the instance manager
    instance_manager = InstanceManager()
    
    # Refresh and return available instances
    instance_manager.refresh_instances()
    return instance_manager.get_available_instances()
