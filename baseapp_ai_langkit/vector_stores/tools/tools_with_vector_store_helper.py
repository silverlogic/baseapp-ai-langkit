from abc import ABC, abstractmethod
from typing import List, Tuple, Type

from baseapp_ai_langkit.vector_stores.models import DefaultVectorStore
from baseapp_ai_langkit.vector_stores.tools.inline_vector_store_tool import (
    InlineVectorStoreTool,
)


class ToolsWithVectorStoreHelper(ABC):
    @abstractmethod
    def get_vector_store_key(self, tool_class: Type[InlineVectorStoreTool]) -> str:
        """
        Args:
            tool_class (Type[InlineVectorStoreTool]): The tool class (extending InlineVectorStoreTool) that can be used to compound the vector store key.
        """
        pass

    def get_tools(self) -> List[InlineVectorStoreTool]:
        """Retrieves the tools instances for the given tools list."""
        return [
            tool_class(vector_store=self.get_vector_store(tool_class))
            for tool_class in self.tools_list
        ]

    def get_vector_store(
        self, tool_class: Type[InlineVectorStoreTool]
    ) -> Tuple[DefaultVectorStore, bool]:
        """
        Args:
            tool_class (Type[InlineVectorStoreTool]): The tool class (extending InlineVectorStoreTool) that can be used to compound the vector store key.
        """
        try:
            return DefaultVectorStore.objects.get(name=self.get_vector_store_key(tool_class)), False
        except DefaultVectorStore.DoesNotExist:
            return self.create_vector_store(tool_class), True

    def create_vector_store(self, tool_class: Type[InlineVectorStoreTool]) -> DefaultVectorStore:
        """
        Args:
            tool_class (Type[InlineVectorStoreTool]): The tool class (extending InlineVectorStoreTool) that can be used to compound the vector store key.
        """
        return DefaultVectorStore.objects.create(
            name=self.get_vector_store_key(tool_class),
        )
