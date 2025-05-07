from django.apps import apps
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
    from baseapp_ai_langkit.slack.rest_framework.viewsets import SlackWebhookViewSet

    baseapp_ai_langkit_router.register(
        r"slack/webhook", SlackWebhookViewSet, basename="slack-webhook"
    )
