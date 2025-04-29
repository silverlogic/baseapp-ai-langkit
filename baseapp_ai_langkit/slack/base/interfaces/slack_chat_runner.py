from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface


class BaseSlackChatInterface(BaseChatInterface):
    slack_context: dict

    def __init__(self, slack_context: dict, *args, **kwargs):
        self.slack_context = slack_context
        super().__init__(*args, **kwargs)
