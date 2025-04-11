from typing import Callable, Optional, Type

from langchain_core.messages import AnyMessage


class BasePromptSchema:
    """
    BasePromptSchema serves as a flexible tool for managing prompts within the system.
    By standardizing the way prompts are written, it enables advanced functionalities
    and enhances the overall prompt management process.

    Args:
        description (str): A brief description of the prompt schema.
        prompt (str): The prompt template that will be formatted with placeholders.
        required_placeholders (list[str]): A list of placeholders that must be present in the prompt.
        placeholders_data (dict): A dictionary containing data to fill in the placeholders.
        conditional_rule (Callable[[dict], bool]): An optional function that determines if the prompt should be generated based on the placeholders data.

    Methods:
        validate() -> bool: Checks if all required placeholders are present in the prompt.
        format() -> str: Formats the prompt using the provided placeholders data.
        get_langgraph_message(message_type: Type[AnyMessage]) -> Optional[AnyMessage]:
            Generates a message of the specified type if the conditional rule is satisfied.
    """

    description: str
    prompt: str
    required_placeholders: list[str]
    placeholders_data: dict
    conditional_rule: Callable[[dict], bool]

    def __init__(
        self,
        description: str,
        prompt: str,
        required_placeholders: list[str] = [],
        placeholders_data: dict = {},
        conditional_rule: Optional[Callable[[dict], bool]] = None,
    ):
        self.description = description
        self.prompt = prompt
        self.required_placeholders = required_placeholders
        self.placeholders_data = placeholders_data
        self.conditional_rule = conditional_rule

    def validate(self, custom_prompt: str = None) -> bool:
        """Validates that all required placeholders are present in the prompt."""
        prompt = custom_prompt or self.prompt
        return all([ph in prompt for ph in self.required_placeholders])

    def format(self) -> str:
        """Formats the prompt using the placeholders data."""
        return self.prompt.format(**self.placeholders_data)

    def get_langgraph_message(self, message_type: Type[AnyMessage]) -> Optional[AnyMessage]:
        """Generates a message of the specified type if the conditional rule is satisfied."""
        if self.conditional_rule and not self.conditional_rule(self.placeholders_data):
            return None
        return message_type(content=self.format())
