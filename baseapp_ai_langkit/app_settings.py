"""
Django settings accessor for baseapp_ai_langkit.

Follows the django-allauth pattern: ``AppSettings`` with a prefix, ``_setting()``,
and lazy resolution via module :func:`__getattr__` (PEP 562).
"""

from __future__ import annotations

from typing import Any, List, Optional, Type, TypeVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from baseapp_ai_langkit.settings import (
    BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_CONTROLLER as _DEFAULT_SLACK_AI_CHAT_CONTROLLER,
)
from baseapp_ai_langkit.settings import (
    BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_EVENT_CALLBACK as _DEFAULT_SLACK_AI_CHAT_EVENT_CALLBACK,
)
from baseapp_ai_langkit.settings import (
    BASEAPP_AI_LANGKIT_SLACK_BOT_APP_ID as _DEFAULT_SLACK_BOT_APP_ID,
)
from baseapp_ai_langkit.settings import (
    BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN as _DEFAULT_SLACK_BOT_USER_OAUTH_TOKEN,
)

T_co = TypeVar("T_co")


class AppSettings:
    """Reads ``prefix_*`` keys from Django settings."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def _setting(self, name: str, dflt: Any) -> Any:
        return getattr(settings, self.prefix + name, dflt)

    def _require_type(self, name: str, dflt: Any, expected_type: Type[T_co]) -> T_co:
        value = self._setting(name, dflt)
        if not isinstance(value, expected_type):
            raise ImproperlyConfigured(
                f"settings.{self.prefix}{name} must be a {expected_type.__name__}"
            )
        return value

    @property
    def SLACK_AI_CHAT_EVENT_CALLBACK(self) -> str:
        return self._setting(
            "SLACK_AI_CHAT_EVENT_CALLBACK",
            _DEFAULT_SLACK_AI_CHAT_EVENT_CALLBACK,
        )

    @property
    def SLACK_AI_CHAT_CONTROLLER(self) -> str:
        return self._setting(
            "SLACK_AI_CHAT_CONTROLLER",
            _DEFAULT_SLACK_AI_CHAT_CONTROLLER,
        )

    @property
    def SLACK_BOT_USER_OAUTH_TOKEN(self) -> Optional[str]:
        return self._setting(
            "SLACK_BOT_USER_OAUTH_TOKEN",
            _DEFAULT_SLACK_BOT_USER_OAUTH_TOKEN,
        )

    @property
    def SLACK_BOT_APP_ID(self) -> Optional[str]:
        return self._setting("SLACK_BOT_APP_ID", _DEFAULT_SLACK_BOT_APP_ID)

    @property
    def SLACK_SLASH_COMMANDS(self) -> Any:
        return self._setting("SLACK_SLASH_COMMANDS", [])

    @property
    def SLACK_INTERACTIVE_ENDPOINT_HANDLERS(self) -> Any:
        return self._setting("SLACK_INTERACTIVE_ENDPOINT_HANDLERS", [])

    @property
    def MCP_TOOLS(self) -> List[Any]:
        return self._require_type("MCP_TOOLS", [], list)

    @property
    def DEBUG_MCP_TOOLS(self) -> List[Any]:
        return self._require_type("DEBUG_MCP_TOOLS", [], list)

    @property
    def MCP_TOOL_PERMISSION_MODEL(self) -> str:
        return self._require_type("MCP_TOOL_PERMISSION_MODEL", "", str)


_app_settings = AppSettings("BASEAPP_AI_LANGKIT_")


def __getattr__(name: str) -> Any:
    # See https://peps.python.org/pep-0562/
    return getattr(_app_settings, name)
