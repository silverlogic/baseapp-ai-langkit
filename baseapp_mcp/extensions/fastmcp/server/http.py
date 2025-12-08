from __future__ import annotations

import typing as typ
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from django.conf import settings
from fastmcp.server.auth import AuthProvider
from fastmcp.server.http import (
    StarletteWithLifespan,
    StreamableHTTPASGIApp,
    StreamableHTTPSessionManager,
    create_base_app,
)
from fastmcp.utilities.logging import get_logger
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from mcp.server.auth.provider import TokenVerifier as TokenVerifierProtocol
from mcp.server.lowlevel.server import LifespanResultT
from mcp.server.streamable_http import EventStore
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import BaseRoute, Route

from baseapp_mcp.auth.middleware.api_key_auth import (
    APIKeyAuthBackend,
    RequireAPIKeyMiddleware,
    RequireAPIKeyOrAuthMiddleware,
)
from baseapp_mcp.extensions.starlette.middleware.authentication import (
    MultipleAuthenticationMiddleware,
)

if typ.TYPE_CHECKING:
    from fastmcp.server.server import FastMCP

logger = get_logger(__name__)


def create_streamable_http_app(
    server: FastMCP[LifespanResultT],
    streamable_http_path: str,
    event_store: EventStore | None = None,
    auth: AuthProvider | None = None,
    json_response: bool = False,
    stateless_http: bool = False,
    debug: bool = False,
    routes: list[BaseRoute] | None = None,
    middleware: list[Middleware] | None = None,
) -> StarletteWithLifespan:
    """Return an instance of the StreamableHTTP server app with APIKey Authentication middleware enabled

    Args:
        server: The FastMCP server instance
        streamable_http_path: Path for StreamableHTTP connections
        event_store: Optional event store for session management
        json_response: Whether to use JSON response format
        stateless_http: Whether to use stateless mode (new transport per request)
        debug: Whether to enable debug mode
        routes: Optional list of custom routes
        middleware: Optional list of middleware

    Returns:
        A Starlette application with StreamableHTTP support
    """
    server_routes: list[BaseRoute] = []
    server_middleware: list[Middleware] = []

    # Create session manager using the provided event store
    session_manager = StreamableHTTPSessionManager(
        app=server._mcp_server,
        event_store=event_store,
        json_response=json_response,
        stateless=stateless_http,
    )

    # Create the ASGI app wrapper
    streamable_http_app = StreamableHTTPASGIApp(session_manager)

    auth_middleware = [
        # APIKey
        Middleware(
            MultipleAuthenticationMiddleware,
            backend=APIKeyAuthBackend(),
        ),
    ]

    # Get auth routes and scopes
    auth_routes = []
    required_scopes = []
    resource_metadata_url = None
    server_require_auth_middleware = RequireAPIKeyMiddleware(
        streamable_http_app, required_scopes, resource_metadata_url
    )

    if auth:
        # OAuth
        auth_middleware.append(
            Middleware(
                MultipleAuthenticationMiddleware,
                backend=BearerAuthBackend(typ.cast(TokenVerifierProtocol, auth)),
            )
        )

        # Get auth routes and scopes
        auth_routes = auth.get_routes()
        required_scopes = getattr(auth, "required_scopes", None) or []
        # Get resource metadata URL for WWW-Authenticate header
        resource_metadata_url = auth.get_resource_metadata_url()
        # Get email regex rules from settings, with default empty list (no email validation)
        email_regex_rules = getattr(settings, "MCP_EMAIL_REGEX_RULES", [])
        server_require_auth_middleware = RequireAPIKeyOrAuthMiddleware(
            app=streamable_http_app,
            email_regex_rules=email_regex_rules,
            required_scopes=required_scopes,
            resource_metadata_url=resource_metadata_url,
        )

    auth_middleware.append(Middleware(AuthContextMiddleware))

    server_routes.extend(auth_routes)
    server_middleware.extend(auth_middleware)

    # Auth is enabled, wrap endpoint with RequireAuthMiddleware
    server_routes.append(Route(streamable_http_path, endpoint=server_require_auth_middleware))

    # Add custom routes with lowest precedence
    if routes:
        server_routes.extend(routes)
    server_routes.extend(server._additional_http_routes)

    # Add middleware
    if middleware:
        server_middleware.extend(middleware)

    # Create a lifespan manager to start and stop the session manager
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        async with session_manager.run():
            yield

    # Create and return the app with lifespan
    app = create_base_app(
        routes=server_routes,
        middleware=server_middleware,
        debug=debug,
        lifespan=lifespan,
    )
    # Store the FastMCP server instance on the Starlette app state
    app.state.fastmcp_server = server

    app.state.path = streamable_http_path

    return app
