import typing as typ

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.auth import AuthContext

from baseapp_ai_langkit import app_settings

if typ.TYPE_CHECKING:
    from baseapp_mcp.tools.base_mcp_tool import BaseMCPTool
User = get_user_model()


def require_tool_permission(tool_cls: typ.Type["BaseMCPTool"]) -> typ.Callable:
    """
    Helper function to require tool permission for a given tool class.
    tool_cls must be subclass of baseapp_mcp.tools.base_mcp_tool.BaseMCPTool
    """

    async def _check(ctx: AuthContext) -> bool:
        if ctx.token is None:
            raise AuthorizationError(_("Authentication required"))
        if email := ctx.token.claims.get("email"):
            try:
                PermissionModel = import_string(app_settings.MCP_TOOL_PERMISSION_MODEL)
                permission_app_label = PermissionModel._meta.app_label
                permission_codename = f"{tool_cls.__module__}.{tool_cls.__qualname__}"
                permission_slug = f"{permission_app_label}.{permission_codename}"

                user = await User.objects.aget(email=email)
                has_permission = await database_sync_to_async(user.has_perm)(permission_slug, None)
                if has_permission:
                    return True
            except User.DoesNotExist:
                pass
        raise AuthorizationError(_("You do not have permission to perform this action."))

    return _check
