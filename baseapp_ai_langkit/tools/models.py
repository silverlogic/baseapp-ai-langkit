from abc import ABC, abstractmethod
from typing import Type

from django.db import models
from langchain.tools import StructuredTool, Tool
from model_utils.models import TimeStampedModel
from openai import BaseModel

from baseapp_ai_langkit.vector_stores.models import (
    AbstractBaseVectorStore,
    DefaultVectorStore,
)


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


class InlineTool(AbstractBaseTool):
    def to_langchain_tool(self) -> StructuredTool:
        return StructuredTool(
            name=self.name,
            func=self.tool_func,
            description=self.description,
            args_schema=self.args_schema,
        )

    def tool_func(self, *args, **kwargs) -> str:
        return ""


class InlineVectorStoreTool(AbstractBaseTool):
    vector_store: AbstractBaseVectorStore

    def __init__(self, vector_store: AbstractBaseVectorStore, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vector_store = vector_store

    def to_langchain_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self.tool_func,
            description=self.description,
            args_schema=self.args_schema,
        )

    def tool_func(self, input_text: str) -> str:
        results = self.vector_store.similarity_search(input_text)
        return "\n".join([res["content"] for res in results])


class DefaultTool(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    vector_store = models.ForeignKey(
        DefaultVectorStore, on_delete=models.CASCADE, related_name="tools"
    )

    def __str__(self):
        return self.name

    def to_langchain_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self.tool_func,
            description=self.description,
        )

    def tool_func(self, input_text: str) -> str:
        results = self.vector_store.similarity_search(input_text)
        return "\n".join([res["content"] for res in results])
