import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from baseapp_ai_langkit.base.interfaces.exceptions import LLMChatInterfaceException
from baseapp_ai_langkit.chats.models import ChatMessage
from baseapp_ai_langkit.chats.tests.factories import (
    ChatMessageFactory,
    ChatSessionFactory,
)
from baseapp_ai_langkit.tests.factories import UserFactory


class TestBaseChatViewSet(APITestCase):
    def setUp(self):
        self.url = reverse("v1:llm-chat-list")

        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.session = ChatSessionFactory(user=self.user)

    def test_list_messages(self):
        ChatMessageFactory(session=self.session, role="user", content="Hello!")
        ChatMessageFactory(session=self.session, role="assistant", content="Hi!")

        response = self.client.get(self.url, {"session_id": str(self.session.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][0]["content"], "Hi!")
        self.assertEqual(response.data["results"][1]["content"], "Hello!")

    def test_list_invalid_session(self):
        response = self.client.get(self.url, {"session_id": uuid.uuid4()})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session_id", response.data)

    def test_list_invalid_session_id(self):
        response = self.client.get(self.url, {"session_id": "invalid-session-id"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session_id", response.data)

    def test_list_missing_existing_session_id(self):
        """In this case, the latest session will be used."""
        response = self.client.get(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_missing_session_id(self):
        """In this case, the session will be created."""
        tmp_user = UserFactory()
        self.client.force_authenticate(user=tmp_user)
        response = self.client.get(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
        self.assertIsNotNone(tmp_user.chat_sessions.first())

    @patch("baseapp_ai_langkit.chats.rest_framework.views.BaseChatViewSet.chat_runner.safe_run")
    def test_create_message(self, mock_chat_runner):
        mock_chat_runner.return_value = "Hello from LLM!"

        data = {"session_id": str(self.session.id), "content": "Hello!"}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("session", response.data)
        self.assertIn("user_message", response.data)
        self.assertIn("assistant_message", response.data)

        self.assertEqual(response.data["user_message"]["content"], "Hello!")
        self.assertEqual(response.data["assistant_message"]["content"], "Hello from LLM!")

        self.assertEqual(ChatMessage.objects.filter(session=self.session).count(), 2)
        self.assertEqual(
            ChatMessage.objects.filter(session=self.session, role="user").first().content, "Hello!"
        )
        self.assertEqual(
            ChatMessage.objects.filter(session=self.session, role="assistant").first().content,
            "Hello from LLM!",
        )

    @patch("baseapp_ai_langkit.chats.rest_framework.views.BaseChatViewSet.chat_runner.safe_run")
    def test_create_message_with_latest_session(self, mock_chat_runner):
        mock_chat_runner.return_value = "Hello from LLM!"

        data = {"content": "Hello!"}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("session", response.data)
        self.assertIn("user_message", response.data)
        self.assertIn("assistant_message", response.data)

        self.assertEqual(response.data["user_message"]["content"], "Hello!")
        self.assertEqual(response.data["assistant_message"]["content"], "Hello from LLM!")

        session_id = response.data["session"]["id"]
        self.assertIsNotNone(session_id)

        self.assertEqual(ChatMessage.objects.filter(session_id=session_id).count(), 2)
        self.assertEqual(
            ChatMessage.objects.filter(session_id=session_id, role="user").first().content, "Hello!"
        )
        self.assertEqual(
            ChatMessage.objects.filter(session_id=session_id, role="assistant").first().content,
            "Hello from LLM!",
        )
        self.assertEqual(str(self.user.chat_sessions.first().id), str(self.session.id))

    @patch("baseapp_ai_langkit.chats.rest_framework.views.BaseChatViewSet.chat_runner.safe_run")
    def test_create_message_and_session(self, mock_chat_runner):
        mock_chat_runner.return_value = "Hello from LLM!"

        data = {"content": "Hello!"}

        tmp_user = UserFactory()
        self.client.force_authenticate(user=tmp_user)
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("session", response.data)
        self.assertIn("user_message", response.data)
        self.assertIn("assistant_message", response.data)

        self.assertEqual(response.data["user_message"]["content"], "Hello!")
        self.assertEqual(response.data["assistant_message"]["content"], "Hello from LLM!")

        session_id = response.data["session"]["id"]
        self.assertIsNotNone(session_id)

        self.assertEqual(ChatMessage.objects.filter(session_id=session_id).count(), 2)
        self.assertEqual(
            ChatMessage.objects.filter(session_id=session_id, role="user").first().content, "Hello!"
        )
        self.assertEqual(
            ChatMessage.objects.filter(session_id=session_id, role="assistant").first().content,
            "Hello from LLM!",
        )
        self.assertNotEqual(str(tmp_user.chat_sessions.first().id), str(self.session.id))

    def test_create_invalid_session(self):
        response = self.client.post(self.url, {"content": "Hello!", "session_id": uuid.uuid4()})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session_id", response.data)

    def test_create_invalid_session_id(self):
        response = self.client.post(
            self.url, {"content": "Hello!", "session_id": "invalid-session-id"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session_id", response.data)

    def test_create_missing_content(self):
        response = self.client.post(self.url, {"session_id": str(self.session.id)})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("content", response.data)

    @patch("baseapp_ai_langkit.chats.rest_framework.views.BaseChatViewSet.chat_runner.safe_run")
    def test_chat_runner_llm_exception(self, mock_chat_runner):
        mock_chat_runner.side_effect = LLMChatInterfaceException("Something went wrong!")

        response = self.client.post(
            self.url, {"content": "Hello!", "session_id": str(self.session.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data)
        self.assertEqual(response.data["code"], "chat_runner_error")

        self.assertEqual(ChatMessage.objects.filter(session=self.session).count(), 0)
