from django.contrib import admin

from baseapp_ai_langkit.base.utils.model_admin_helper import admin_classes

from .models import MCPLog

ModelAdmin = admin_classes["ModelAdmin"]


@admin.register(MCPLog)
class MCPLogAdmin(ModelAdmin):
    list_display = (
        "id",
        "tool_name",
        "tool_arguments",
        "user_identifier",
        "total_tokens",
        "transformer_calls",
        "created",
    )
    search_fields = ("tool_arguments",)
    readonly_fields = (
        "tool_name",
        "tool_arguments",
        "user_identifier",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "transformer_calls",
        "response",
    )
    list_filter = ["created", "tool_name"]
