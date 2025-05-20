"""
Hadoopt Odoo MCP - Multi-Control Panel for Odoo
"""

# Import core modules
from .core.instance_manager import InstanceManager
from .core.config_manager import ConfigManager

# Import main modules
from .odoo_client import OdooClient, get_odoo_client, list_available_instances
from .enhanced_utils import OdooEnhancedUtils

# Import tool registration functions
from .multi_instance import register_multi_instance_tools
from .main_tools import register_main_tools
from .analysis import register_analysis_tools
from .discovery_tools import register_discovery_tools
from .visualization import register_visualization_tools

# Import the server
from .server import mcp, app_lifespan, AppContext

__all__ = [
    # Core classes
    'InstanceManager',
    'ConfigManager',
    
    # Client classes
    'OdooClient',
    'OdooEnhancedUtils',
    'get_odoo_client',
    'list_available_instances',
    
    # Tool registration functions
    'register_multi_instance_tools',
    'register_main_tools',
    'register_analysis_tools',
    'register_discovery_tools',
    'register_visualization_tools',
    
    # Server
    'mcp',
    'app_lifespan',
    'AppContext'
]
