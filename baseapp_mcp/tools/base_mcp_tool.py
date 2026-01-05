import inspect
from abc import ABC, abstractmethod
from typing import Any

from langchain.tools import StructuredTool

from baseapp_mcp.utils import get_user_identifier


class BaseMCPTool(ABC):
    """
    Base class for MCP tools, providing name, description, and argument schema.

    To create a tool, derive this class and implement `tool_func` (check the README for examples).
    To register this class, say called `YourMCPTool`, as a tool on a DjangoFastMCP server `mcp`,
    use `mcp.register_tool(YourMCPTool)`.
    This will register a tool with name and description taken from the class attributes,
    and argument schema inferred from the method with name `method_for_inferring_args_schema`.

    When the tool gets called by an LLM client, an instance of the tool class will be created,
    and the `tool_func` method will be executed with the provided arguments.
    """

    name: str
    description: str

    # The name of the method that provides the signature for the mcp tool.
    # Contrary to LangChain, fastmcp will automatically infer the argument
    # schema from a method and does not allow an explicit pydantic model.
    method_for_inferring_args_schema: str = "tool_func"

    # Typically, calling read only tools in LLM clients needs no confirmation
    read_only: bool = True

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.annotations = {"readOnlyHint": cls.read_only}

    def __init__(
        self,
        user_identifier: str = "unknown",
    ):
        """
        Initialize MCPTool with user_identifier.

        Args:
            user_identifier: Identifier for the user (optional, defaults to "unknown")
        """
        self.user_identifier = user_identifier

    @abstractmethod
    async def tool_func(self, *args, **kwargs) -> Any:
        """
        The core function of the tool. Must be implemented by subclasses.

        The arguments of the `method_for_inferring_args_schema` method
        must be declared explicitly and typed for proper MCP registration.
        So unless you change this method name in your subclass,
        you cannot use *args or **kwargs as parameters for `tool_func`.
        """
        pass

    @classmethod
    def get_name(cls) -> str:
        """
        Get the name of the tool. You can override this method in subclasses.

        Returns:
            The name of the tool
        """
        return cls.name

    @classmethod
    def get_description(cls) -> str:
        """
        Get the description of the tool. You can override this method in subclasses.

        Returns:
            The description of the tool
        """
        return cls.description

    @classmethod
    def adjust_signature(cls, func: Any) -> Any:
        """
        Copy the signature of `method_for_inferring_args_schema` to the given function,
        excluding the `self` parameter.
        """
        signature_method = getattr(cls, cls.method_for_inferring_args_schema)
        sig = inspect.signature(signature_method)
        params_without_self = list(sig.parameters.values())[1:]
        func.__signature__ = sig.replace(parameters=params_without_self)

        if hasattr(signature_method, "__annotations__"):
            func.__annotations__ = {
                k: v for k, v in signature_method.__annotations__.items() if k != "self"
            }

    @classmethod
    def get_fastmcp_tool_func(cls) -> Any:
        """
        Convert the tool to a typed function that can be registered on a fastmcp server.

        Returns:
            Callable that can be registered as an MCP tool with the same signature as tool_func
        """

        async def fast_mcp_tool_func(**kwargs):
            user_identifier = get_user_identifier()
            tool_instance = cls(user_identifier=user_identifier)
            result = await tool_instance.tool_func(**kwargs)
            return result

        # Set name and docstring for fastmcp registration
        fast_mcp_tool_func.__name__ = cls.get_name()
        fast_mcp_tool_func.__doc__ = cls.get_description()
        cls.adjust_signature(fast_mcp_tool_func)

        return fast_mcp_tool_func

    @classmethod
    def to_langchain_tool(cls, args_schema, tool_func_name: str | None = None) -> StructuredTool:
        """
        Convert the tool to a LangChain StructuredTool for use in agents.

        This method makes MCP tools compatible with baseapp_ai_langkit agents
        that expect InlineTool instances. Since MCP tools don't need an explicit
        args_schema, it must be provided here.

        args:
            args_schema: Pydantic model defining the tool's arguments. This should be
                compatible with the signature of `method_for_inferring_args_schema`.
            tool_func_name (optional): Name of the method to use as the tool function.
                If `None`, defaults to `method_for_inferring_args_schema`.

        Returns:
            StructuredTool instance that can be used in LangChain agents
        """

        if tool_func_name is None:
            tool_func_name = cls.method_for_inferring_args_schema
        tool_func = getattr(cls, tool_func_name)

        return StructuredTool(
            name=cls.get_name(),
            description=cls.get_description(),
            args_schema=args_schema,
            func=tool_func,
        )
