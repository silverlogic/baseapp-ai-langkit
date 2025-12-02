import logging
from typing import List, Optional, Type

from django.utils.translation import gettext_lazy as _
from langchain.schema import AIMessage
from langchain.tools import Tool
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from baseapp_ai_langkit.base.agents.base_agent import BaseAgent
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.tools.inline_tool import InlineTool
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer

logger = logging.getLogger(__name__)


class LangGraphAgent(LLMNodeInterface, BaseAgent):
    """
    LangGraphAgent is an agent that utilizes a LangGraph model to generate responses to user queries by leveraging available tools.
    It extends both the LLMNodeInterface and BaseAgent classes, integrating their functionalities.

    This agent is designed to work with a language model and can maintain a checkpointer for state management, allowing it to save and restore its state during interactions.

    Args:
        llm (BaseLanguageModel): The language model to use for generating responses.
        config (dict): The configuration for the agent, which may include various settings for its operation.
        tools (List[Tool]): A list of tools available to the agent for assisting in generating responses.
        checkpointer (Optional[LangGraphCheckpointer]): An optional checkpointer for managing the agent's state.
        state_modifier_schema (Optional[BasePromptSchema]): The schema for the agent's base prompt, which can be set during initialization or statically.
        usage_prompt_schema (Optional[BasePromptSchema]): The schema for the usage prompt, which can also be set during initialization or statically.
        debug (bool): A flag indicating whether to run the agent in debug mode, providing additional logging and information.

    Raises:
        ValueError: If `llm`, `tools`, or other required parameters are not provided during initialization.
    """

    checkpointer: Optional[LangGraphCheckpointer]
    debug: bool

    tools_list: List[Type[InlineTool]] = []

    def __init__(
        self,
        tools_list: List[Type[InlineTool]] = None,
        checkpointer: Optional[LangGraphCheckpointer] = None,
        debug: Optional[bool] = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if tools_list:
            self.tools_list = tools_list

        self.tools = self.get_tools()
        self.validate_tools()

        self.checkpointer = checkpointer
        self.debug = debug

    def get_tools(self) -> List[Tool]:
        tools = []
        for tool_class in self.tools_list:
            try:
                tool = self.initialize_tool(tool_class)
                tools.append(tool.to_langchain_tool())
            except Exception as e:
                logger.error("Failed to initialize tool %s: %s", tool_class.__name__, str(e))
                raise
        return tools

    def initialize_tool(self, tool_class: Type[InlineTool]) -> InlineTool:
        """Override this method to send custom arguments to the tool constructor."""
        return tool_class()

    def update_agent(self, state_modifier: Optional[SystemMessage]):
        self.agent_executor = create_react_agent(
            model=self.llm,
            tools=self.tools,
            debug=self.debug,
            state_modifier=state_modifier,
            checkpointer=self.checkpointer,
        )

    def invoke(self, messages: List[AnyMessage], state: dict = {}) -> AIMessage:
        state_modifiers = self.get_state_modifier_list()
        for state_modifier in state_modifiers:
            state_modifier.placeholders_data.update(state)

        state_modifiers_system_message = self.get_state_modifier_system_message()

        self.update_agent(
            state_modifiers_system_message[0] if len(state_modifiers_system_message) > 0 else None
        )

        try:
            messages = state_modifiers_system_message[1:] + messages
            response = self.agent_executor.invoke(
                {"messages": messages}, config=self.config, stream_mode="values"
            )

            response_text = response["messages"][-1].content

            return AIMessage(content=response_text)
        except Exception as e:
            logger.error(
                "Unexpected error occurred: %s | Input: %s | Tools: %s",
                e,
                messages,
                [tool.name for tool in self.tools],
            )
            raise Exception(_("An unexpected error occurred. Please try again."))
