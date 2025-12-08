import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from django.conf import settings
from langchain.tools import StructuredTool
from pydantic import BaseModel

from baseapp_mcp import exceptions as mcp_exceptions
from baseapp_mcp.logs.models import MCPLog
from baseapp_mcp.rate_limits.models import TokenUsage
from baseapp_mcp.rate_limits.utils import RateLimiter

logger = logging.getLogger(__name__)


calls = settings.MCP_TOOL_RATE_LIMIT_CALLS
period = settings.MCP_TOOL_RATE_LIMIT_PERIOD

# Global rate limiter instance to be used by all MCP tools
_rate_limiter = RateLimiter(calls, period)


class MCPTool(ABC):
    """
    Base class for MCP tools with token usage logging and rate limiting.

    Provides:
    - Rate limiting per user
    - Token usage tracking per user (persisted to database)
    - Monthly limit checking
    """

    name: str
    description: str
    args_schema: type[BaseModel] | None = None

    def __init__(
        self,
        user_identifier: str,
        uses_tokens: bool = False,
        uses_transformer_calls: bool = False,
        name: str | None = None,
        description: str | None = None,
        args_schema: type[BaseModel] | None = None,
    ):
        """
        Initialize MCPTool with user identifier and usage flags.

        Args:
            user_identifier: Identifier for the user, used for rate and token limiting per user
            uses_tokens: Whether the tool uses token-based LLM calls (if True, and the token limit is exceeded, an exception is thrown when executing the tool)
            uses_transformer_calls: Whether the tool uses transformer calls (if True, and the transformer call limit is exceeded, an exception is thrown when executing the tool)
            name: Tool name (optional, defaults to class attribute)
            description: Tool description (optional, defaults to class attribute)
            args_schema: Pydantic model for tool arguments (optional, defaults to class attribute)
        """
        self.user_identifier = user_identifier
        self.uses_tokens = uses_tokens
        self.uses_transformer_calls = uses_transformer_calls
        if name:
            self.name = name
        if description:
            self.description = description
        if args_schema:
            self.args_schema = args_schema
        self._reset_tokens()

    def _reset_tokens(self):
        """Reset internal token usage counters."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.transformer_calls = 0

    def _extract_token_usage(self, response: Any) -> Dict[str, int]:
        """
        Extract token usage from LLM response.

        Args:
            response: Response from LLM (OpenAI, Anthropic, etc.)

        Returns:
            Dict with token counts
        """
        tokens = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

        # OpenAI/LangChain response format
        if hasattr(response, "response_metadata") and isinstance(response.response_metadata, dict):
            usage = response.response_metadata.get("usage", None) or response.response_metadata.get(
                "token_usage", {}
            )
            if isinstance(usage, dict):
                tokens["total_tokens"] = usage.get("total_tokens", 0)
                tokens["prompt_tokens"] = usage.get("prompt_tokens", 0)
                tokens["completion_tokens"] = usage.get("completion_tokens", 0)

        # Direct usage object
        else:
            usage = getattr(response, "usage", None) or getattr(response, "token_usage", None)
            # Try OpenAI naming, fallback to Anthropic naming
            tokens["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or getattr(
                usage, "input_tokens", 0
            )
            tokens["completion_tokens"] = getattr(usage, "completion_tokens", 0) or getattr(
                usage, "output_tokens", 0
            )
            tokens["total_tokens"] = getattr(usage, "total_tokens", 0) or (
                tokens["prompt_tokens"] + tokens["completion_tokens"]
            )

        return tokens

    def add_token_usage(self, response: Any):
        """
        Update internal token usage counters from LLM response.

        Args:
            response: Response from LLM
        """
        tokens = self._extract_token_usage(response)
        self.total_tokens += tokens["total_tokens"]
        self.prompt_tokens += tokens["prompt_tokens"]
        self.completion_tokens += tokens["completion_tokens"]

    def add_transformer_calls(self, count: int = 1):
        """
        Update internal transformer call count.

        Args:
            count: Number of calls to add
        """
        self.transformer_calls += count

    def _save_token_usage(self):
        """
        Save token usage to database.

        Args:
            user_identifier: User identifier
        """
        try:
            if (
                self.total_tokens
                or self.prompt_tokens
                or self.completion_tokens
                or self.transformer_calls
            ):
                TokenUsage.objects.add_usage(
                    user_identifier=self.user_identifier,
                    total_tokens=self.total_tokens,
                    transformer_calls=self.transformer_calls,
                )
        except Exception as e:
            logger.error(f"Failed to save token usage: {e}")

    def _enforce_monthly_limit(self) -> None:
        """Enforce monthly token limit for a user by throwing an exception if exceeded."""

        try:
            token_limit = settings.MCP_MONTHLY_TOKEN_LIMIT
            transformer_call_limit = settings.MCP_MONTHLY_TRANSFORMER_CALL_LIMIT

            usage = TokenUsage.objects.get_monthly_usage(self.user_identifier)
            used_tokens = usage["total_tokens"]
            used_transformer_calls = usage["transformer_calls"]
        except Exception as e:
            logger.error(f"Failed to retrieve monthly token usage: {e}")
            return

        # Only raise token limit exception if the tool uses tokens
        if self.uses_tokens and used_tokens > token_limit:
            raise mcp_exceptions.MCPRateError(
                f"Monthly token limit exceeded: {used_tokens} > {token_limit}"
            )

        # Only raise transformer call limit exception if the tool uses transformer calls
        if self.uses_transformer_calls and used_transformer_calls > transformer_call_limit:
            raise mcp_exceptions.MCPRateError(
                f"Monthly transformer call limit exceeded: {used_transformer_calls} > {transformer_call_limit}"
            )

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limit per user by throwing an exception if exceeded."""

        allowed, _, _ = _rate_limiter.check_rate_limit(self.user_identifier)
        if not allowed:
            raise mcp_exceptions.MCPRateError(
                f"Tool rate limit exceeded. Maximum {calls} tool calls per {period} seconds."
            )

    def _combine_arguments(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Combine positional and keyword arguments of self.tool_func_core into a single dictionary.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Dict with all arguments
        """
        sig = inspect.signature(self.tool_func_core)
        param_names = list(sig.parameters.keys())

        arguments = {}
        for i, arg in enumerate(args):
            if i < len(param_names):
                arguments[param_names[i]] = arg
        arguments.update(kwargs)
        return arguments

    def _log_response(self, simplified_response: Any, arguments: Dict[str, Any]) -> None:
        """Log response and token usage."""
        tokens = (
            {
                "total_tokens": self.total_tokens,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
            }
            if self.uses_tokens
            else {}
        )
        transformer_calls = (
            {"transformer_calls": self.transformer_calls} if self.uses_transformer_calls else {}
        )

        log_entry = MCPLog(
            tool_name=self.name,
            tool_arguments=arguments,
            response=simplified_response,
            user_identifier=self.user_identifier,
            **tokens,
            **transformer_calls,
        )
        log_entry.save()

    def tool_func(self, *args, **kwargs) -> Any:
        """
        Wrapper around tool_func_core to handle token usage logging.
        """
        # Check rate limit (number of calls per N seconds per user)
        if settings.MCP_ENABLE_TOOL_RATE_LIMITING:
            self._enforce_rate_limit()

        # Check token limit (number of tokens used per month per user)
        if settings.MCP_ENABLE_MONTHLY_LIMITS:
            self._enforce_monthly_limit()

        self._reset_tokens()
        try:
            tool_response = self.tool_func_core(*args, **kwargs)
        except mcp_exceptions.MCPValidationError as e:
            logger.error(f"Validation error in tool '{self.name}': {e}")
            raise e
        except mcp_exceptions.MCPDataError as e:
            logger.error(f"Data error in tool '{self.name}': {e}")
            raise e
        except mcp_exceptions.MCPRateError as e:
            logger.error(f"Rate limit error in tool '{self.name}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in tool '{self.name}': {e}")
            raise e

        if isinstance(tool_response, tuple) and len(tool_response) == 2:
            response, simplified_response = tool_response
        else:
            response = tool_response
            simplified_response = tool_response

        try:
            all_arguments = self._combine_arguments(*args, **kwargs)
            self._log_response(simplified_response, all_arguments)
        except Exception as e:
            # This function is just for logging, so errors should not affect tool execution
            # We log them, but do not re-raise
            logger.error(f"Failed to log response: {e}")

        self._save_token_usage()

        return response

    @abstractmethod
    def tool_func_core(self, *args, **kwargs) -> Any:
        """
        Override this method in subclasses.

        return:
            The tool's response.
            Can be a tuple of the form (response, simplified_response_for_logging)
            If the return value is not a tuple of length two, it is assumed that response = simplified_response_for_logging
        """
        pass

    def to_langchain_tool(self) -> StructuredTool:
        """
        Convert the tool to a LangChain StructuredTool for use in agents.

        This method makes MCP tools compatible with baseapp_ai_langkit agents
        that expect InlineTool instances.

        Returns:
            StructuredTool instance that can be used in LangChain agents
        """
        return StructuredTool(
            name=self.name,
            func=self.tool_func,
            description=self.description,
            args_schema=self.args_schema,
        )
