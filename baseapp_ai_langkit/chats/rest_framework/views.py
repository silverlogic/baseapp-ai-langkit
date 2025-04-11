from rest_framework import permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface
from baseapp_ai_langkit.base.interfaces.exceptions import LLMChatInterfaceException
from baseapp_ai_langkit.chats.models import (
    ChatIdentity,
    ChatMessage,
    ChatPrePromptedQuestion,
)
from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner

from .serializers import (
    ChatCreateSerializer,
    ChatIdentitySerializer,
    ChatListSerializer,
    ChatMessageSerializer,
    ChatPrePromptedQuestionSerializer,
    ChatSessionSerializer,
)


class ChatMessagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class BaseChatViewSet(viewsets.ViewSet):
    """
    ViewSet designed to be extendable for customizing how your LLM Chat behaves.

    The idea of this ViewSet is to allow the developers to override only the needed methods. Here
    are the list of methods and properties that we suggest you to override to achieve your level
    of customization:
    - `chat_runner`: The chat runner that will be used to handle LLM processing. It must
    implement the `BaseChatInterface` interface. The default implementation is `DefaultChatRunner`.
    - `get_list_serializer`: The serializer used to validate the params of the list endpoint, as
    well as handle the session validation.
    - `get_create_serializer`: The serializer used to validate the data of the create endpoint, as
    well as handle the session validation and creation.

    Everything else is customizable as well.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ChatMessagePagination
    chat_runner: BaseChatInterface = DefaultChatRunner

    def get_queryset(self, session):
        return ChatMessage.objects.filter(session=session).order_by("-created")

    def get_list_serializer(self, *args, **kwargs):
        return ChatListSerializer(*args, **kwargs)

    def get_create_serializer(self, *args, **kwargs):
        return ChatCreateSerializer(*args, **kwargs)

    def get_message_serializer(self, *args, **kwargs):
        return ChatMessageSerializer(*args, **kwargs)

    def get_session_serializer(self, *args, **kwargs):
        return ChatSessionSerializer(*args, **kwargs)

    def list(self, request):
        serializer = self.get_list_serializer(
            data=request.query_params, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        # TODO: (when moving this to the Baseapp) If we override the ViewSet and change how the
        # session is managed (e.g. campaign), they would share the session, mixing the messages.
        if serializer.validated_data.get("session_id"):
            session = serializer.get_session_or_error()
        else:
            session = serializer.get_or_create_user_session()

        messages = self.get_queryset(session)
        paginator = self.pagination_class()
        paginated_messages = paginator.paginate_queryset(messages, request)
        serializer = self.get_message_serializer(paginated_messages, many=True)
        return paginator.get_paginated_response(serializer.data)

    def create(self, request):
        serializer = self.get_create_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("session_id"):
            session = serializer.get_or_create_session()
        else:
            session = serializer.get_or_create_user_session()

        input_content = serializer.validated_data.get("content")

        try:
            output_content = self.chat_runner(session=session, user_input=input_content).safe_run()
        except LLMChatInterfaceException as e:
            return Response(
                {"error": str(e), "code": "chat_runner_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {
            "session": session.id,
            "role": ChatMessage.ROLE_CHOICES.user,
            "content": input_content,
        }
        user_message_serializer = self.get_message_serializer(data=data)
        user_message_serializer.is_valid(raise_exception=True)
        user_message_serializer.save()

        data = {
            "session": session.id,
            "role": ChatMessage.ROLE_CHOICES.assistant,
            "content": output_content,
        }
        assistant_message_serializer = self.get_message_serializer(data=data)
        assistant_message_serializer.is_valid(raise_exception=True)
        assistant_message_serializer.save()

        session_serializer = self.get_session_serializer(session)

        response_data = {
            "session": session_serializer.data,
            "user_message": user_message_serializer.data,
            "assistant_message": assistant_message_serializer.data,
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class ChatIdentityViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        try:
            identity = ChatIdentity.objects.get(is_active=True)
            serializer = ChatIdentitySerializer(identity)
            return Response(serializer.data)
        except ChatIdentity.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class ChatPrePromptedQuestionViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        queryset = ChatPrePromptedQuestion.objects.filter(is_active=True)
        serializer = ChatPrePromptedQuestionSerializer(queryset, many=True)
        return Response(serializer.data)
