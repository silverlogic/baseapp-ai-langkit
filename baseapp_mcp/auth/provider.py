import logging
import typing
from datetime import datetime, time

from django.apps import apps
from fastmcp.server.auth.auth import AccessToken

logger = logging.getLogger(__name__)


class APIKeyVerifierProtocol(typing.Protocol):
    """Protocol for verifying API Keys."""

    APIKeyModel: str

    async def verify_api_key(self, unencrypted_api_key: str) -> AccessToken | None:
        """Verify an API Key and return access info if valid."""


class BaseAPIKeyVerifier(APIKeyVerifierProtocol):
    APIKeyModel: str = None

    def __init__(self, *args, **kwargs):
        """
        Initialize the token verifier.

        Args:
            resource_server_url: The URL of this resource server. This is used
            for RFC 8707 resource indicators, including creating the WWW-Authenticate
            header.
            required_scopes: Scopes that are required for all requests
        """
        super().__init__(*args, **kwargs)

    async def verify_api_key(self, unencrypted_api_key: str) -> AccessToken | None:
        APIKeyModel = apps.get_model(self.APIKeyModel)

        encrypted_api_key: bytes = APIKeyModel.objects.encrypt(
            unencrypted_value=unencrypted_api_key
        )

        if api_key := await (
            APIKeyModel.objects.all()
            .filter(is_expired=False, encrypted_api_key=encrypted_api_key)
            .select_related("user")
            .afirst()
        ):
            expires_at: int | None = None
            if expiry_date := api_key.expiry_date:
                expiry_datetime = datetime.combine(expiry_date, time.min)
                expires_at = expiry_datetime.timestamp()

            # Create an AccessToken with basic claims
            access_token = AccessToken(
                token=encrypted_api_key.decode(),
                client_id=APIKeyModel.__name__,
                scopes=[],
                expires_at=int(expires_at) if expires_at else None,
                claims=dict(email=api_key.user.email),
            )
            return access_token

        return None


class APIKeyVerifier(BaseAPIKeyVerifier):
    """Base class for token verifiers (Resource Servers).

    This class provides token verification capability without OAuth server functionality.
    Token verifiers typically don't provide authentication routes by default.
    """

    APIKeyModel = "baseapp_api_key.APIKey"
