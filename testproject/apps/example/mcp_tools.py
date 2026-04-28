from baseapp_mcp.tools.mcp_tool import MCPTool


class ExampleTool1(MCPTool):
    name = "example_tool_1"
    description = "Example tool 1"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}


class ExampleTool2(MCPTool):
    name = "example_tool_2"
    description = "Example tool 2"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}


class ExampleTool3(MCPTool):
    name = "example_tool_3"
    description = "Example tool 3"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}


class ExampleTool4(MCPTool):
    name = "example_tool_4"
    description = "Example tool 4"

    def tool_func_core(self) -> dict[str, str]:
        return {"result": "success"}
