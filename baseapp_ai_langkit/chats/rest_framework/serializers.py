from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from baseapp_ai_langkit.chats.models import (
    ChatIdentity,
    ChatMessage,
    ChatPrePromptedQuestion,
    ChatSession,
)


class BaseChatSerializer(serializers.Serializer):
    def get_or_create_user_session(self) -> ChatSession:
        request = self.context.get("request")
        return ChatSession.objects.get_or_create_user_session(request.user)


class ChatListSerializer(BaseChatSerializer):
    session_id = serializers.UUIDField(required=False)

    def get_session_or_error(self) -> ChatSession:
        session_id = self.validated_data.get("session_id")
        if not session_id:
            raise serializers.ValidationError({"session_id": _("This field is required.")})

        try:
            return ChatSession.objects.get_session_or_error(session_id)
        except LookupError as le:
            raise serializers.ValidationError({"session_id": str(le)})


class ChatCreateSerializer(BaseChatSerializer):
    session_id = serializers.UUIDField(required=False)
    content = serializers.CharField(required=True, max_length=400)

    def get_or_create_session(self) -> ChatSession:
        session_id = self.validated_data.get("session_id")
        request = self.context.get("request")

        try:
            return ChatSession.objects.get_or_create_session(session_id, request.user)
        except LookupError as le:
            raise serializers.ValidationError({"session_id": str(le)})


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "session", "role", "content", "created"]


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ["id", "user", "created"]


class ChatIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatIdentity
        fields = [
            "id",
            "name",
            "avatar",
            "chat_intro_title",
            "chat_intro_subtitle",
            "chat_fab_text",
            "is_active",
        ]


class ChatPrePromptedQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatPrePromptedQuestion
        fields = ["id", "title", "prompt", "is_active", "order"]
