from abc import ABC, abstractmethod

from baseapp_ai_langkit.slack.event_callbacks.base_slack_event_callback import (
    BaseSlackEventCallback,
)
from baseapp_ai_langkit.slack.slack_instance_controller import SlackInstanceController


class BaseSlackAIChatEvent(ABC):
    slack_event_callback: BaseSlackEventCallback
    slack_instance_controller: SlackInstanceController

    data: dict
    team_id: str
    event_data: dict
    event_type: str

    def __init__(
        self,
        slack_event_callback: BaseSlackEventCallback,
    ):
        self.slack_event_callback = slack_event_callback
        self.slack_instance_controller = self.slack_event_callback.slack_instance_controller

        self.data = self.slack_event_callback.data
        self.team_id = self.slack_event_callback.team_id
        self.event_data = self.slack_event_callback.event_data
        self.event_type = self.slack_event_callback.event_type

    @abstractmethod
    def handle(self):
        pass
