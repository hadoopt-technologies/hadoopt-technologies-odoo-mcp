"""
Configuration manager for Odoo MCP

Handles loading and validation of instance configurations
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manager for Odoo instance configurations"""
    
    def __init__(self, config_dirs=None):
        """
        Initialize the configuration manager
        
        Args:
            config_dirs: Optional list of directories to look for configuration files
        """
        self.config_dirs = config_dirs or [
            "config",
            "hadoopt_odoo_mcp/config",
            os.path.expanduser("~/config")
        ]
        
    def load_config(self, instance_name: str = "default") -> Dict[str, Any]:
        """
        Load configuration for a specific instance
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            Configuration dictionary
        """
        # 1. Check for instance-specific environment variables
        env_prefix = instance_name.upper()
        if all(
            var in os.environ
            for var in [f"{env_prefix}_ODOO_URL", f"{env_prefix}_ODOO_DB", 
                        f"{env_prefix}_ODOO_USERNAME", f"{env_prefix}_ODOO_PASSWORD"]
        ):
            return {
                "url": os.environ[f"{env_prefix}_ODOO_URL"],
                "db": os.environ[f"{env_prefix}_ODOO_DB"],
                "username": os.environ[f"{env_prefix}_ODOO_USERNAME"],
                "password": os.environ[f"{env_prefix}_ODOO_PASSWORD"],
                "timeout": int(os.environ.get(f"{env_prefix}_ODOO_TIMEOUT", "30")),
                "verify_ssl": os.environ.get(f"{env_prefix}_ODOO_VERIFY_SSL", "1").lower() in ["1", "true", "yes"],
                "cache_enabled": os.environ.get(f"{env_prefix}_ODOO_CACHE_ENABLED", "1").lower() in ["1", "true", "yes"],
                "cache_ttl": int(os.environ.get(f"{env_prefix}_ODOO_CACHE_TTL", "300")),
            }
        
        # 2. Check for generic environment variables for default instance
        if all(
            var in os.environ
            for var in ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]
        ) and instance_name == "default":
            return {
                "url": os.environ["ODOO_URL"],
                "db": os.environ["ODOO_DB"],
                "username": os.environ["ODOO_USERNAME"],
                "password": os.environ["ODOO_PASSWORD"],
                "timeout": int(os.environ.get("ODOO_TIMEOUT", "30")),
                "verify_ssl": os.environ.get("ODOO_VERIFY_SSL", "1").lower() in ["1", "true", "yes"],
                "cache_enabled": os.environ.get("ODOO_CACHE_ENABLED", "1").lower() in ["1", "true", "yes"],
                "cache_ttl": int(os.environ.get("ODOO_CACHE_TTL", "300")),
            }

        # 3. Try to load from configuration files
        config_paths = []
        
        # Define config file paths to check
        for config_dir in self.config_dirs:
            config_paths.append(os.path.join(config_dir, f"{instance_name}.json"))
            
        # Add backward compatibility with old config.json
        if instance_name == "default":
            for config_dir in self.config_dirs:
                config_paths.append(os.path.join(config_dir, "config.json"))

        # Try to load from file
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        config = json.load(f)
                        # Add defaults for optional settings
                        if "timeout" not in config:
                            config["timeout"] = 30
                        if "verify_ssl" not in config:
                            config["verify_ssl"] = True
                        if "cache_enabled" not in config:
                            config["cache_enabled"] = True
                        if "cache_ttl" not in config:
                            config["cache_ttl"] = 300
                        return config
                except Exception as e:
                    logger.error(f"Error loading config from {path}: {e}")
                    # Continue to try other paths

        # 4. If no config found for specific instance and it's not default,
        # try to load default config
        if instance_name != "default":
            try:
                return self.load_config("default")
            except FileNotFoundError:
                pass

        raise FileNotFoundError(
            f"No Odoo configuration found for instance '{instance_name}'. "
            f"Please create a config/{instance_name}.json file or set environment variables."
        )
    
    def list_available_instances(self) -> List[str]:
        """
        List all available Odoo instances based on configuration files and environment variables
        
        Returns:
            List of instance names
        """
        instances = []
        
        # Check config directories
        for config_dir in self.config_dirs:
            if os.path.exists(config_dir) and os.path.isdir(config_dir):
                for filename in os.listdir(config_dir):
                    if filename.endswith(".json"):
                        instance_name = filename[:-5]  # Remove .json extension
                        if instance_name not in instances:
                            instances.append(instance_name)
        
        # Check for environment variables
        for key in os.environ:
            if key.endswith("_ODOO_URL"):
                instance = key[:-9]  # Remove _ODOO_URL suffix
                if instance and instance not in instances:
                    # Check if all required variables are present
                    if all(var in os.environ for var in 
                           [f"{instance}_ODOO_DB", 
                            f"{instance}_ODOO_USERNAME", 
                            f"{instance}_ODOO_PASSWORD"]):
                        instances.append(instance.lower())
        
        # Check for default config if not already added
        if "default" not in instances:
            for config_path in [
                os.path.join(config_dir, "config.json") 
                for config_dir in self.config_dirs
            ]:
                if os.path.exists(config_path):
                    instances.append("default")
                    break
        
        return sorted(instances)
    
    def get_instance_config(self, instance_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific instance
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            Configuration dictionary
        """
        return self.load_config(instance_name)
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate a configuration dictionary
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_keys = ["url", "db", "username", "password"]
        return all(key in config for key in required_keys)
    
    def add_instance_config(self, instance_name: str, config: Dict[str, Any]) -> bool:
        """
        Add a new instance configuration
        
        Args:
            instance_name: Name of the instance
            config: Configuration dictionary
            
        Returns:
            True if successful, False otherwise
        """
        # Validate configuration
        if not self.validate_config(config):
            return False
        
        # Add defaults
        if "timeout" not in config:
            config["timeout"] = 30
        if "verify_ssl" not in config:
            config["verify_ssl"] = True
        if "cache_enabled" not in config:
            config["cache_enabled"] = True
        if "cache_ttl" not in config:
            config["cache_ttl"] = 300
        
        # Use the first available config directory
        for config_dir in self.config_dirs:
            if os.path.exists(config_dir) and os.path.isdir(config_dir):
                config_path = os.path.join(config_dir, f"{instance_name}.json")
                try:
                    with open(config_path, "w") as f:
                        json.dump(config, f, indent=2)
                    return True
                except Exception as e:
                    logger.error(f"Error saving config to {config_path}: {e}")
                    return False
        
        # If no config directory exists, create the first one
        os.makedirs(self.config_dirs[0], exist_ok=True)
        config_path = os.path.join(self.config_dirs[0], f"{instance_name}.json")
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving config to {config_path}: {e}")
            return False
    
    def remove_instance_config(self, instance_name: str) -> bool:
        """
        Remove an instance configuration
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            True if successful, False otherwise
        """
        # Don't allow removing default
        if instance_name == "default":
            return False
        
        # Check if configuration exists in any of the directories
        for config_dir in self.config_dirs:
            config_path = os.path.join(config_dir, f"{instance_name}.json")
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                    return True
                except Exception as e:
                    logger.error(f"Error removing config {config_path}: {e}")
                    return False
        
        return False
