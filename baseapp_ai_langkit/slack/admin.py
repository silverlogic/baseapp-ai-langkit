import json

from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer

from baseapp_ai_langkit.base.utils.model_admin_helper import ModelAdmin, TabularInline
from baseapp_ai_langkit.slack.utils.export_reactions_helper import (
    generate_reaction_export_csv,
    get_message_content,
)

from .models import (
    SlackAIChat,
    SlackAIChatMessage,
    SlackAIChatMessageReaction,
    SlackEvent,
    SlackEventStatus,
)


def pretty_json(data):
    if data is None:
        return None
    formatter = HtmlFormatter(style="colorful", cssclass="pretty-json")
    return format_html(
        highlight("{}", JsonLexer(), formatter),
        json.dumps(data, sort_keys=True, indent=2),
    )


class SlackEventStatusInline(TabularInline):
    model = SlackEventStatus
    extra = 0
    readonly_fields = ("id", "created", "modified", "status", "status_message")


@admin.register(SlackEvent)
class SlackEventAdmin(ModelAdmin):
    list_display = ("id", "team_id", "event_ts", "event_type", "created", "modified")
    search_fields = ("id", "team_id", "event_ts", "event_type")
    list_filter = ("team_id", "event_ts", "event_type")
    ordering = ("-created",)
    fields = ("id", "team_id", "event_ts", "event_type", "data_json_pretty", "created", "modified")
    readonly_fields = (
        "id",
        "team_id",
        "event_ts",
        "event_type",
        "data_json_pretty",
        "created",
        "modified",
    )
    inlines = [SlackEventStatusInline]

    def data_json_pretty(self, instance):
        return pretty_json(instance.data)

    data_json_pretty.short_description = "data"

    class Media:
        css = {
            "all": [
                "css/pretty-json.css",
            ]
        }


class SlackAIChatMessageInline(TabularInline):
    model = SlackAIChatMessage
    extra = 0
    fields = (
        "id",
        "chat_message_link",
        "user_message_slack_event",
        "user_message_text",
        "output_slack_event",
        "output_message_text",
    )
    readonly_fields = (
        "id",
        "chat_message_link",
        "user_message_slack_event",
        "user_message_text",
        "output_slack_event",
        "output_message_text",
    )

    def chat_message_link(self, obj):
        url = reverse("admin:baseapp_ai_langkit_slack_slackaichatmessage_change", args=[obj.id])
        return format_html('<a href="{}">Chat Message {}</a>', url, obj.id)

    chat_message_link.short_description = "Chat Message"

    def user_message_text(self, obj):
        data = obj.user_message_slack_event.data
        if data and isinstance(data, dict):
            message = data.get("event", {})
            if isinstance(message, dict):
                return message.get("text", "")
        return ""

    user_message_text.short_description = "User Message Text"

    def output_message_text(self, obj):
        if obj.output_response_output_data and isinstance(obj.output_response_output_data, dict):
            message = obj.output_response_output_data.get("message", {})
            if isinstance(message, dict):
                return message.get("text", "")
        return ""

    output_message_text.short_description = "Output Message Text"


@admin.register(SlackAIChat)
class SlackAIChatAdmin(ModelAdmin):
    list_display = (
        "id",
        "celery_task_id",
        "chat_session_link",
        "slack_event_link",
        "slack_event_event_ts",
        "slack_event_event_type",
        "created",
        "modified",
    )
    search_fields = ("id", "celery_task_id")
    ordering = ("-created",)
    readonly_fields = ("id", "created", "modified", "chat_session_link", "slack_event_link")
    inlines = [SlackAIChatMessageInline]

    def slack_event_event_ts(self, obj):
        return obj.slack_event.event_ts

    slack_event_event_ts.short_description = "Event TS"

    def slack_event_event_type(self, obj):
        return obj.slack_event.event_type

    slack_event_event_type.short_description = "Event Type"

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


class SlackAIChatMessageReactionInline(TabularInline):
    model = SlackAIChatMessageReaction
    extra = 0
    readonly_fields = ("id", "created", "modified", "reaction", "slack_event")


@admin.register(SlackAIChatMessage)
class SlackAIChatMessageAdmin(ModelAdmin):
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
    fields = (
        "id",
        "created",
        "modified",
        "slack_chat",
        "user_message_slack_event",
        "output_slack_event",
        "output_response_output_data_json_pretty",
    )
    readonly_fields = (
        "id",
        "created",
        "modified",
        "slack_chat",
        "user_message_slack_event",
        "output_slack_event",
        "output_response_output_data_json_pretty",
    )
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
        return format_html(
            '<a href="{}">{} (event_ts: {})</a>',
            url,
            obj.user_message_slack_event.id,
            obj.user_message_slack_event.event_ts,
        )

    user_message_slack_event_link.short_description = "User Message Slack Event"

    def output_slack_event_link(self, obj):
        url = reverse(
            "admin:baseapp_ai_langkit_slack_slackevent_change", args=[obj.output_slack_event.id]
        )
        return format_html(
            '<a href="{}">{} (event_ts: {})</a>',
            url,
            obj.output_slack_event.id,
            obj.output_slack_event.event_ts,
        )

    output_slack_event_link.short_description = "Output Slack Event"

    def output_response_output_data_json_pretty(self, instance):
        return pretty_json(instance.output_response_output_data)

    output_response_output_data_json_pretty.short_description = "output_response_output_data"

    class Media:
        css = {
            "all": [
                "css/pretty-json.css",
            ]
        }


@admin.register(SlackAIChatMessageReaction)
class SlackAIChatMessageReactionAdmin(ModelAdmin):
    list_display = (
        "id",
        "user_email",
        "slack_chat_message_link",
        "reaction",
        "slack_user_message",
        "slack_output_message",
        "created",
        "modified",
    )
    search_fields = (
        "id",
        "user__id",
        "slack_chat_message__id",
        "reaction",
    )
    ordering = ("-created",)
    readonly_fields = (
        "id",
        "created",
        "modified",
        "user",
        "slack_chat_message",
        "reaction",
        "slack_event",
    )
    actions = ["export_csv_thumbs_up_action", "export_csv_thumbs_down_action"]

    def user_email(self, obj):
        return obj.user.email

    def slack_chat_message_link(self, obj):
        url = reverse(
            "admin:baseapp_ai_langkit_slack_slackaichatmessage_change",
            args=[obj.slack_chat_message.id],
        )
        return format_html('<a href="{}">{}</a>', url, obj.slack_chat_message.id)

    slack_chat_message_link.short_description = "Slack Chat Message"

    def slack_user_message(self, obj):
        return get_message_content(obj.slack_chat_message.user_message_slack_event)

    slack_user_message.short_description = "User Message"

    def slack_output_message(self, obj):
        return get_message_content(obj.slack_chat_message.output_slack_event)

    slack_output_message.short_description = "Output Message"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/export-csv-thumbs-up/",
                self.admin_site.admin_view(self.export_csv_thumbs_up_action),
                name="langkit_slackaichatmessagereaction_export_csv_thumbs_up",
            ),
            path(
                "<path:object_id>/export-csv-thumbs-down/",
                self.admin_site.admin_view(self.export_csv_thumbs_down_action),
                name="langkit_slackaichatmessagereaction_export_csv_thumbs_down",
            ),
        ]
        return custom_urls + urls

    def export_csv_thumbs_up_action(self, request, queryset):
        return generate_reaction_export_csv(
            queryset, SlackAIChatMessageReaction.THUMBS_UP_REACTIONS, "thumbs_up"
        )

    def export_csv_thumbs_down_action(self, request, queryset):
        return generate_reaction_export_csv(
            queryset, SlackAIChatMessageReaction.THUMBS_DOWN_REACTIONS, "thumbs_down"
        )

    export_csv_thumbs_up_action.short_description = "Export CSV Thumbs Up"
    export_csv_thumbs_down_action.short_description = "Export CSV Thumbs Down"
