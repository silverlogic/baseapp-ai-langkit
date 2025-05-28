from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from baseapp_ai_langkit.base.utils.model_admin_helper import ModelAdmin

from .models import ChatIdentity, ChatMessage, ChatPrePromptedQuestion, ChatSession


@admin.register(ChatIdentity)
class ChatIdentityAdmin(ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)
    ordering = ("name",)


class ChatSessionFilter(admin.SimpleListFilter):
    title = "session"
    parameter_name = "session"

    def lookups(self, request, model_admin):
        return [(session.id, f"Session {session.id}") for session in ChatSession.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(session__id=self.value())
        return queryset


@admin.register(ChatMessage)
class ChatMessageAdmin(ModelAdmin):
    list_display = ("id", "session", "role", "content", "created")
    list_filter = (ChatSessionFilter,)
    search_fields = ("id", "content")
    ordering = ("created",)
    readonly_fields = ("id", "session", "role", "content", "created")


@admin.register(ChatSession)
class ChatSessionAdmin(ModelAdmin):
    list_display = ("id", "user", "created", "modified", "view_messages_link")
    search_fields = ("id",)
    ordering = ("-created",)
    readonly_fields = ("id", "created", "modified")

    def view_messages_link(self, obj):
        url = (
            reverse("admin:baseapp_ai_langkit_chats_chatmessage_changelist") + f"?session={obj.id}"
        )
        return format_html('<a href="{}">View Messages</a>', url)

    view_messages_link.short_description = "Messages"


@admin.register(ChatPrePromptedQuestion)
class ChatPrePromptedQuestionAdmin(SortableAdminMixin, ModelAdmin):
    list_display = (
        "title",
        "is_active",
        "order",
    )
    search_fields = (
        "title",
        "prompt",
    )
    list_filter = ("is_active",)
