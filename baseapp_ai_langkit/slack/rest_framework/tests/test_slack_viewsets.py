import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from baseapp_ai_langkit.slack.models import SlackEvent, SlackEventStatus
from baseapp_ai_langkit.slack.rest_framework.viewsets import SlackWebhookViewSet
from baseapp_ai_langkit.slack.tests.factories import (
    SlackEventFactory,
    SlackEventStatusFactory,
)
from baseapp_ai_langkit.slack.tests.test import SlackTestCase


class TestSlackWebhookViewSet(APITestCase, SlackTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("v1:slack-webhook-list")

    @patch.object(SlackWebhookViewSet, "permission_classes", new=[])
    def test_url_verification(self):
        challenge = "test_challenge_token"
        response = self.client.post(
            self.url,
            data=json.dumps({"type": "url_verification", "challenge": challenge}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"challenge": challenge})

    @patch("baseapp_ai_langkit.slack.tasks.slack_handle_event_hook_event_callback_data.delay")
    @patch.object(SlackWebhookViewSet, "permission_classes", new=[])
    def test_event_callback_new_event(self, mock_task):
        event_data = {
            "type": "event_callback",
            "team_id": "T12345",
            "event": {
                "type": "app_mention",
                "event_ts": "1234567890.123456",
                "user": "U12345",
                "text": "Hello <@bot>",
            },
        }

        self.assertEqual(SlackEvent.objects.count(), 0)

        response = self.client.post(self.url, data=event_data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(SlackEvent.objects.count(), 1)
        slack_event = SlackEvent.objects.first()
        self.assertEqual(slack_event.team_id, "T12345")
        self.assertEqual(slack_event.event_ts, "1234567890.123456")
        self.assertEqual(slack_event.event_type, "app_mention")

        self.assertEqual(SlackEventStatus.objects.count(), 1)
        event_status = SlackEventStatus.objects.first()
        self.assertEqual(event_status.slack_event, slack_event)

        mock_task.assert_called_once_with(slack_event_id=slack_event.id)

    @patch("baseapp_ai_langkit.slack.tasks.slack_handle_event_hook_event_callback_data.delay")
    @patch.object(SlackWebhookViewSet, "permission_classes", new=[])
    def test_event_callback_existing_event(self, mock_task):
        existing_event = SlackEventFactory(
            team_id="T12345",
            event_ts="1234567890.123456",
            event_type="app_mention",
            data={
                "team_id": "T12345",
                "event": {
                    "type": "app_mention",
                    "event_ts": "1234567890.123456",
                    "user": "U12345",
                    "text": "Hello <@bot>",
                },
            },
        )

        SlackEventStatusFactory(slack_event=existing_event, status=SlackEventStatus.STATUS.success)

        event_data = {
            "type": "event_callback",
            "team_id": "T12345",
            "event": {
                "type": "app_mention",
                "event_ts": "1234567890.123456",
                "user": "U12345",
                "text": "Updated message",
            },
        }

        response = self.client.post(self.url, data=event_data, content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(SlackEvent.objects.count(), 1)
        updated_event = SlackEvent.objects.first()
        self.assertEqual(updated_event.id, existing_event.id)
        self.assertEqual(updated_event.data["event"]["text"], "Updated message")
        self.assertEqual(SlackEventStatus.objects.count(), 2)
        mock_task.assert_called_once_with(slack_event_id=existing_event.id)

    @patch.object(SlackWebhookViewSet, "permission_classes", new=[])
    def test_event_callback_already_running(self):
        existing_event = SlackEventFactory(
            team_id="T12345",
            event_ts="1234567890.123456",
            event_type="app_mention",
            data={
                "team_id": "T12345",
                "event": {
                    "type": "app_mention",
                    "event_ts": "1234567890.123456",
                    "user": "U12345",
                    "text": "Hello <@bot>",
                },
            },
        )

        SlackEventStatusFactory(slack_event=existing_event, status=SlackEventStatus.STATUS.running)

        # Create a viewset instance to test the protected method
        viewset = SlackWebhookViewSet()

        with self.assertRaises(Exception) as context:
            viewset._raise_if_event_exists_and_is_running(
                team_id="T12345", event_ts="1234567890.123456", event_type="app_mention"
            )

        self.assertIn("Event is already running", str(context.exception))

    @patch("baseapp_ai_langkit.slack.rest_framework.viewsets.logger")
    @patch.object(SlackWebhookViewSet, "permission_classes", new=[])
    def test_exception_handling(self, mock_logger):
        response = self.client.post(
            self.url, data=json.dumps({"type": "event_callback"}), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_logger.exception.assert_called_once()
