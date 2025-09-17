from unittest.mock import MagicMock

from django.test import override_settings

from baseapp_ai_langkit.slack.event_callbacks.tests.test_slack_ai_chat_event_callback import (
    TestSlackAIChatEventCallback,
)
from baseapp_ai_langkit.slack.slack_ai_chat_controller import SlackAIChatController
from baseapp_ai_langkit.slack.tasks import (
    slack_handle_event_hook_event_callback_data,
    slack_process_incoming_user_slack_message,
)
from baseapp_ai_langkit.slack.tests.factories import (
    SlackAIChatFactory,
    SlackEventFactory,
)

from .test import SlackTestCase

MockEventCallback = MagicMock(TestSlackAIChatEventCallback)
MockController = MagicMock(SlackAIChatController)


class TestSlackTasks(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event = SlackEventFactory()
        self.slack_chat = SlackAIChatFactory(slack_event=self.slack_event)

    @override_settings(
        BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_EVENT_CALLBACK="baseapp_ai_langkit.slack.tests.test_slack_tasks.MockEventCallback"
    )
    def test_slack_handle_event_hook_event_callback_data_with_custom_callback(self):
        slack_handle_event_hook_event_callback_data(self.slack_event.id)
        MockEventCallback.assert_called_once()

    @override_settings(
        BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_CONTROLLER="baseapp_ai_langkit.slack.tests.test_slack_tasks.MockController"
    )
    def test_slack_process_incoming_user_slack_message_with_custom_controller(self):
        slack_process_incoming_user_slack_message(self.slack_chat.id, self.slack_event.id)
        MockController.assert_called_once()
