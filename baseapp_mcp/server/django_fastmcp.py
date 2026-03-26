import logging
import typing as typ
from typing import TYPE_CHECKING

import fastmcp
from django.conf import settings
from django.utils.module_loading import import_string
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.event_store import EventStore
from fastmcp.server.http import StarletteWithLifespan
from starlette.middleware import Middleware as ASGIMiddleware

from baseapp_ai_langkit import app_settings
from baseapp_mcp.extensions.fastmcp.server.http import create_streamable_http_app
from baseapp_mcp.server.config import get_auth_provider, get_server_instructions
from baseapp_mcp.server.lifespan import default_lifespan

if TYPE_CHECKING:
    from baseapp_mcp.tools.base_mcp_tool import BaseMCPTool

logger = logging.getLogger(__name__)


class DjangoFastMCP(FastMCP):
    """
    FastMCP subclass with Django-specific integrations.

    Provides:
    - Custom streamable HTTP app with API key authentication
    - Async and sync server running methods
    - Django settings integration via create() classmethod
    - Customizable authentication via get_auth() method
    """

    @classmethod
    def get_auth(cls) -> AuthProvider | None:
        """
        Get the authentication provider for this server.

        This method can be overridden in subclasses to provide custom authentication.
        By default, it uses get_auth_provider() which reads from Django settings.

        Returns:
            Auth provider instance or None to disable OAuth (API keys only)
        """
        return get_auth_provider()

    def streamable_http_app(
        self,
        path: str | None = None,
        middleware: list[ASGIMiddleware] | None = None,
        json_response: bool | None = None,
        stateless_http: bool | None = None,
        event_store: EventStore | None = None,
        retry_interval: int | None = None,
    ) -> StarletteWithLifespan:
        """
        Custom app initializer with APIKey Authentication middleware enabled.

        Args:
            path: Path for the endpoint
            middleware: Additional middleware to apply
            json_response: Whether to return JSON responses
            stateless_http: Whether to use stateless HTTP

        Returns:
            Starlette application with MCP server configured
        """

        return create_streamable_http_app(
            server=self,
            streamable_http_path=path or fastmcp.settings.streamable_http_path,
            event_store=event_store,
            retry_interval=retry_interval,
            auth=self.auth,
            json_response=(
                json_response if json_response is not None else fastmcp.settings.json_response
            ),
            stateless_http=(
                stateless_http if stateless_http is not None else fastmcp.settings.stateless_http
            ),
            debug=fastmcp.settings.debug,
            middleware=middleware,
        )

    def http_app(
        self: FastMCP,
        path: str | None = None,
        middleware: list[ASGIMiddleware] | None = None,
        json_response: bool | None = None,
        stateless_http: bool | None = None,
        transport: typ.Literal["http", "streamable-http", "sse"] = "http",
        event_store: EventStore | None = None,
        retry_interval: int | None = None,
    ) -> StarletteWithLifespan:
        if transport in ("streamable-http", "http"):
            return self.streamable_http_app(
                path=path,
                middleware=middleware,
                json_response=json_response,
                stateless_http=stateless_http,
                event_store=event_store,
                retry_interval=retry_interval,
            )
        return super().http_app(
            path=path,
            middleware=middleware,
            json_response=json_response,
            stateless_http=stateless_http,
            transport=transport,
            event_store=event_store,
            retry_interval=retry_interval,
        )

    def register_tool(self, mcp_tool: type["BaseMCPTool"]) -> None:
        """
        Register a tool with the MCP server.

        Args:
            mcp_tool: The MCP tool class to register (subclass of BaseMCPTool)
        """
        self.tool(
            mcp_tool.get_fastmcp_tool_func(),
            annotations=mcp_tool.annotations,
            auth=mcp_tool.get_auth(),
        )

    @classmethod
    def create(
        cls,
        name: str | None = None,
        instructions: str | None = None,
        lifespan: typ.Callable | None = None,
        auth: AuthProvider | None = None,
    ) -> "DjangoFastMCP":
        """
        Create and configure an MCP server instance.

        Args:
            name: Server name (defaults to settings.APPLICATION_NAME + " MCP")
            instructions: Server instructions (defaults to get_server_instructions())
            lifespan: Custom lifespan function (defaults to default_lifespan)
            auth: Auth provider (defaults to cls.get_auth() which can be customized)

        Returns:
            Configured DjangoFastMCP instance
        """
        name = name or f"{settings.APPLICATION_NAME} MCP"
        # Allow project-specific instructions via Django settings
        if instructions is None:
            instructions = get_server_instructions()
        lifespan = lifespan or default_lifespan

        # Use provided auth, or get from get_auth() method (which can be overridden)
        if auth is None:
            auth = cls.get_auth()

        mcp = cls(name=name, instructions=instructions, auth=auth, lifespan=lifespan)
        mcp.register_tools_from_django_settings()
        return mcp

    def register_tools_from_django_settings(self):
        logger.info("Registering MCP tools from Django settings...")

        tool_import_strings = app_settings.MCP_TOOLS
        debug_tool_import_strings = app_settings.DEBUG_MCP_TOOLS

        if settings.DEBUG:
            tool_import_strings = [
                *tool_import_strings,
                *debug_tool_import_strings,
            ]

        for tool_import_string in tool_import_strings:
            ToolClass = import_string(tool_import_string)
            self.register_tool(ToolClass)
            logger.info(f"\tRegistered tool: {tool_import_string}")
