from abc import ABC, abstractmethod

from baseapp_ai_langkit.slack.event_callbacks.slack_event_callback import (
    SlackEventCallback,
)


class BaseHandleEventCallback(ABC):
    slack_event_callback: SlackEventCallback

    def __init__(self, slack_event_callback: SlackEventCallback):
        self.slack_event_callback = slack_event_callback

    @abstractmethod
    def handle(self):
        pass
