import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from asgiref.sync import sync_to_async
from django.conf import settings

from baseapp_mcp import exceptions as mcp_exceptions
from baseapp_mcp.logs.models import MCPLog
from baseapp_mcp.rate_limits.models import TokenUsage
from baseapp_mcp.rate_limits.utils import RateLimiter
from baseapp_mcp.tools.base_mcp_tool import BaseMCPTool

logger = logging.getLogger(__name__)


calls = settings.MCP_TOOL_RATE_LIMIT_CALLS
period = settings.MCP_TOOL_RATE_LIMIT_PERIOD

# Global rate limiter instance to be used by all MCP tools
_rate_limiter = RateLimiter(calls, period)


class MCPTool(BaseMCPTool, ABC):
    """
    MCP tool with more advanced functionality (token usage logging, rate limiting, replacement of bad characters).

    Provides:
    - Rate limiting per user
    - Token usage tracking per user (persisted to database)
    - Monthly limit checking
    - Character replacement in responses
    """

    # Use tool_func_core for the signature
    method_for_inferring_args_schema: str = "tool_func_core"

    # Whether the tool uses token-based LLM calls
    # (if True, and the token limit is exceeded,
    # an exception is thrown when executing the tool)
    uses_tokens: bool = False

    # Whether the tool uses transformer calls
    # (if True, and the transformer call limit is exceeded,
    # an exception is thrown when executing the tool)
    uses_transformer_calls: bool = False

    def __init__(
        self,
        user_identifier: str = "unknown",
    ):
        """
        Initialize MCPTool with user identifier and reset token counts.

        Args:
            user_identifier: Identifier for the user (optional, defaults to "unknown")
        """
        super().__init__(user_identifier=user_identifier)
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

    def is_monthly_limit_enabled(self) -> bool:
        """Override this in subclasses to enable/disable monthly limit checking."""
        return settings.MCP_ENABLE_MONTHLY_LIMITS

    def _enforce_monthly_limit(self) -> None:
        """Enforce monthly token limit for a user by throwing an exception if exceeded."""
        if not self.is_monthly_limit_enabled():
            return

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

    def is_rate_limit_enabled(self) -> bool:
        """Override this in subclasses to enable/disable rate limiting."""
        return settings.MCP_ENABLE_TOOL_RATE_LIMITING

    def get_rate_limiter(self) -> RateLimiter:
        """Override this in subclasses to use a custom rate limiter."""
        return _rate_limiter

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limit per user by throwing an exception if exceeded."""
        if not self.is_rate_limit_enabled():
            return

        allowed, _, _ = self.get_rate_limiter().check_rate_limit(self.user_identifier)
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
        signature_method = getattr(self, self.method_for_inferring_args_schema)
        sig = inspect.signature(signature_method)
        param_names = list(sig.parameters.keys())

        arguments = {}
        for i, arg in enumerate(args):
            if i < len(param_names):
                arguments[param_names[i]] = arg
        arguments.update(kwargs)
        return arguments

    def _log_response(self, response: Any, arguments: Dict[str, Any]) -> None:
        """Log response and token usage."""
        simplified_response = self.simplify_response(response)
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

    def simplify_response(self, response: Any) -> Any:
        """
        Override this method in subclasses to simplify the response for logging.

        Args:
            response: The tool's response

        Returns:
            Simplified response for logging
        """
        return response

    async def tool_func(self, *args, **kwargs) -> Any:
        """
        Wrapper around tool_func_core to check rate limits and log tool usage.
        """
        # Check rate limit (number of calls per N seconds per user)
        await sync_to_async(self._enforce_rate_limit)()

        # Check token limit (number of tokens used per month per user)
        await sync_to_async(self._enforce_monthly_limit)()

        self._reset_tokens()
        try:
            # Support both sync and async implementations of tool_func_core.
            if inspect.iscoroutinefunction(self.tool_func_core):
                tool_func_core_async = self.tool_func_core
            else:
                tool_func_core_async = sync_to_async(self.tool_func_core)
            response = await tool_func_core_async(*args, **kwargs)
        except mcp_exceptions.MCPValidationError as e:
            logger.error(f"Validation error in tool '{self.name}': {e}", exc_info=True)
            raise e
        except mcp_exceptions.MCPDataError as e:
            logger.error(f"Data error in tool '{self.name}': {e}", exc_info=True)
            raise e
        except mcp_exceptions.MCPRateError as e:
            logger.error(f"Rate limit error in tool '{self.name}': {e}", exc_info=True)
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in tool '{self.name}': {e}", exc_info=True)
            raise e

        try:
            all_arguments = self._combine_arguments(*args, **kwargs)
            await sync_to_async(self._log_response)(response, all_arguments)
        except Exception as e:
            # This function is just for logging, so errors should not affect tool execution
            # We log them, but do not re-raise
            logger.error(f"Failed to log response: {e}", exc_info=True)

        await sync_to_async(self._save_token_usage)()

        return self._clean_response(response)

    def _clean_response(self, response: Any) -> Any:
        """
        Clean the response.

        Calls replace_bad_characters recursively on strings within the response.
        """
        if isinstance(response, str):
            return self.replace_bad_characters(response)
        elif isinstance(response, list):
            return [self._clean_response(item) for item in response]
        elif isinstance(response, dict):
            return {key: self._clean_response(value) for key, value in response.items()}
        return response

    def replace_bad_characters(self, text: str) -> str:
        """
        Replace problematic unicode characters in a string.
        You can override this method in subclasses if needed.

        Args:
            text: Input string

        Returns:
            Cleaned string
        """
        return text.replace("\u2028", "\n").replace("\u2029", "\n")

    @abstractmethod
    def tool_func_core(self, *args, **kwargs) -> Any:
        """
        Override this method in subclasses. Can be async or sync.

        If you want to use elicitation, sampling, or other async MCP features,
        make this method async. In this case, offload long-running sync operations
        (e.g., database queries) to a thread using `sync_to_async`.
        Otherwise, you can implement this method as a regular sync function.

        The method signature (except self) will be used for MCP tool registration.
        Make sure to type all arguments and the return value.

        Example:
        def tool_func_core(
            self,
            query: Annotated[str, "The search query"],
            max_results: Annotated[int, "Maximum number of results"] = 5)
        -> Dict[str, Any]:
            ...
        """
        pass
