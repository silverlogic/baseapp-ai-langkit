from django.db import models

from baseapp_ai_langkit import app_settings


class BaseMCPToolPermission(models.Model):
    class Meta:
        abstract = True
        managed = False

        tool_import_strings = [
            *app_settings.DEBUG_MCP_TOOLS,
            *app_settings.MCP_TOOLS,
        ]

        default_permissions = ()
        permissions = [
            (tool_import_string, "MCP Tool Access %s" % tool_import_string)
            for tool_import_string in tool_import_strings
        ]

        del tool_import_strings
