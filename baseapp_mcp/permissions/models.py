from django.db import models

MCP_TOOL_PERMISSION_GROUPS = [
    ("Standard MCP Tool Access", "access_standard_mcp_tools", "Can access standard MCP tools"),
    ("Debug MCP Tools", "access_debug_mcp_tools", "Can access debug MCP tools"),
    (
        "Experimental MCP Tools",
        "access_experimental_mcp_tools",
        "Can access experimental MCP tools",
    ),
]


class MCPToolPermission(models.Model):
    """
    Exists solely to register the three MCP tool permissions with Django.
    Has no table and should never be instantiated or queried.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [(codename, name) for _, codename, name in MCP_TOOL_PERMISSION_GROUPS]
