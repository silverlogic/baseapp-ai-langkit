from baseapp_ai_langkit.chats.runners.default_chat_runner import DefaultChatRunner
from baseapp_ai_langkit.slack.interfaces.slack_chat_runner import BaseSlackChatInterface


class SlackDummyRunner(BaseSlackChatInterface, DefaultChatRunner):
    def __init__(self, slack_context: dict, *args, **kwargs):
        BaseSlackChatInterface.__init__(self, slack_context=slack_context, *args, **kwargs)
        DefaultChatRunner.__init__(self, *args, **kwargs)
