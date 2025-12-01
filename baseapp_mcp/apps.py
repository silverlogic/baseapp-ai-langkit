from django.apps import AppConfig


class BaseappMCPConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "baseapp_mcp"
    label = "baseapp_mcp"
    verbose_name = "BaseApp MCP"
