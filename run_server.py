#!/usr/bin/env python
"""
Standalone script to run the Odoo MCP server with enhanced features
"""
import sys
import os
import logging
import anyio

from mcp.server.stdio import stdio_server
from hadoopt_odoo_mcp.server import mcp
from hadoopt_odoo_mcp.startup_tools import initialize_server

logger = logging.getLogger(__name__)


def main() -> int:
    """
    Run the Odoo MCP server
    """
    try:
        # Initialize server with optimized settings
        server_info = initialize_server(
            optimize_resources=True,
            auto_setup_logging=True
        )
        
        # Print Python version for debugging purposes
        logger.info(f"Python version: {sys.version}")
        
        # Log environment variables related to Odoo (hiding password)
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith("ODOO_"):
                if key == "ODOO_PASSWORD":
                    logger.info(f"  {key}: ***hidden***")
                else:
                    logger.info(f"  {key}: {value}")

        # Run server in stdio mode
        async def arun():
            logger.info("Starting Odoo MCP server with stdio transport...")
            async with stdio_server() as streams:
                logger.info("Stdio server initialized, running MCP server...")
                await mcp._mcp_server.run(
                    streams[0], streams[1], mcp._mcp_server.create_initialization_options()
                )
        
        # Run server
        anyio.run(arun)
        logger.info("Odoo MCP server stopped normally")
        return 0
    except KeyboardInterrupt:
        logger.info("Odoo MCP server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error starting server: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())