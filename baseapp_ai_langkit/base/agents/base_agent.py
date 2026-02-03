from abc import ABC, abstractmethod
from typing import List

from langchain_core.messages import AIMessage
from langchain_core.tools import Tool


class BaseAgent(ABC):
    """
    Abstract base class for AI agents that utilize language models, tools, and optional memory systems to process and respond to user inputs.

    Attributes:
        tools (List[Tool]): A list of tools that the agent can utilize to assist in generating responses.

    Args:
        tools (List[Tool]): A list of tools available to the agent.

    Raises:
        ValueError: If no tools are provided.
    """

    tools: List[Tool]

    def __init__(
        self,
        tools: List[Tool] = None,
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
