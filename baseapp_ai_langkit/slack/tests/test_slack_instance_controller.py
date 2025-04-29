from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController
from baseapp_ai_langkit.tests.factories import UserFactory

from .test import SlackTestCase


class TestSlackInstanceController(SlackTestCase):
    def setUp(self):
        super().setUp()
        self.slack_instance_controller = SlackInstanceController()

    def test_get_or_create_user_for_slack_user__real_user(self):
        user_profile_data = self.user_profile_data()

        self.mock_slack_api_call("users.profile.get", response_data=user_profile_data)

        # Test Created
        user, created = self.slack_instance_controller.get_or_create_user_from_slack_user(
            slack_user_id=self.dummy_real_user_id()
        )
        self.assertTrue(created)
        self.assertEqual(user.email, user_profile_data["profile"]["email"])
        self.assertEqual(user.first_name, user_profile_data["profile"]["first_name"])
        self.assertEqual(user.last_name, user_profile_data["profile"]["last_name"])

        # Test Updated
        user, created = self.slack_instance_controller.get_or_create_user_from_slack_user(
            slack_user_id=self.dummy_real_user_id()
        )
        self.assertFalse(created)

    def test_get_or_create_user_for_slack_user__bot_user(self):
        user_profile_data = self.bot_user_profile_data()

        self.mock_slack_api_call("users.profile.get", response_data=user_profile_data)

        user, created = self.slack_instance_controller.get_or_create_user_from_slack_user(
            slack_user_id=self.dummy_bot_user_id()
        )
        self.assertIsNone(user)
        self.assertFalse(created)

    def test_get_or_create_user_for_slack_bot(self):
        user, created = self.slack_instance_controller.get_or_create_user_from_slack_bot(
            bot_id=self.dummy_bot_user_id()
        )
        self.assertIsNotNone(user)
        self.assertTrue(created)
        self.assertEqual(user.email, f"slack_bot_{self.dummy_bot_user_id()}@tsl.io")
        self.assertEqual(user.first_name, "Slackbot")
        self.assertEqual(user.last_name, self.dummy_bot_user_id())

    def test_get_or_create_user_for_slack_bot__already_exists(self):
        user = UserFactory(email=f"slack_bot_{self.dummy_bot_user_id()}@tsl.io")
        user, created = self.slack_instance_controller.get_or_create_user_from_slack_bot(
            bot_id=self.dummy_bot_user_id()
        )
        self.assertIsNotNone(user)
        self.assertFalse(created)
