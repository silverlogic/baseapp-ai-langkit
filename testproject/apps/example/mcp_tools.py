import typing as typ

from baseapp_mcp.tools.mcp_tool import MCPTool


class ExampleTool1(MCPTool):
    """
    An example MCPTool that requires no permission
    """

    name = "example_tool_1"
    description = "Example tool 1"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}

    @classmethod
    def get_auth(cls) -> typ.Callable | None:
        return None


class ExampleTool2(MCPTool):
    """`
    An example MCPTool that requires default permission
    """

    name = "example_tool_2"
    description = "Example tool 2"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}


class ExampleTool3(MCPTool):
    """`
    An example MCPTool that requires default permission
    """

    name = "example_tool_3"
    description = "Example tool 3"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}
