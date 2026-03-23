import httpx
from baseapp_api_key.models import APIKey
from pydantic import SecretStr

__all__ = ["APIKeyAuth"]


class APIKeyAuth(httpx.Auth):
    def __init__(
        self,
        api_key: APIKey,
    ):
        self.unencrypted_api_key = SecretStr(
            APIKey.objects.decrypt(encrypted_value=api_key.encrypted_api_key)
        )

    def auth_flow(self, request):
        request.headers["HTTP-API-KEY"] = self.unencrypted_api_key.get_secret_value()
        yield request
