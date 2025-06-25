from abc import ABC, abstractmethod
from typing import Type

from langchain.tools import Tool
from openai import BaseModel


class AbstractBaseTool(ABC):
    """
    Base class for tools that process input data and provide insights.
    The class properties can be set during initialization or loaded from the class (static).
    """

    name: str
    description: str
    args_schema: Type[BaseModel] = None

    def __init__(
        self, name: str = None, description: str = None, args_schema: Type[BaseModel] = None
    ):
        if name:
            self.name = name
        if description:
            self.description = description
        if args_schema:
            self.args_schema = args_schema

    @abstractmethod
    def tool_func(self, input_text: str) -> str:
        """
        Process the input text and return insights or results.

        Args:
            input_text (str): The input text to process.

        Returns:
            str: The processed output or insights.
        """
        pass

    @abstractmethod
    def to_langchain_tool(self) -> Tool:
        """
        Convert the tool to a Langchain tool for use in agents.

        Returns:
            Tool: The Langchain tool representation.
        """
        pass
