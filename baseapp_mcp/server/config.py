from cryptography.fernet import Fernet
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from .constants import DEFAULT_MCP_ROUTE_PATH, DEFAULT_SERVER_INSTRUCTIONS


def get_mcp_route_path() -> str:
    """
    Get the MCP route path, allowing customization via Django settings.

    Returns:
        The MCP route path from settings.MCP_ROUTE_PATH or DEFAULT_MCP_ROUTE_PATH
    """
    from django.conf import settings

    return getattr(settings, "MCP_ROUTE_PATH", DEFAULT_MCP_ROUTE_PATH)


def get_server_instructions() -> str:
    """
    Get the MCP server instructions, allowing customization via Django settings.

    Returns:
        The server instructions from settings.MCP_SERVER_INSTRUCTIONS or DEFAULT_SERVER_INSTRUCTIONS
    """
    from django.conf import settings

    return getattr(settings, "MCP_SERVER_INSTRUCTIONS", None) or DEFAULT_SERVER_INSTRUCTIONS


def get_auth_provider():
    """
    Get the authentication provider, allowing customization via Django settings.

    Supports:
    - settings.MCP_ENABLE_OAUTH = False to disable OAuth (API keys only)

    For custom authentication providers, override DjangoFastMCP.get_auth() in your project.

    Returns:
        Auth provider instance or None if OAuth is disabled
    """
    from django.conf import settings
    from fastmcp.server.auth.providers.google import GoogleProvider

    if getattr(settings, "MCP_ENABLE_OAUTH", True) is False:
        return None

    # Default: GoogleProvider
    return GoogleProvider(
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        base_url=getattr(settings, "MCP_URL", "http://localhost:8001"),
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        jwt_signing_key=settings.MCP_JWT_SIGNING_KEY,
        client_storage=FernetEncryptionWrapper(
            key_value=_get_redis_store(), fernet=Fernet(settings.MCP_STORAGE_ENCRYPTION_KEY)
        ),
    )


def _get_redis_store() -> RedisStore:
    """Creates a RedisStore. Uses REDIS_URL if provided, otherwise falls back to individual settings."""
    from django.conf import settings

    redis_url = getattr(settings, "REDIS_URL", None)
    if redis_url:
        return RedisStore(url=redis_url)

    redis_host = getattr(settings, "REDIS_HOST", "redis")
    redis_port = getattr(settings, "REDIS_PORT", 6379)
    redis_password = getattr(settings, "REDIS_PASSWORD", None)
    return RedisStore(host=redis_host, port=redis_port, password=redis_password)
