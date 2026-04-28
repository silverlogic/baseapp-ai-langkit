from __future__ import annotations

import typing as typ

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.auth import AuthContext

from baseapp_mcp.app_settings import app_settings

if typ.TYPE_CHECKING:
    from baseapp_mcp.tools.base_mcp_tool import BaseMCPTool
User = get_user_model()


def _get_permission_for_tool(tool_cls: typ.Type[BaseMCPTool]) -> typ.Optional[str]:
    _TOOL_CATEGORY_PERMISSIONS = {
        "MCP_TOOLS": "baseapp_mcp_permissions.access_standard_mcp_tools",
        "DEBUG_MCP_TOOLS": "baseapp_mcp_permissions.access_debug_mcp_tools",
        "EXPERIMENTAL_MCP_TOOLS": "baseapp_mcp_permissions.access_experimental_mcp_tools",
    }

    tool_import_string = f"{tool_cls.__module__}.{tool_cls.__qualname__}"
    for setting_name, permission in _TOOL_CATEGORY_PERMISSIONS.items():
        if tool_import_string in getattr(app_settings, setting_name):
            return permission
    return None


def require_tool_permission(tool_cls: typ.Type[BaseMCPTool]) -> typ.Callable:
    async def _check(ctx: AuthContext) -> bool:
        if ctx.token is None:
            raise AuthorizationError(_("Authentication required"))
        if (email := ctx.token.claims.get("email")) and (
            permission := _get_permission_for_tool(tool_cls)
        ):
            try:
                user = await User.objects.aget(email=email)
                has_permission = await database_sync_to_async(user.has_perm)(permission)
                if has_permission:
                    return True
            except User.DoesNotExist:
                pass
        raise AuthorizationError(_("You do not have permission to perform this action."))

    return _check
