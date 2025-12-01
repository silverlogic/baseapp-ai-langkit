from django.apps import AppConfig


class BaseappMCPLogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "baseapp_mcp.logs"
    label = "baseapp_mcp_logs"
    verbose_name = "BaseApp MCP Logs"

    def ready(self):
        # Import admin to ensure it's registered
        from . import admin  # noqa
