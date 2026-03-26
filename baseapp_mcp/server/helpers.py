"""
Helper functions for MCP server setup and configuration.
"""

from typing import TYPE_CHECKING

import django
from django.conf import settings
from fastmcp.server.http import StarletteWithLifespan
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from baseapp_mcp.middleware.rate_limiting import UserRateLimitMiddleware
from baseapp_mcp.server.config import get_mcp_route_path

if TYPE_CHECKING:
    from baseapp_mcp.server.django_fastmcp import DjangoFastMCP


def register_health_check_route(mcp_server: "DjangoFastMCP", route_path: str | None = None) -> None:
    """
    Register a health check route on the MCP server.

    Args:
        mcp_server: The MCP server instance to register the route on
        route_path: Optional custom path (defaults to /{MCP_ROUTE_PATH}/health)
    """
    mcp_route_path = get_mcp_route_path()
    path = route_path or f"/{mcp_route_path}/health"

    @mcp_server.custom_route(path, methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse(dict(status="Running"), status_code=200)


def get_application(
    mcp_server: "DjangoFastMCP", stateless_http: bool = True
) -> StarletteWithLifespan:
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

    mcp_route_path = get_mcp_route_path()
    return mcp_server.streamable_http_app(
        path=f"/{mcp_route_path}",
        stateless_http=stateless_http,
        middleware=middleware,
    )
