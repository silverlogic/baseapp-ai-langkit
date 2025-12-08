from django.apps import AppConfig


class BaseappMCPRateLimitsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "baseapp_mcp.rate_limits"
    label = "baseapp_mcp_rate_limits"
    verbose_name = "BaseApp MCP Rate Limits"

    def ready(self):
        # Import admin to ensure it's registered
        from . import admin  # noqa
