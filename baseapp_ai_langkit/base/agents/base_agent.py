import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from django.utils.translation import gettext_lazy as _
from langchain.agents import AgentExecutor, create_react_agent
from langchain.base_language import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.schema import AIMessage
from langchain.tools import Tool
from langchain_postgres import PostgresChatMessageHistory

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for AI agents that utilize language models, tools, and optional memory systems to process and respond to user inputs.

    Attributes:
        tools (List[Tool]): A list of tools that the agent can utilize to assist in generating responses.
        agent_executor (Optional[AgentExecutor]): The executor responsible for managing the agent's operations.

    Args:
        tools (List[Tool]): A list of tools available to the agent.

    Raises:
        ValueError: If no tools are provided.
    """

    tools: List[Tool]
    agent_executor: Optional[AgentExecutor]

    def __init__(
        self,
        tools: List[Tool],
    ):
        self.tools = tools
        self.validate_tools()

    def validate_tools(self):
        if not self.tools:
            raise ValueError("At least one tool is required.")

    @abstractmethod
    def update_agent(self):
        """
        Update the agent's executor configuration.
        """

    @abstractmethod
    def invoke(self, message: str) -> AIMessage:
        """
        Generate a response to an input message.

        Args:
            message (str): The input message.

        Returns:
            AIMessage: The agent's response.
        """


class DefaultAgent(BaseAgent):
    """
    Default agent that utilizes ReAct prompting to generate responses to user queries by leveraging available tools.

    This agent is designed to interact with a language model and can maintain a memory of past interactions to enhance its responses.

    Args:
        llm (BaseLanguageModel): The language model utilized for generating responses.
        prompt_template (PromptTemplate): The template used to format the agent's prompts.
        tools (List[Tool]): A list of tools that the agent can utilize to assist in generating responses.
        memory (Optional[PostgresChatMessageHistory]): An optional memory component that stores the agent's chat history.

    Raises:
        ValueError: If `llm`, `prompt_template`, or `tools` are not provided during initialization.
    """

    llm: BaseLanguageModel
    memory: Optional[PostgresChatMessageHistory]
    prompt_template: PromptTemplate

    def __init__(
        self,
        llm: BaseLanguageModel,
        prompt_template: PromptTemplate,
        memory: Optional[PostgresChatMessageHistory] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.llm = llm
        self.prompt_template = prompt_template
        self.memory = memory
        self.update_agent()

    def update_agent(self):
        agent = create_react_agent(
            tools=self.tools,
            llm=self.llm,
            prompt=self.prompt_template,
        )

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            stream_runnable=False,
        )

        if self.memory:
            self.agent_executor.memory = self.memory

    def invoke(self, message: str) -> AIMessage:
        if not self.agent_executor:
            raise ValueError("Agent executor is not initialized.")

        try:
            response = self.agent_executor.invoke(
                {
                    "input": message,
                    "chat_history": (self.memory.get_chat_history() if self.memory else []),
                }
            )
            response_text = response.get("output", "")
            return AIMessage(content=response_text)
        except Exception as e:
            logger.error(
                "Unexpected error occurred: %s | Input: %s | Tools: %s",
                e,
                message,
                [tool.name for tool in self.tools],
            )
            raise Exception(_("An unexpected error occurred. Please try again."))
