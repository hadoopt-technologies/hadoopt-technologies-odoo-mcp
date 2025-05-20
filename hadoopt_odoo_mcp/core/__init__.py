"""
Core module for Odoo MCP client
"""
from .instance_manager import InstanceManager
from .config_manager import ConfigManager

__all__ = ['InstanceManager', 'ConfigManager']
