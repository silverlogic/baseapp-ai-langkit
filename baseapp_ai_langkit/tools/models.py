from abc import ABC, abstractmethod

from django.db import models
from langchain.tools import Tool
from model_utils.models import TimeStampedModel

from baseapp_ai_langkit.vector_stores.models import (
    AbstractBaseVectorStore,
    DefaultVectorStore,
)


class AbstractBaseTool(ABC):
    """
    Base class for tools that process input data and provide insights.
    """

    name: str
    description: str
    # TODO: Add the args schema here.
    vector_store: AbstractBaseVectorStore

    def __init__(self, name: str, description: str, vector_store: AbstractBaseVectorStore):
        self.name = name
        self.description = description
        self.vector_store = vector_store

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


class InMemoryTool(AbstractBaseTool):
    def to_langchain_tool(self) -> Tool:
        return Tool(
            name=self.name,
            func=self.tool_func,
            description=self.description,
        )

    def tool_func(self, input_text: str) -> str:
        results = self.vector_store.similarity_search(input_text)
        return "\n".join([res["content"] for res in results])


class InlineTool(InMemoryTool):
    """
    Inline tools must have their name and description set inline in the class.
    """

    # TODO: The VectorStore is not always needed. It should be optional.

    def __init__(self, vector_store: AbstractBaseVectorStore):
        self.vector_store = vector_store


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
