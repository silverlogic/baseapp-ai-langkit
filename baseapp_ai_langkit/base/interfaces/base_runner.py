import logging
from abc import ABC, abstractmethod
from typing import Tuple, Type, Union

from baseapp_ai_langkit.base.interfaces.exceptions import LLMChatInterfaceException
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.chats.models import ChatSession

logger = logging.getLogger(__name__)


class BaseRunnerInterface(ABC):
    # TODO: change to OrderedDict.
    edge_nodes: dict[str, Type[LLMNodeInterface]] = {}
    nodes: dict[str, Type[LLMNodeInterface]] = {}

    @abstractmethod
    def run(self) -> str:
        """
        The LLM interface logic should be implemented here.
        """
        pass

    def safe_run(self):
        try:
            return self.run()
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__}: {e}")
            raise LLMChatInterfaceException(e)

    @classmethod
    def get_available_nodes(cls) -> dict[str, Type[LLMNodeInterface]]:
        return {**cls.edge_nodes, **cls.nodes}

    def instantiate_edge_node(self, node_key: str, *args, **kwargs):
        node_class = self.edge_nodes[node_key]
        usage_prompt_schema, state_modifier_schema = self.get_dynamic_prompt_schemas(
            node_key, node_class
        )
        return node_class(
            usage_prompt_schema=usage_prompt_schema,
            state_modifier_schema=state_modifier_schema,
            *args,
            **kwargs,
        )

    def get_nodes(self, *args, **kwargs):
        nodes = {}
        for node_key, node_class in self.nodes.items():
            try:
                usage_prompt_schema, state_modifier_schema = self.get_dynamic_prompt_schemas(
                    node_key, node_class
                )
            except Exception as e:
                usage_prompt_schema, state_modifier_schema = None, None
                logger.exception(f"Error in _maybe_override_prompt_schemas for {node_key}: {e}")
            nodes[node_key] = self.instantiate_node(
                node_class,
                usage_prompt_schema=usage_prompt_schema,
                state_modifier_schema=state_modifier_schema,
                *args,
                **kwargs,
            )
        return nodes

    def get_dynamic_prompt_schemas(
        self, node_key: str, node_class: Type[LLMNodeInterface]
    ) -> Tuple[BasePromptSchema, Union[list[BasePromptSchema], BasePromptSchema]]:
        from baseapp_ai_langkit.runners.models import (
            LLMRunner,
            LLMRunnerNode,
            LLMRunnerNodeUsagePrompt,
        )

        runner_record = LLMRunner.get_runner_instance_from_runner_class(self.__class__)
        if not runner_record:
            return None, None

        try:
            node_record = runner_record.nodes.get(node=node_key)
        except LLMRunnerNode.DoesNotExist:
            return None, None

        try:
            usage_prompt_record = node_record.usage_prompt
            usage_prompt_schema = usage_prompt_record.get_prompt_schema()
        except LLMRunnerNodeUsagePrompt.DoesNotExist:
            usage_prompt_schema = None

        state_modifiers = node_record.state_modifiers.all()
        state_modifier_schema = node_class.get_static_state_modifier_list()
        for state_modifier in state_modifiers:
            if isinstance(node_class.state_modifier_schema, list):
                state_modifier_schema[state_modifier.index] = state_modifier.get_prompt_schema()
            else:
                state_modifier_schema = state_modifier.get_prompt_schema()
        return usage_prompt_schema, state_modifier_schema

    def instantiate_node(self, node_class: Type[LLMNodeInterface], *args, **kwargs):
        return node_class(*args, **kwargs)


class BaseChatInterface(BaseRunnerInterface):
    def __init__(self, session: ChatSession, user_input: str):
        self.session = session
        self.user_input = user_input
