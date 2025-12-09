from __future__ import annotations

from starlette.authentication import UnauthenticatedUser
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.types import Receive, Scope, Send


class MultipleAuthenticationMiddleware(AuthenticationMiddleware):
    """
    A `AuthenticationMiddleware` subclass that won't overwrite existing auth and user scope
    to allow for multiple authentication methods in the authentication chain.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if "user" in scope:
            existing_user = scope["user"]
            if not isinstance(existing_user, UnauthenticatedUser):
                # If a user is already authenticated, skip further authentication
                await self.app(scope, receive, send)
                return
        
        # Otherwise, proceed with normal authentication
        await super().__call__(scope, receive, send)
