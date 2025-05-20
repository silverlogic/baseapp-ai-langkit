import copy
from abc import ABC, abstractmethod
from typing import List, Optional, Union

from langchain.base_language import BaseLanguageModel
from langchain.schema import AIMessage, SystemMessage
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema


class LLMNodeInterface(ABC):
    """
    LLMNodeInterface is designed to allow prompt customizations for all workers and agents,
    providing more flexibility in the prompt system structure. This abstract class serves as a
    foundation for implementing various agents and workers that utilize language models, enabling
    them to define and manage their prompt schemas and state modifiers effectively.

    Args:
        llm (BaseLanguageModel): The default language model to use.
        config (RunnableConfig): The configuration for the runnable.
        usage_prompt_schema (Optional[BasePromptSchema]): Optional usage prompt schema.
        state_modifier_schema (Optional[Union[BasePromptSchema, List[BasePromptSchema]]]):
            Optional state modifier schema or list of schemas.
    """

    llm: BaseLanguageModel
    config: RunnableConfig
    usage_prompt_schema: Optional[BasePromptSchema] = None
    state_modifier_schema: Optional[Union[BasePromptSchema, List[BasePromptSchema]]] = None

    def __init__(
        self,
        llm: BaseLanguageModel,
        config: RunnableConfig,
        usage_prompt_schema: Optional[BasePromptSchema] = None,
        state_modifier_schema: Optional[Union[BasePromptSchema, List[BasePromptSchema]]] = None,
        **kwargs,
    ):
        self.llm = self.get_llm_model(llm)
        self.config = config

        if usage_prompt_schema:
            self.usage_prompt_schema = usage_prompt_schema
        if state_modifier_schema:
            self.state_modifier_schema = state_modifier_schema

        if custom_placeholders_data := self.get_custom_placeholders_data():
            if self.usage_prompt_schema:
                self.usage_prompt_schema.placeholders_data.update(custom_placeholders_data)
            if self.state_modifier_schema:
                for state_modifier in self.get_state_modifier_list():
                    state_modifier.placeholders_data.update(custom_placeholders_data)

    def get_llm_model(self, llm: BaseLanguageModel) -> BaseLanguageModel:
        """
        Override this method in LLMNodeInterface subclass to specify a LLM model for the node.
        """
        return llm

    def get_custom_placeholders_data(self) -> Optional[dict]:
        """Use this method to add custom placeholders during runtime."""
        return None

    def get_usage_prompt(self) -> str:
        if self.usage_prompt_schema:
            return self.usage_prompt_schema.format()
        return ""

    def get_state_modifier_list(self) -> List[BasePromptSchema]:
        if self.state_modifier_schema:
            if not isinstance(self.state_modifier_schema, list):
                state_modifiers = [self.state_modifier_schema]
            else:
                state_modifiers = self.state_modifier_schema
            return state_modifiers
        return []

    @classmethod
    def get_static_state_modifier_list(cls) -> List[BasePromptSchema]:
        if cls.state_modifier_schema:
            if not isinstance(cls.state_modifier_schema, list):
                state_modifiers = [cls.state_modifier_schema]
            else:
                state_modifiers = cls.state_modifier_schema
            return copy.deepcopy(state_modifiers)
        return []

    @classmethod
    def get_static_usage_prompt(cls) -> str:
        if cls.usage_prompt_schema:
            return copy.deepcopy(cls.usage_prompt_schema)
        return ""

    def get_state_modifier_system_message(self) -> List[SystemMessage]:
        state_modifiers = self.get_state_modifier_list()
        if len(state_modifiers) > 0:
            system_messages = [
                state_modifier.get_langgraph_message(message_type=SystemMessage)
                for state_modifier in state_modifiers
            ]
            return list(filter(lambda v: v is not None, system_messages))
        return []

    @abstractmethod
    def invoke(self, messages: List[AnyMessage], *args, **kwargs) -> AIMessage:
        pass
