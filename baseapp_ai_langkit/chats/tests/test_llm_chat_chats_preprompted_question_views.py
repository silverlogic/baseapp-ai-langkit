from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from baseapp_ai_langkit.chats.tests.factories import ChatPrePromptedQuestionFactory
from baseapp_ai_langkit.tests.factories import UserFactory


class TestChatPrePromptedQuestionViewSet(APITestCase):
    def setUp(self):
        self.url = reverse("v1:llm-chat-pre-prompted-question-list")

        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list(self):
        ChatPrePromptedQuestionFactory(is_active=True)
        ChatPrePromptedQuestionFactory(is_active=True)
        ChatPrePromptedQuestionFactory(is_active=False)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_without_active_question(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
