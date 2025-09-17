from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from baseapp_ai_langkit.chats.tests.factories import ChatIdentityFactory
from baseapp_ai_langkit.tests.factories import UserFactory


class TestChatIdentityViewSet(APITestCase):
    def setUp(self):
        self.url = reverse("v1:llm-chat-identity-list")

        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_get_active_chat(self):
        active_chat = ChatIdentityFactory(is_active=True)
        ChatIdentityFactory(is_active=False)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], active_chat.id)

    def test_get_no_active_chat(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
