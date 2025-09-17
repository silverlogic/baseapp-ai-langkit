import abc
import itertools
from dataclasses import dataclass
from dataclasses import field as dcfield

import pydash


# TODO: Move to langkit
@dataclass
class SlackBaseModalBuilder(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def SLACK_VIEW_CALLBACK_ID(cls) -> str:
        """Return the Slack view callback ID for this modal."""
        pass

    @abc.abstractmethod
    def build(self, **kwargs) -> dict:
        """Builds the modal."""
        pass


@dataclass
class SlackExampleModalBuilder(SlackBaseModalBuilder):
    """
    An example SlackBaseModalBuilder
    """

    option_1_options: list[int] = dcfield(default_factory=lambda: list(range(1, 10)))
    option_2_options: list[int] = dcfield(default_factory=lambda: list(range(1, 10)))

    selected_option_1: int | None = None
    selected_option_2: int | None = None

    @classmethod
    def SLACK_VIEW_CALLBACK_ID(cls) -> str:
        return "example"

    @classmethod
    def SLACK_TEXT_BLOCK_ID(cls) -> str:
        return "example"

    def _build_example_text_block(self) -> dict:
        return {
            "block_id": self.__class__.SLACK_TEXT_BLOCK_ID(),
            "type": "input",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "initial_value": "",
                "multiline": True,
                "action_id": "action",
            },
            "label": {"type": "plain_text", "text": "example"},
        }

    @classmethod
    def SLACK_OPTION_1_BLOCK_ID(cls) -> str:
        return "option_1"

    def _build_example_options_block_1(self) -> dict:
        def _option_for(value: int) -> dict:
            return {
                "text": {
                    "type": "plain_text",
                    "text": f"Value {value}",
                    "emoji": False,
                },
                "value": f"{value}",
            }

        if len(self.option_1_options) == 0:
            return None

        return {
            "block_id": self.__class__.SLACK_OPTION_1_BLOCK_ID(),
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Option 1"},
            "accessory": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select an item", "emoji": True},
                "options": [_option_for(item) for item in self.option_1_options],
                **dict(
                    dict(
                        initial_option=_option_for(
                            pydash.find(
                                self.option_1_options, lambda item: item == self.selected_option_1
                            )
                            if self.selected_option_1
                            else None
                        )
                    )
                    if isinstance(self.selected_option_1, int)
                    else dict()
                ),
                "action_id": "static_select",
            },
        }

    @classmethod
    def SLACK_OPTION_2_BLOCK_ID(cls) -> str:
        return "option_2"

    def _build_example_options_block_2(self) -> dict:
        def _option_for(value: int) -> dict:
            return {
                "text": {
                    "type": "plain_text",
                    "text": f"Value {value}",
                    "emoji": False,
                },
                "value": f"{value}",
            }

        # Only show this field if we have selected an option_1
        if not isinstance(self.selected_option_1, int):
            return None
        if len(self.option_2_options) == 0:
            return None

        return {
            "block_id": self.__class__.SLACK_OPTION_2_BLOCK_ID(),
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Option 2"},
            "accessory": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select an item", "emoji": True},
                "options": [_option_for(item) for item in self.option_2_options],
                **dict(
                    dict(
                        initial_option=_option_for(
                            pydash.find(
                                self.option_2_options, lambda item: item == self.selected_option_2
                            )
                            if self.selected_option_2
                            else None
                        )
                    )
                    if isinstance(self.selected_option_2, int)
                    else dict()
                ),
                "action_id": "static_select",
            },
        }

    def build(self, **kwargs) -> dict:
        return {
            "callback_id": self.__class__.SLACK_VIEW_CALLBACK_ID(),
            "title": {"type": "plain_text", "text": "Example"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": list(
                itertools.filterfalse(
                    lambda item: not item,
                    [
                        self._build_example_text_block(),
                        self._build_example_options_block_1(),
                        self._build_example_options_block_2(),
                    ],
                )
            ),
            "type": "modal",
            **kwargs,
        }
