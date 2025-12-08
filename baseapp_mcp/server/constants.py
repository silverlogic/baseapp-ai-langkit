"""
Constants for MCP server configuration.
"""

DEFAULT_MCP_ROUTE_PATH = "mcp"

# Default server instructions - can be overridden via Django settings.MCP_SERVER_INSTRUCTIONS
DEFAULT_SERVER_INSTRUCTIONS = """
This server provides MCP (Model Context Protocol) tools for document search and retrieval.
Register custom tools using the register_tool function or by extending this module.
"""
