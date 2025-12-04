import json
import re
import typing as typ

from django.conf import settings
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from pydantic import AnyHttpUrl
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from baseapp_mcp.auth.provider import (
    APIKeyVerifier,
    APIKeyVerifierProtocol,
    BaseAPIKeyVerifier,
)


class AuthenticatedAPIKeyUser(AuthenticatedUser):
    """User authenticated with API key."""

    pass


class BaseAPIKeyAuthBackend(AuthenticationBackend):
    """
    Authentication backend that validates API keys from request headers.

    Similar to BearerAuthBackend but looks for API keys in a configurable header
    instead of the Authorization header with Bearer token.
    """

    api_key_verifier: BaseAPIKeyVerifier

    def __init__(
        self,
        api_key_verifier: BaseAPIKeyVerifier,
    ):
        """
        Initialize the API key authentication backend.

        Args:
            token_verifier: The token verifier to validate API keys
            api_key_header: The header name to look for API keys (defaults to settings.BA_API_KEY_REQUEST_HEADER)
        """
        self.api_key_verifier = api_key_verifier

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, AuthenticatedAPIKeyUser] | None:
        """
        Authenticate the connection using API key from headers.

        Args:
            conn: The HTTP connection

        Returns:
            Tuple of (AuthCredentials, AuthenticatedAPIKeyUser) if valid, None otherwise
        """
        API_KEY_REQUEST_HEADER = settings.BA_API_KEY_REQUEST_HEADER.replace("_", "-")

        unencrypted_api_key = conn.headers.get(API_KEY_REQUEST_HEADER, None)

        access_token: AccessToken | None = None

        if isinstance(unencrypted_api_key, str):
            access_token = await self.api_key_verifier.verify_api_key(
                unencrypted_api_key=unencrypted_api_key
            )

        if not access_token:
            return None

        return AuthCredentials(access_token.scopes), AuthenticatedAPIKeyUser(auth_info=access_token)


class APIKeyAuthBackend(BaseAPIKeyAuthBackend):
    def __init__(self):
        super(APIKeyAuthBackend, self).__init__(
            api_key_verifier=typ.cast(APIKeyVerifierProtocol, APIKeyVerifier())
        )


class RequireAPIKeyMiddleware:
    """
    Middleware that requires a valid API Key in the Authorization header.

    This will validate the token with the auth provider and store the resulting
    auth info in the request state.
    """

    def __init__(
        self,
        app: ASGIApp,
        required_scopes: list[str] = [],
        resource_metadata_url: AnyHttpUrl | None = None,
    ):
        """
        Initialize the middleware.

        Args:
            app: ASGI application
            required_scopes: List of scopes that the token must have
            resource_metadata_url: Optional protected resource metadata URL for WWW-Authenticate header
        """
        self.app = app
        self.required_scopes = required_scopes
        self.resource_metadata_url = resource_metadata_url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        auth_user = scope.get("user")

        if isinstance(auth_user, AuthenticatedAPIKeyUser):
            await self.app(scope, receive, send)
        elif isinstance(auth_user, AuthenticatedUser):
            auth_credentials = scope.get("auth")

            for required_scope in self.required_scopes:
                # auth_credentials should always be provided; this is just paranoia
                if auth_credentials is None or required_scope not in auth_credentials.scopes:
                    await self._send_auth_error(
                        send,
                        status_code=403,
                        error="insufficient_scope",
                        description=f"Required scope: {required_scope}",
                    )
                    return

            await self.app(scope, receive, send)
        else:
            await self._send_auth_error(
                send,
                status_code=401,
                error="invalid_api_key_or_invalid_invalid_token",
                description="Authentication required",
            )

    async def _send_auth_error(
        self, send: Send, status_code: int, error: str, description: str
    ) -> None:
        """Send an authentication error response with WWW-Authenticate header."""
        # Build WWW-Authenticate header value
        www_auth_parts = [f'error="{error}"', f'error_description="{description}"']
        if self.resource_metadata_url:
            www_auth_parts.append(f'resource_metadata="{self.resource_metadata_url}"')

        www_authenticate = f"Bearer {', '.join(www_auth_parts)}"

        # Send response
        body = {"error": error, "error_description": description}
        body_bytes = json.dumps(body).encode()

        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body_bytes)).encode()),
                    (b"www-authenticate", www_authenticate.encode()),
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body_bytes,
            }
        )


class RequireAPIKeyOrAuthMiddleware:
    """
    Middleware that requires
        a valid API Key in the Authorization header.
    or
        a valid Bearer token in the Authorization header.

    This will validate the token with the auth provider and store the resulting
    auth info in the request state.
    """

    email_regex_rules: typ.List[str]

    def __init__(
        self,
        app: ASGIApp,
        email_regex_rules: typ.List[str],
        required_scopes: list[str] = [],
        resource_metadata_url: AnyHttpUrl | None = None,
    ):
        """
        Initialize the middleware.

        Args:
            app: ASGI application
            required_scopes: List of scopes that the token must have
            resource_metadata_url: Optional protected resource metadata URL for WWW-Authenticate header
        """
        self.app = app
        self.email_regex_rules = email_regex_rules
        self.required_scopes = required_scopes
        self.resource_metadata_url = resource_metadata_url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        auth_user = scope.get("user")
        if isinstance(auth_user, AuthenticatedUser):
            auth_credentials = scope.get("auth")
            claims = getattr(auth_user.access_token, "claims")

            # Validate email
            if isinstance(claims, dict):
                email = claims.get("email", "")
                validation_results = [
                    re.match(rule, email) is not None for rule in self.email_regex_rules
                ]
                if not all(validation_results):
                    await self._send_auth_error(
                        send,
                        status_code=401,
                        error="invalid_email_address",
                        description="Email Address does not meet requirements.",
                    )
                    return

            # Scopes not applicable to APIKey authentication
            if isinstance(auth_user, AuthenticatedAPIKeyUser) is False:
                for required_scope in self.required_scopes:
                    # auth_credentials should always be provided; this is just paranoia
                    if auth_credentials is None or required_scope not in auth_credentials.scopes:
                        await self._send_auth_error(
                            send,
                            status_code=403,
                            error="insufficient_scope",
                            description=f"Required scope: {required_scope}",
                        )
                        return

            await self.app(scope, receive, send)
        else:
            await self._send_auth_error(
                send,
                status_code=401,
                error="invalid_api_key_or_invalid_invalid_token",
                description="Authentication required",
            )

    async def _send_auth_error(
        self, send: Send, status_code: int, error: str, description: str
    ) -> None:
        """Send an authentication error response with WWW-Authenticate header."""
        # Build WWW-Authenticate header value
        www_auth_parts = [f'error="{error}"', f'error_description="{description}"']
        if self.resource_metadata_url:
            www_auth_parts.append(f'resource_metadata="{self.resource_metadata_url}"')

        www_authenticate = f"Bearer {', '.join(www_auth_parts)}"

        # Send response
        body = {"error": error, "error_description": description}
        body_bytes = json.dumps(body).encode()

        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body_bytes)).encode()),
                    (b"www-authenticate", www_authenticate.encode()),
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body_bytes,
            }
        )
