"""
Django settings accessor for baseapp_mcp.

Follows the django-allauth pattern: ``AppSettings`` with a prefix, ``_setting()``,
and lazy resolution via module :func:`__getattr__` (PEP 562).
"""

from __future__ import annotations

from typing import Any, List, Type, TypeVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

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

    def _validated_mcp_tool_lists(self) -> tuple[List[str], List[str], List[str]]:
        mcp = self._require_type("MCP_TOOLS", [], list)
        debug = self._require_type("DEBUG_MCP_TOOLS", [], list)
        experimental = self._require_type("EXPERIMENTAL_MCP_TOOLS", [], list)
        pairs = [
            ("MCP_TOOLS", set(mcp), "DEBUG_MCP_TOOLS", set(debug)),
            ("MCP_TOOLS", set(mcp), "EXPERIMENTAL_MCP_TOOLS", set(experimental)),
            ("DEBUG_MCP_TOOLS", set(debug), "EXPERIMENTAL_MCP_TOOLS", set(experimental)),
        ]
        for name_a, set_a, name_b, set_b in pairs:
            overlap = list(set_a & set_b)
            if overlap:
                raise ImproperlyConfigured(
                    f"settings.{self.prefix}{name_a} and {self.prefix}{name_b} "
                    f"must not share entries: {overlap}"
                )
        return mcp, debug, experimental

    @property
    def MCP_TOOLS(self) -> List[str]:
        mcp, _, _ = self._validated_mcp_tool_lists()
        return mcp

    @property
    def DEBUG_MCP_TOOLS(self) -> List[str]:
        _, debug, _ = self._validated_mcp_tool_lists()
        return debug

    @property
    def EXPERIMENTAL_MCP_TOOLS(self) -> List[str]:
        _, _, experimental = self._validated_mcp_tool_lists()
        return experimental

    @property
    def MCP_TOOL_PERMISSION_MODEL(self) -> str:
        return self._require_type("MCP_TOOL_PERMISSION_MODEL", "", str)


app_settings = AppSettings("BASEAPP_AI_LANGKIT_")


def __getattr__(name: str) -> Any:
    # See https://peps.python.org/pep-0562/
    return getattr(app_settings, name)
