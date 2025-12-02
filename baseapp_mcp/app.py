import logging
import typing as typ
from contextlib import asynccontextmanager
from functools import partial

import anyio
import django
import uvicorn
from django.conf import settings
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.utilities.cli import log_server_banner
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from baseapp_mcp.extensions.fastmcp.server.http import create_streamable_http_app
from baseapp_mcp.middleware.rate_limiting import UserRateLimitMiddleware
from baseapp_mcp.utils import sanitize_sensitive_dict

MCP_ROUTE_PATH = "mcp"

logger = logging.getLogger(__name__)

# Default server instructions - can be overridden via Django settings.MCP_SERVER_INSTRUCTIONS
DEFAULT_SERVER_INSTRUCTIONS = """
This server provides MCP (Model Context Protocol) tools for document search and retrieval.
Register custom tools using the register_tool function or by extending this module.
"""


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
        logger.info("🚀 MCP Server starting up...")
        logger.info("✅ MCP Server startup complete")

        # Yield control back to the server
        # The value yielded is available in the lifespan context
        yield {"startup_time": "server_ready"}

    finally:
        logger.info("🔄 MCP Server shutting down...")
        logger.info("✅ MCP Server shutdown complete")


class DjangoFastMCP(FastMCP):
    def streamable_http_app(
        self,
        path: str | None = None,
        middleware: list[ASGIMiddleware] | None = None,
        json_response: bool | None = None,
        stateless_http: bool | None = None,
    ) -> StarletteWithLifespan:
        """
        Custom app initializer with APIKey Authentication middleware enabled
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
        """Run the server using Streamable-HTTP transport.

        Args:
            host: Host address to bind to (defaults to settings.host)
            port: Port to bind to (defaults to settings.port)
            log_level: Log level for the server (defaults to settings.log_level)
            path: Path for the endpoint (defaults to settings.streamable_http_path or settings.sse_path)
            uvicorn_config: Additional configuration for the Uvicorn server
            middleware: A list of middleware to apply to the app
            stateless_http: Whether to use stateless HTTP (defaults to settings.stateless_http)
        """

        host = host or self._deprecated_settings.host
        port = port or self._deprecated_settings.port
        default_log_level_to_use = (log_level or self._deprecated_settings.log_level).lower()
        transport = "streamable-http"

        app = self.streamable_http_app(
            path=f"/{MCP_ROUTE_PATH}", stateless_http=True, middleware=middleware
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
        Run the FastMCP server. Note this is a synchronous function.
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
        auth: GoogleProvider | None = None,
        debug: bool | None = None,
    ) -> "DjangoFastMCP":
        """
        Create and configure an MCP server instance.

        Args:
            name: Server name (defaults to settings.APPLICATION_NAME + " MCP")
            instructions: Server instructions (defaults to settings.MCP_SERVER_INSTRUCTIONS or DEFAULT_SERVER_INSTRUCTIONS)
            lifespan: Custom lifespan function (defaults to default_lifespan)
            auth: Auth provider (defaults to GoogleProvider with settings)
            debug: Debug mode (defaults to settings.DEBUG)

        Returns:
            Configured DjangoFastMCP instance
        """
        name = name or f"{settings.APPLICATION_NAME} MCP"
        # Allow project-specific instructions via Django settings
        if instructions is None:
            instructions = (
                getattr(settings, "MCP_SERVER_INSTRUCTIONS", None) or DEFAULT_SERVER_INSTRUCTIONS
            )
        lifespan = lifespan or default_lifespan
        debug = debug if debug is not None else settings.DEBUG

        if auth is None:
            auth = GoogleProvider(
                client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
                base_url=settings.MCP_URL,
                required_scopes=[
                    "openid",
                    "https://www.googleapis.com/auth/userinfo.email",
                ],
            )

        return cls(
            name=name,
            lifespan=lifespan,
            instructions=instructions,
            auth=auth,
            debug=debug,
        )


def register_debug_tool(mcp_server: DjangoFastMCP) -> None:
    """
    Register a debug tool that returns user info (only useful in DEBUG mode).

    Args:
        mcp_server: The MCP server instance to register the tool on
    """
    if not settings.DEBUG:
        return

    @mcp_server.tool
    async def get_user_info() -> dict:
        """Returns information about the authenticated Google user."""
        from fastmcp.server.dependencies import get_access_token

        sensitive_keys = {
            "access_token",
            "refresh_token",
            "id_token",
            "token",
            "secret",
            "password",
            "private_key",
            "api_key",
            "client_secret",
            "auth_token",
            "session_token",
            "bearer_token",
        }
        token = get_access_token()
        return sanitize_sensitive_dict(data=token.claims, sensitive_keys=sensitive_keys)


def register_health_check_route(mcp_server: DjangoFastMCP, route_path: str | None = None) -> None:
    """
    Register a health check route on the MCP server.

    Args:
        mcp_server: The MCP server instance to register the route on
        route_path: Optional custom path (defaults to /{MCP_ROUTE_PATH}/health)
    """
    path = route_path or f"/{MCP_ROUTE_PATH}/health"

    @mcp_server.custom_route(path, methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse(dict(status="Running"), status_code=200)


def get_application(mcp_server: DjangoFastMCP) -> StarletteWithLifespan:
    """
    Get the MCP application instance with middleware configured.

    This function can be called to get the ASGI application for use with
    gunicorn/uvicorn workers.

    Args:
        mcp_server: The MCP server instance to create the application from

    Returns:
        Starlette application with MCP server configured
    """
    if not django.apps.apps.ready:
        django.setup(set_prefix=False)

    middleware = (
        [
            ASGIMiddleware(
                UserRateLimitMiddleware,
                calls=settings.MCP_GENERAL_RATE_LIMIT_CALLS,
                period=settings.MCP_GENERAL_RATE_LIMIT_PERIOD,
            )
        ]
        if settings.MCP_ENABLE_GENERAL_RATE_LIMITING
        else []
    )

    return mcp_server.streamable_http_app(
        path=f"/{MCP_ROUTE_PATH}",
        stateless_http=True,
        middleware=middleware,
    )
