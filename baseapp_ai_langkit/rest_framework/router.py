from rest_framework import routers

from baseapp_ai_langkit.chats.rest_framework.views import (
    BaseChatViewSet,
    ChatIdentityViewSet,
    ChatPrePromptedQuestionViewSet,
)

baseapp_ai_langkit_router = routers.DefaultRouter()
# TODO: (when the FE chat is connected to Campaign Chat) figure out how to disable the chat routes without blocking the unit tests.
baseapp_ai_langkit_router.register(r"chat", BaseChatViewSet, basename="llm-chat")
baseapp_ai_langkit_router.register(
    r"chat/identity", ChatIdentityViewSet, basename="llm-chat-identity"
)
baseapp_ai_langkit_router.register(
    r"chat/pre-prompted-question",
    ChatPrePromptedQuestionViewSet,
    basename="llm-chat-pre-prompted-question",
)
