import os

__all__ = [
    "BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_EVENT_CALLBACK",
    "BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_CONTROLLER",
    "BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN",
    "BASEAPP_AI_LANGKIT_SLACK_BOT_APP_ID",
    "SLACK_CLIENT_ID",
    "SLACK_CLIENT_SECRET",
    "SLACK_VERIFICATION_TOKEN",
    "SLACK_SIGNING_SECRET",
]

# Baseapp AI Langkit Slack Settings
BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_EVENT_CALLBACK = (
    "baseapp_ai_langkit.slack.event_callbacks.slack_ai_chat_event_callback.SlackAIChatEventCallback"
)
BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_CONTROLLER = (
    "baseapp_ai_langkit.slack.slack_ai_chat_controller.SlackAIChatController"
)

BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN = os.environ.get(
    "BASEAPP_AI_LANGKIT_SLACK_BOT_USER_OAUTH_TOKEN", None
)
BASEAPP_AI_LANGKIT_SLACK_BOT_APP_ID = os.environ.get("BASEAPP_AI_LANGKIT_SLACK_BOT_APP_ID", None)
SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", None)
SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", None)
SLACK_VERIFICATION_TOKEN = os.environ.get("SLACK_VERIFICATION_TOKEN", None)
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", None)
