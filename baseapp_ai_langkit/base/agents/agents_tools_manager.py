from abc import ABC, abstractmethod
from typing import List, Tuple, Type

from baseapp_ai_langkit.tools.models import InlineTool
from baseapp_ai_langkit.vector_stores.models import DefaultVectorStore


class AgentsToolsManager(ABC):
    # TODO: Reevaluate this class. These tools require a vector store, but the vector store is not always needed.
    tools_list: List[Type[InlineTool]] = []

    @abstractmethod
    def get_vector_store_key(self, tool_class: Type[InlineTool]) -> str:
        """
        Args:
            tool_class (Type[InlineTool]): The tool class (extending InlineTool) that can be used to compound the vector store key.
        """
        pass

    def get_tools(self) -> List[InlineTool]:
        """Retrieves the tools instances for the given tools list."""
        return [
            tool_class(vector_store=self.get_vector_store(tool_class))
            for tool_class in self.tools_list
        ]

    def get_vector_store(self, tool_class: Type[InlineTool]) -> Tuple[DefaultVectorStore, bool]:
        """
        Args:
            tool_class (Type[InlineTool]): The tool class (extending InlineTool) that can be used to compound the vector store key.
        """
        try:
            return DefaultVectorStore.objects.get(name=self.get_vector_store_key(tool_class)), False
        except DefaultVectorStore.DoesNotExist:
            return self.create_vector_store(tool_class), True

    def create_vector_store(self, tool_class: Type[InlineTool]) -> DefaultVectorStore:
        """
        Args:
            tool_class (Type[InlineTool]): The tool class (extending InlineTool) that can be used to compound the vector store key.
        """
        return DefaultVectorStore.objects.create(
            name=self.get_vector_store_key(tool_class),
        )
