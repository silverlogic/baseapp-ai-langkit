from django.apps import apps
from django.conf import settings
from rest_framework import routers

from baseapp_ai_langkit.chats.rest_framework.views import (
    BaseChatViewSet,
    ChatIdentityViewSet,
    ChatPrePromptedQuestionViewSet,
)

# Chats
baseapp_ai_langkit_router = routers.DefaultRouter()
baseapp_ai_langkit_router.register(r"chat", BaseChatViewSet, basename="llm-chat")
baseapp_ai_langkit_router.register(
    r"chat/identity", ChatIdentityViewSet, basename="llm-chat-identity"
)
baseapp_ai_langkit_router.register(
    r"chat/pre-prompted-question",
    ChatPrePromptedQuestionViewSet,
    basename="llm-chat-pre-prompted-question",
)

# Slack
if apps.is_installed("baseapp_ai_langkit.slack"):
    from django.utils.module_loading import import_string

    from baseapp_ai_langkit.slack.rest_framework.viewsets import (
        SlackInteractiveEndpointViewSet,
        SlackWebhookViewSet,
    )

    baseapp_ai_langkit_router.register(
        r"slack/webhook", SlackWebhookViewSet, basename="slack_webhook"
    )

    baseapp_ai_langkit_router.register(
        r"slack/interactive-endpoint",
        SlackInteractiveEndpointViewSet,
        basename="slack_interactive_endpoint",
    )

    slash_command_imports: list[str] = []
    if isinstance(settings.BASEAPP_AI_LANGKIT_SLACK_SLASH_COMMANDS, list):
        slash_command_imports.extend(settings.BASEAPP_AI_LANGKIT_SLACK_SLASH_COMMANDS)
    for slash_command_import in slash_command_imports:
        SlashCommandViewset = import_string(slash_command_import)
        baseapp_ai_langkit_router.register(
            rf"slack/slash/{SlashCommandViewset.name}",
            SlashCommandViewset,
            basename=f"slack_slash_{SlashCommandViewset.name}",
        )
