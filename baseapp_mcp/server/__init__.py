"""
MCP server components.

This package provides:
- DjangoFastMCP: FastMCP subclass with Django integration
- Helper functions: register_debug_tool(), register_health_check_route(), get_application()
- Lifespan functions: default_lifespan() for server startup/shutdown
- Constants: MCP_ROUTE_PATH, DEFAULT_SERVER_INSTRUCTIONS
"""

from baseapp_mcp.server.config import (
    get_auth_provider,
    get_mcp_route_path,
    get_server_instructions,
)
from baseapp_mcp.server.constants import (
    DEFAULT_MCP_ROUTE_PATH,
    DEFAULT_SERVER_INSTRUCTIONS,
)
from baseapp_mcp.server.django_fastmcp import DjangoFastMCP
from baseapp_mcp.server.helpers import (
    get_application,
    register_debug_tool,
    register_health_check_route,
)
from baseapp_mcp.server.lifespan import default_lifespan

__all__ = [
    "DjangoFastMCP",
    "default_lifespan",
    "register_debug_tool",
    "register_health_check_route",
    "get_application",
    "DEFAULT_MCP_ROUTE_PATH",
    "get_mcp_route_path",
    "DEFAULT_SERVER_INSTRUCTIONS",
    "get_server_instructions",
    "get_auth_provider",
]
