from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    SlackAIChat,
    SlackAIChatMessage,
    SlackAIChatMessageReaction,
    SlackEvent,
    SlackEventStatus,
)


class SlackEventStatusInline(admin.TabularInline):
    model = SlackEventStatus
    extra = 0
    readonly_fields = ("id", "created", "modified", "status", "status_message")


@admin.register(SlackEvent)
class SlackEventAdmin(admin.ModelAdmin):
    list_display = ("id", "team_id", "event_ts", "created", "modified")
    search_fields = ("id", "team_id", "event_ts")
    list_filter = ("team_id", "event_ts")
    ordering = ("-created",)
    readonly_fields = ("id", "team_id", "event_ts", "created", "modified")
    inlines = [SlackEventStatusInline]


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


class SlackAIChatMessageReactionInline(admin.TabularInline):
    model = SlackAIChatMessageReaction
    extra = 0
    readonly_fields = ("id", "created", "modified", "reaction", "slack_event")


@admin.register(SlackAIChatMessage)
class SlackAIChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "slack_chat_link",
        "user_message_slack_event_link",
        "output_slack_event_link",
        "created",
        "modified",
    )
    search_fields = (
        "id",
        "slack_chat__id",
        "user_message_slack_event__id",
        "output_slack_event__id",
    )
    ordering = ("-created",)
    readonly_fields = ("id", "created", "modified")
    inlines = [SlackAIChatMessageReactionInline]

    def slack_chat_link(self, obj):
        url = reverse("admin:baseapp_ai_langkit_slack_slackevent_change", args=[obj.slack_chat.id])
        return format_html('<a href="{}">{}</a>', url, obj.slack_chat.id)

    slack_chat_link.short_description = "Slack Chat"

    def user_message_slack_event_link(self, obj):
        url = reverse(
            "admin:baseapp_ai_langkit_slack_slackevent_change",
            args=[obj.user_message_slack_event.id],
        )
        return format_html('<a href="{}">{}</a>', url, obj.user_message_slack_event.id)

    user_message_slack_event_link.short_description = "User Message Slack Event"

    def output_slack_event_link(self, obj):
        url = reverse(
            "admin:baseapp_ai_langkit_slack_slackevent_change", args=[obj.output_slack_event.id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.output_slack_event.id)

    output_slack_event_link.short_description = "Output Slack Event"
