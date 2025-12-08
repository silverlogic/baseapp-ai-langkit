from django.contrib import admin

from baseapp_ai_langkit.base.utils.model_admin_helper import admin_classes

from .models import TokenUsage

ModelAdmin = admin_classes["ModelAdmin"]


@admin.register(TokenUsage)
class TokenUsageAdmin(ModelAdmin):
    list_display = (
        "id",
        "user_identifier",
        "year_month",
        "total_tokens",
        "transformer_calls",
        "modified",
    )
    list_filter = [
        "year",
        "month",
        "modified",
    ]
    search_fields = [
        "user_identifier",
    ]
    readonly_fields = (
        "user_identifier",
        "year",
        "month",
        "total_tokens",
        "transformer_calls",
        "created",
        "modified",
    )
    ordering = ["-year", "-month", "user_identifier"]

    def year_month(self, obj):
        """Display year/month in a readable format."""
        return f"{obj.year}/{obj.month:02d}"

    year_month.short_description = "Period"
    year_month.admin_order_field = "year"
