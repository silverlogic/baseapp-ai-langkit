from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from slack_sdk import WebClient

User = get_user_model()


class SlackInstanceController:
    slack_web_client: WebClient

    def __init__(self):
        self.slack_web_client = self._get_slack_web_client()

    def _get_slack_web_client(self) -> WebClient:
        return WebClient(token=settings.BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN)

    def get_or_create_user_from_slack_user(
        self, slack_user_id: str
    ) -> Tuple[Optional[AbstractBaseUser], bool]:
        response = self.slack_web_client.users_profile_get(
            user=slack_user_id,
        )
        response.validate()
        user_profile: dict = response["profile"]
        is_from_bot = isinstance(user_profile.get("api_app_id"), str)
        if is_from_bot:
            return (None, False)

        return User.objects.update_or_create(
            email=user_profile["email"],
            defaults=dict(
                first_name=user_profile.get("first_name"),
                last_name=user_profile.get("last_name"),
            ),
        )
