from langchain.tools import Tool

from baseapp_ai_langkit.base.tools.base_tool import AbstractBaseTool
from baseapp_ai_langkit.vector_stores.models import AbstractBaseVectorStore


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
