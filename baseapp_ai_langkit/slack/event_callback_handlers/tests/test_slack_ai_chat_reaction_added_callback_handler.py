from unittest.mock import MagicMock

from baseapp_ai_langkit.slack.event_callback_handlers.slack_ai_chat_reaction_added_callback_handler import (
    SlackAIChatReactionAddedCallbackHandler,
)
from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.models import SlackAIChatMessageReaction
from baseapp_ai_langkit.slack.tests.factories import (
    SlackAIChatMessageFactory,
    SlackEventFactory,
)
from baseapp_ai_langkit.slack.tests.test import SlackTestCase
from baseapp_ai_langkit.tests.factories import UserFactory


class TestSlackAIChatReactionAddedCallbackHandler(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_event = SlackEventFactory(
            data={
                "team_id": "T12345",
                "event": {
                    "type": "reaction_added",
                    "user": self.dummy_real_user_id(),
                    "reaction": "thumbsup",
                    "item": {
                        "type": "message",
                        "channel": self.dummy_channel_id(),
                        "ts": "12134567890.123457",
                    },
                    "event_ts": "1234567890.123456",
                },
            }
        )
        self.mock_slack_event_callback = MagicMock(spec=BaseSlackEventCallback)
        self.mock_slack_event_callback.slack_event = self.slack_event
        self.mock_slack_event_callback.data = self.slack_event.data
        self.mock_slack_event_callback.team_id = self.slack_event.data["team_id"]
        self.mock_slack_event_callback.event_data = self.slack_event.data["event"]
        self.mock_slack_event_callback.event_type = self.slack_event.data["event"]["type"]

        self.mock_slack_instance_controller = MagicMock()
        self.mock_slack_event_callback.slack_instance_controller = (
            self.mock_slack_instance_controller
        )

        self.handler = SlackAIChatReactionAddedCallbackHandler(
            slack_event_callback=self.mock_slack_event_callback
        )
        self.handler.slack_instance_controller = self.mock_slack_instance_controller
        self.handler.verify_incoming_app = MagicMock()

    def test_handle_reaction_added_message_not_found(self):
        with self.assertRaises(BaseSlackEventCallback.WarningException) as context:
            self.handler.handle()

        self.assertIn("SlackAIChatMessage matching query does not exist", str(context.exception))

    def test_handle_reaction_added_success(self):
        user = UserFactory()
        self.mock_slack_instance_controller.get_or_create_user_from_slack_user.return_value = (
            user,
            True,
        )

        output_slack_event = SlackEventFactory(
            team_id=self.slack_event.data["team_id"],
            event_ts=self.slack_event.data["event"]["item"]["ts"],
        )
        slack_chat_message = SlackAIChatMessageFactory(output_slack_event=output_slack_event)

        reaction_count_before = SlackAIChatMessageReaction.objects.count()

        self.handler.handle()

        reaction_count_after = SlackAIChatMessageReaction.objects.count()
        self.assertEqual(reaction_count_after, reaction_count_before + 1)

        reaction = SlackAIChatMessageReaction.objects.last()
        self.assertEqual(reaction.user, user)
        self.assertEqual(reaction.slack_chat_message, slack_chat_message)
        self.assertEqual(reaction.reaction, self.slack_event.data["event"]["reaction"])
        self.assertEqual(reaction.slack_event, self.slack_event)

        self.mock_slack_instance_controller.get_or_create_user_from_slack_user.assert_called_once_with(
            slack_user_id=self.slack_event.data["event"]["user"]
        )
