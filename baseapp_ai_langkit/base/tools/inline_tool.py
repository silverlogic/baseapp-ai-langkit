from langchain.tools import StructuredTool

from baseapp_ai_langkit.base.tools.base_tool import AbstractBaseTool


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
