from django.apps import AppConfig
from django.db.models.signals import post_migrate


class BaseappMCPPermissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "baseapp_mcp.permissions"
    label = "baseapp_mcp_permissions"
    verbose_name = "BaseApp MCP Permissions"

    def ready(self):
        from . import admin, signals  # noqa

        post_migrate.connect(signals.create_mcp_permission_groups, sender=self)
