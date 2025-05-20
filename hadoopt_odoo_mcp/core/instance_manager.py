"""
Instance manager for Odoo MCP

Handles multiple Odoo instance connections and context switching
"""

import logging
import time
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

class InstanceManager:
    """Manager for multiple Odoo instance connections"""
    
    def __init__(self, default_instance: str = "default"):
        """
        Initialize the instance manager
        
        Args:
            default_instance: Name of the default instance to use
        """
        self.config_manager = ConfigManager()
        self.connections = {}
        self.utils = {}
        self.active_instance = default_instance
        self.connection_timestamps = {}
        self.connection_validity = 3600  # 1 hour connection validity
        
        # Initialize instances
        self._initialize_instances()
    
    def _initialize_instances(self):
        """Initialize available instances from configuration"""
        # Get list of available instances
        instances = self.config_manager.list_available_instances()
        
        if not instances:
            logger.warning("No Odoo instances found in configuration")
            return
        
        # Set default instance
        default_instance = "default" if "default" in instances else instances[0]
        
        # Store instance names without connecting immediately to reduce startup time
        self._instance_names = instances
        
        # Set active instance
        self.active_instance = default_instance
        
    def _connect_instance(self, instance_name: str) -> bool:
        """
        Establish connection to an Odoo instance
        
        Args:
            instance_name: Name of the instance to connect
            
        Returns:
            True if successfully connected, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from ..odoo_client import OdooClient
            from ..enhanced_utils import OdooEnhancedUtils
            
            # Load configuration
            config = self.config_manager.get_instance_config(instance_name)
            
            # Create client and utils
            client = OdooClient(
                url=config["url"],
                db=config["db"],
                username=config["username"],
                password=config["password"],
                timeout=config.get("timeout", 30),
                verify_ssl=config.get("verify_ssl", True),
                cache_enabled=config.get("cache_enabled", True),
                cache_ttl=config.get("cache_ttl", 300),
            )
            
            utils = OdooEnhancedUtils(client)
            
            # Store connections
            self.connections[instance_name] = client
            self.utils[instance_name] = utils
            self.connection_timestamps[instance_name] = time.time()
            
            logger.info(f"Connected to Odoo instance '{instance_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Odoo instance '{instance_name}': {e}")
            return False
    
    def validate_connection(self, instance_name: str) -> bool:
        """
        Check if a connection is still valid
        
        Args:
            instance_name: Name of the instance to check
            
        Returns:
            True if the connection is valid, False otherwise
        """
        if instance_name not in self.connections:
            return False
        
        # Check connection timestamp
        if instance_name in self.connection_timestamps:
            timestamp = self.connection_timestamps[instance_name]
            if time.time() - timestamp > self.connection_validity:
                logger.info(f"Connection to '{instance_name}' expired, will reconnect")
                return False
        
        # Check connection with a simple call
        try:
            client = self.connections[instance_name]
            client.execute_method('res.users', 'read', [client.uid], ['name'])
            return True
        except Exception as e:
            logger.warning(f"Connection to '{instance_name}' is invalid: {e}")
            return False
    
    def get_client(self, instance_name: Optional[str] = None):
        """
        Get an Odoo client for a specific instance, connecting if necessary
        
        Args:
            instance_name: Name of the instance to get (default: active instance)
            
        Returns:
            OdooClient instance or None if not found
        """
        instance_name = instance_name or self.active_instance
        
        # Connect if not already connected
        if instance_name not in self.connections:
            if not self._connect_instance(instance_name):
                return None
        
        # Validate connection and reconnect if necessary
        if not self.validate_connection(instance_name):
            if not self._connect_instance(instance_name):
                return None
        
        return self.connections.get(instance_name)
    
    def get_utils(self, instance_name: Optional[str] = None):
        """
        Get utils for a specific instance, connecting if necessary
        
        Args:
            instance_name: Name of the instance to get (default: active instance)
            
        Returns:
            OdooEnhancedUtils instance or None if not found
        """
        instance_name = instance_name or self.active_instance
        
        # Ensure client is connected
        if not self.get_client(instance_name):
            return None
        
        return self.utils.get(instance_name)
    
    def get_available_instances(self) -> List[str]:
        """
        Get a list of available instances
        
        Returns:
            List of instance names
        """
        # Refresh available instances
        if not hasattr(self, '_instance_names'):
            self._instance_names = self.config_manager.list_available_instances()
            
        return self._instance_names
    
    def switch_instance(self, instance_name: str) -> bool:
        """
        Switch the active instance
        
        Args:
            instance_name: Name of the instance to switch to
            
        Returns:
            True if successful, False if the instance doesn't exist
        """
        # Check if instance is available
        if instance_name not in self.get_available_instances():
            return False
        
        # Ensure instance is connected
        if not self.get_client(instance_name):
            return False
        
        # Switch active instance
        self.active_instance = instance_name
        return True
    
    def get_instance_info(self, instance_name: Optional[str] = None) -> Dict:
        """
        Get information about a specific instance
        
        Args:
            instance_name: Name of the instance to get info about (default: active instance)
            
        Returns:
            Dictionary with instance information
        """
        instance_name = instance_name or self.active_instance
        client = self.get_client(instance_name)
        
        if not client:
            return {
                "success": False,
                "error": f"Instance '{instance_name}' not available or not connected"
            }
        
        try:
            # Get user info
            user_info = client.execute_method(
                "res.users", "read", [client.uid], ["name", "login", "company_id"]
            )[0]
            
            return {
                "success": True,
                "instance": instance_name,
                "url": client.url,
                "database": client.db,
                "user": {
                    "id": client.uid,
                    "name": user_info.get("name"),
                    "login": user_info.get("login"),
                    "company_id": user_info.get("company_id")
                },
                "connection_age": time.time() - self.connection_timestamps.get(instance_name, 0) if instance_name in self.connection_timestamps else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "instance": instance_name
            }
    
    def add_instance(self, instance_name: str, url: str, db: str, 
                    username: str, password: str, **kwargs) -> bool:
        """
        Add a new instance configuration and connect to it
        
        Args:
            instance_name: Name for the new instance
            url: Odoo server URL
            db: Database name
            username: Username for authentication
            password: Password for authentication
            **kwargs: Additional configuration parameters
            
        Returns:
            True if successful, False otherwise
        """
        # Check if instance already exists
        if instance_name in self.get_available_instances():
            logger.warning(f"Instance '{instance_name}' already exists")
            return False
        
        # Create configuration
        config = {
            "url": url,
            "db": db,
            "username": username,
            "password": password,
            **kwargs
        }
        
        # Save configuration
        if not self.config_manager.add_instance_config(instance_name, config):
            logger.error(f"Failed to save configuration for instance '{instance_name}'")
            return False
        
        # Add to available instances
        if not hasattr(self, '_instance_names'):
            self._instance_names = []
        if instance_name not in self._instance_names:
            self._instance_names.append(instance_name)
            self._instance_names.sort()
        
        # Connect to instance
        return self._connect_instance(instance_name)
    
    def remove_instance(self, instance_name: str) -> bool:
        """
        Remove an instance configuration
        
        Args:
            instance_name: Name of the instance to remove
            
        Returns:
            True if successful, False otherwise
        """
        # Check if instance exists
        if instance_name not in self.get_available_instances():
            logger.warning(f"Instance '{instance_name}' does not exist")
            return False
        
        # Check if it's the active instance
        if instance_name == self.active_instance:
            logger.warning(f"Cannot remove active instance '{instance_name}'")
            return False
        
        # Remove from connections
        if instance_name in self.connections:
            del self.connections[instance_name]
        
        # Remove from utils
        if instance_name in self.utils:
            del self.utils[instance_name]
        
        # Remove from timestamps
        if instance_name in self.connection_timestamps:
            del self.connection_timestamps[instance_name]
        
        # Remove from available instances
        if hasattr(self, '_instance_names') and instance_name in self._instance_names:
            self._instance_names.remove(instance_name)
        
        # Remove configuration
        return self.config_manager.remove_instance_config(instance_name)
    
    @contextmanager
    def instance_context(self, instance_name: str):
        """
        Context manager for temporarily switching instances
        
        Args:
            instance_name: Name of the instance to use
            
        Yields:
            The client for the specified instance
        """
        previous_instance = self.active_instance
        
        try:
            # Switch to requested instance
            if not self.switch_instance(instance_name):
                raise ValueError(f"Failed to switch to instance '{instance_name}'")
            
            # Get client
            client = self.get_client(instance_name)
            if not client:
                raise ValueError(f"Failed to get client for instance '{instance_name}'")
            
            yield client
        finally:
            # Switch back to previous instance
            self.active_instance = previous_instance
    
    def refresh_instances(self):
        """Refresh the list of available instances"""
        self._instance_names = self.config_manager.list_available_instances()
        
        # Remove connections for instances that no longer exist
        for instance_name in list(self.connections.keys()):
            if instance_name not in self._instance_names:
                if instance_name in self.connections:
                    del self.connections[instance_name]
                if instance_name in self.utils:
                    del self.utils[instance_name]
                if instance_name in self.connection_timestamps:
                    del self.connection_timestamps[instance_name]
        
        # If active instance no longer exists, switch to a valid one
        if self.active_instance not in self._instance_names and self._instance_names:
            self.active_instance = self._instance_names[0]
    
    def disconnect_instance(self, instance_name: str) -> bool:
        """
        Disconnect from an instance
        
        Args:
            instance_name: Name of the instance to disconnect
            
        Returns:
            True if successful, False otherwise
        """
        if instance_name not in self.connections:
            return False
        
        # Remove connections
        del self.connections[instance_name]
        if instance_name in self.utils:
            del self.utils[instance_name]
        if instance_name in self.connection_timestamps:
            del self.connection_timestamps[instance_name]
        
        return True
    
    def disconnect_all(self):
        """Disconnect from all instances"""
        self.connections.clear()
        self.utils.clear()
        self.connection_timestamps.clear()
