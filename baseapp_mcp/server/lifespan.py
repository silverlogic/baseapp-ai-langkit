"""
Lifespan functions for MCP server startup and shutdown.
"""

import logging
import typing as typ
from contextlib import asynccontextmanager

from fastmcp import FastMCP

logger = logging.getLogger(__name__)


@asynccontextmanager
async def default_lifespan(mcp_server: FastMCP) -> typ.AsyncIterator[typ.Any]:
    """
    Default lifespan function for MCP server.

    Provides basic startup and shutdown logging. Projects can create their own
    lifespan function to add custom startup/cleanup tasks (e.g., database connections,
    cache initialization, etc.).

    Args:
        mcp_server: The FastMCP server instance

    Yields:
        Dictionary with startup information
    """
    try:
        logger.info("✅ MCP Server startup complete")

        # Yield control back to the server
        # The value yielded is available in the lifespan context
        yield {"startup_time": "server_ready"}

    finally:
        logger.info("🔄 MCP Server shutting down...")
        logger.info("✅ MCP Server shutdown complete")
