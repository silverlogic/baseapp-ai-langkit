import logging
import typing as typ
from functools import partial

import anyio
import uvicorn
from django.conf import settings
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.cli import log_server_banner
from starlette.middleware import Middleware as ASGIMiddleware

from baseapp_mcp.extensions.fastmcp.server.http import create_streamable_http_app
from baseapp_mcp.server.config import (
    get_auth_provider,
    get_mcp_route_path,
    get_server_instructions,
)
from baseapp_mcp.server.lifespan import default_lifespan

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
            streamable_http_path=path or self._deprecated_settings.streamable_http_path,
            event_store=None,
            auth=self.auth,
            json_response=(
                json_response
                if json_response is not None
                else self._deprecated_settings.json_response
            ),
            stateless_http=(
                stateless_http
                if stateless_http is not None
                else self._deprecated_settings.stateless_http
            ),
            debug=self._deprecated_settings.debug,
            middleware=middleware,
        )

    async def run_streamable_http_async(
        self,
        show_banner: bool = True,
        host: str | None = None,
        port: int | None = None,
        log_level: str | None = None,
        path: str | None = None,
        uvicorn_config: dict[str, typ.Any] | None = None,
        middleware: list[ASGIMiddleware] | None = None,
    ) -> None:
        """
        Run the server using Streamable-HTTP transport.

        Args:
            show_banner: Whether to display the server banner
            host: Host address to bind to (defaults to settings.host)
            port: Port to bind to (defaults to settings.port)
            log_level: Log level for the server (defaults to settings.log_level)
            path: Path for the endpoint (defaults to settings.streamable_http_path or settings.sse_path)
            uvicorn_config: Additional configuration for the Uvicorn server
            middleware: A list of middleware to apply to the app
        """
        host = host or self._deprecated_settings.host
        port = port or self._deprecated_settings.port
        default_log_level_to_use = (log_level or self._deprecated_settings.log_level).lower()
        transport = "streamable-http"

        mcp_route_path = get_mcp_route_path()
        app = self.streamable_http_app(
            path=f"/{mcp_route_path}", stateless_http=True, middleware=middleware
        )

        # Get the path for the server URL
        server_path = (
            app.state.path.lstrip("/")
            if hasattr(app, "state") and hasattr(app.state, "path")
            else path or ""
        )

        # Display server banner
        if show_banner:
            log_server_banner(
                server=self,
                transport=transport,
                host=host,
                port=port,
                path=server_path,
            )

        _uvicorn_config_from_user = uvicorn_config or {}

        config_kwargs: dict[str, typ.Any] = {
            "timeout_graceful_shutdown": 0,
            "lifespan": "on",
        }
        config_kwargs.update(_uvicorn_config_from_user)

        if "log_config" not in config_kwargs and "log_level" not in config_kwargs:
            config_kwargs["log_level"] = default_log_level_to_use

        config = uvicorn.Config(app, host=host, port=port, **config_kwargs)
        server = uvicorn.Server(config)
        path = app.state.path.lstrip("/")  # type: ignore
        logger.info(
            f"Starting MCP server {self.name!r} with transport {transport!r} on http://{host}:{port}/{path}"
        )

        await server.serve()

    def run_streamable_http(
        self,
        show_banner: bool = True,
        **transport_kwargs: typ.Any,
    ) -> None:
        """
        Run the FastMCP server synchronously.

        This is a convenience wrapper around run_streamable_http_async that uses anyio.run().

        Args:
            show_banner: Whether to display the server banner
            **transport_kwargs: Additional arguments passed to run_streamable_http_async
        """
        anyio.run(
            partial(
                self.run_streamable_http_async,
                show_banner=show_banner,
                **transport_kwargs,
            )
        )

    @classmethod
    def create(
        cls,
        name: str | None = None,
        instructions: str | None = None,
        lifespan: typ.Callable | None = None,
        auth: AuthProvider | None = None,
        debug: bool | None = None,
    ) -> "DjangoFastMCP":
        """
        Create and configure an MCP server instance.

        Args:
            name: Server name (defaults to settings.APPLICATION_NAME + " MCP")
            instructions: Server instructions (defaults to get_server_instructions())
            lifespan: Custom lifespan function (defaults to default_lifespan)
            auth: Auth provider (defaults to cls.get_auth() which can be customized)
            debug: Debug mode (defaults to settings.DEBUG)

        Returns:
            Configured DjangoFastMCP instance
        """
        name = name or f"{settings.APPLICATION_NAME} MCP"
        # Allow project-specific instructions via Django settings
        if instructions is None:
            instructions = get_server_instructions()
        lifespan = lifespan or default_lifespan
        debug = debug if debug is not None else settings.DEBUG

        # Use provided auth, or get from get_auth() method (which can be overridden)
        if auth is None:
            auth = cls.get_auth()

        return cls(
            name=name,
            lifespan=lifespan,
            instructions=instructions,
            auth=auth,
            debug=debug,
        )
