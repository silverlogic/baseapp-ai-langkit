from __future__ import annotations

from starlette.authentication import (
    AuthCredentials,
    AuthenticationError,
    UnauthenticatedUser,
)
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.types import Receive, Scope, Send


class MultipleAuthenticationMiddleware(AuthenticationMiddleware):
    """
    A `AuthenticationMiddleware` subclass that won't overwrite existing auth and user scope
    to allow for multiple authentication methods in the authentication chain.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ["http", "websocket"]:
            await self.app(scope, receive, send)
            return

        if "user" in scope:
            existing_user = scope["user"]
            if not isinstance(existing_user, UnauthenticatedUser):
                await self.app(scope, receive, send)
                return

        conn = HTTPConnection(scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except AuthenticationError as exc:
            response = self.on_error(conn, exc)
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1000})
            else:
                await response(scope, receive, send)
            return

        if auth_result is None:
            auth_result = AuthCredentials(), UnauthenticatedUser()
        scope["auth"], scope["user"] = auth_result
        await self.app(scope, receive, send)
