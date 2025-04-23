from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import SlackEvent, SlackAIChat


@admin.register(SlackEvent)
class SlackEventAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created", "modified")
    search_fields = ("id", "status")
    list_filter = ("status",)
    ordering = ("-created",)
    readonly_fields = ("id", "status", "created", "modified")


@admin.register(SlackAIChat)
class SlackAIChatAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "celery_task_id",
        "chat_session_link",
        "slack_event_link",
        "created",
        "modified",
    )
    search_fields = ("id", "celery_task_id")
    ordering = ("-created",)
    readonly_fields = ("id", "created", "modified")

    def chat_session_link(self, obj):
        url = reverse(
            "admin:baseapp_ai_langkit_chats_chatsession_change", args=[obj.chat_session.id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.chat_session.id)

    chat_session_link.short_description = "Chat Session"

    def slack_event_link(self, obj):
        url = reverse("admin:baseapp_ai_langkit_slack_slackevent_change", args=[obj.slack_event.id])
        return format_html('<a href="{}">{}</a>', url, obj.slack_event.id)

    slack_event_link.short_description = "Slack Event"
