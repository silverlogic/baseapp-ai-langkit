from collections import OrderedDict

if "CONSTANCE_CONFIG" not in globals():
    CONSTANCE_CONFIG = OrderedDict()

if "CONSTANCE_CONFIG_FIELDSETS" not in globals():
    CONSTANCE_CONFIG_FIELDSETS = OrderedDict()

CONSTANCE_CONFIG = {
    **CONSTANCE_CONFIG,
    **OrderedDict(
        [
            (
                "SLACK_BOT_USER_OAUTH_TOKEN",
                ("", "The bot use OAuth Token for the Slack app."),
            ),
        ]
    ),
}
CONSTANCE_CONFIG_FIELDSETS = {
    **CONSTANCE_CONFIG_FIELDSETS,
    **OrderedDict(
        [
            (
                "Slack Options",
                ("SLACK_BOT_USER_OAUTH_TOKEN",),
            ),
        ]
    ),
}

# Baseapp AI Langkit Slack Settings
BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_EVENT_CALLBACK = (
    "baseapp_ai_langkit.slack.event_callbacks.slack_ai_chat_event_callback.SlackAIChatEventCallback"
)
BASEAPP_AI_LANGKIT_SLACK_AI_CHAT_CONTROLLER = (
    "baseapp_ai_langkit.slack.slack_ai_chat_controller.SlackAIChatController"
)
