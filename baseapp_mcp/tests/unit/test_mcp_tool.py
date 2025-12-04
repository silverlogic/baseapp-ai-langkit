from unittest import mock

import pytest
from django.test import override_settings

from baseapp_mcp import exceptions
from baseapp_mcp.logs.models import MCPLog
from baseapp_mcp.rate_limits.models import TokenUsage
from baseapp_mcp.tools import MCPTool

MCPDataError = exceptions.MCPDataError
MCPRateError = exceptions.MCPRateError
MCPValidationError = exceptions.MCPValidationError

pytestmark = pytest.mark.django_db


class TestMCPTool:
    """Test the MCPTool base class."""

    class MockTool(MCPTool):
        """Mock tool for testing."""

        name = "mock_tool"
        description = "A mock tool for testing"

        def tool_func_core(self, *args, **kwargs):
            return {"result": "success"}

    class MockToolWithTokens(MCPTool):
        """Mock tool that simulates LLM token usage."""

        name = "mock_tool_with_tokens"
        description = "A mock tool with token usage"

        def __init__(self, user_identifier: str):
            super().__init__(user_identifier, uses_tokens=True)

        def tool_func_core(self, *args, **kwargs):
            # Simulate LLM response
            mock_response = mock.Mock()
            mock_response.response_metadata = {
                "usage": {
                    "total_tokens": 100,
                    "prompt_tokens": 60,
                    "completion_tokens": 40,
                }
            }
            self.add_token_usage(mock_response)
            return {"result": "success"}

    class MockToolWithTransformer(MCPTool):
        """Mock tool that simulates transformer calls."""

        name = "mock_tool_with_transformer"
        description = "A mock tool with transformer calls"

        def __init__(self, user_identifier: str):
            super().__init__(user_identifier, uses_transformer_calls=True)

        def tool_func_core(self, *args, **kwargs):
            self.add_transformer_calls(1)
            return {"result": "success"}

    class MockToolWithSimplifiedResponse(MCPTool):
        """Mock tool that returns tuple (response, simplified_response)."""

        name = "mock_tool_simplified"
        description = "A mock tool with simplified response"

        def tool_func_core(self, query: str, top_k: int, options: dict = None):
            full_response = {"query": query, "results": [(n, "bla") for n in range(top_k)]}
            simplified = {"query": query, "num_results": top_k}
            return full_response, simplified

    class MockToolThatRaisesValidationError(MCPTool):
        """Mock tool that raises validation error."""

        name = "mock_validation_error"
        description = "A mock tool that raises validation error"

        def tool_func_core(self, value: str):
            if not value:
                raise MCPValidationError("Value cannot be empty")
            return {"result": "success"}

    class MockToolThatRaisesDataError(MCPTool):
        """Mock tool that raises data error."""

        name = "mock_data_error"
        description = "A mock tool that raises data error"

        def tool_func_core(self, id: str):
            raise MCPDataError(f"Document with ID {id} not found")

    def test_initialization_mock_tool(self):
        """Test MCPTool initialization."""
        tool = self.MockTool(user_identifier="test@example.com")

        assert tool.user_identifier == "test@example.com"
        assert tool.uses_tokens is False
        assert tool.uses_transformer_calls is False
        assert tool.total_tokens == 0
        assert tool.prompt_tokens == 0
        assert tool.completion_tokens == 0
        assert tool.transformer_calls == 0

    def test_initialization_mock_tool_with_tokens(self):
        """Test MCPTool initialization."""
        tool = self.MockToolWithTokens(user_identifier="test@example.com")

        assert tool.user_identifier == "test@example.com"
        assert tool.uses_tokens is True
        assert tool.uses_transformer_calls is False
        assert tool.total_tokens == 0
        assert tool.prompt_tokens == 0
        assert tool.completion_tokens == 0
        assert tool.transformer_calls == 0

    def test_initialization_mock_tool_with_transformer(self):
        """Test MCPTool initialization."""
        tool = self.MockToolWithTransformer(user_identifier="test@example.com")

        assert tool.user_identifier == "test@example.com"
        assert tool.uses_tokens is False
        assert tool.uses_transformer_calls is True
        assert tool.total_tokens == 0
        assert tool.prompt_tokens == 0
        assert tool.completion_tokens == 0
        assert tool.transformer_calls == 0

    def test_extract_token_usage_openai_format(self):
        """Test token extraction from OpenAI response format."""
        tool = self.MockTool(user_identifier="test@example.com")

        mock_response = mock.Mock()
        mock_response.response_metadata = {
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }
        }

        tokens = tool._extract_token_usage(mock_response)

        assert tokens["total_tokens"] == 150
        assert tokens["prompt_tokens"] == 100
        assert tokens["completion_tokens"] == 50

    def test_extract_token_usage_anthropic_format(self):
        """Test token extraction from Anthropic response format."""
        tool = self.MockTool(user_identifier="test@example.com")

        class AnthropicUsage:
            input_tokens = 80
            output_tokens = 40

        mock_response = mock.Mock()
        mock_response.response_metadata = None
        mock_response.usage = AnthropicUsage()

        tokens = tool._extract_token_usage(mock_response)

        assert tokens["prompt_tokens"] == 80
        assert tokens["completion_tokens"] == 40
        assert tokens["total_tokens"] == 120  # Calculated

    def test_extract_token_usage_no_usage(self):
        """Test token extraction when no usage data available."""
        tool = self.MockTool(user_identifier="test@example.com")

        mock_response = mock.Mock()
        mock_response.response_metadata = {}
        mock_response.usage = None

        tokens = tool._extract_token_usage(mock_response)

        assert tokens["total_tokens"] == 0
        assert tokens["prompt_tokens"] == 0
        assert tokens["completion_tokens"] == 0

    def test_add_token_usage(self):
        """Test adding token usage from response."""
        tool = self.MockTool(user_identifier="test@example.com")

        mock_response = mock.Mock()
        mock_response.response_metadata = {
            "usage": {
                "total_tokens": 100,
                "prompt_tokens": 60,
                "completion_tokens": 40,
            }
        }

        tool.add_token_usage(mock_response)

        assert tool.total_tokens == 100
        assert tool.prompt_tokens == 60
        assert tool.completion_tokens == 40

        # Add more tokens
        tool.add_token_usage(mock_response)

        assert tool.total_tokens == 200
        assert tool.prompt_tokens == 120
        assert tool.completion_tokens == 80

    def test_add_transformer_calls(self):
        """Test adding transformer calls."""
        tool = self.MockTool(user_identifier="test@example.com")

        tool.add_transformer_calls()
        assert tool.transformer_calls == 1

        tool.add_transformer_calls(3)
        assert tool.transformer_calls == 4

    def test_save_token_usage(self):
        """Test saving token usage to database."""
        tool = self.MockToolWithTokens(user_identifier="test@example.com")
        tool.tool_func()

        usage = TokenUsage.objects.get_monthly_usage("test@example.com")
        assert usage["total_tokens"] == 100
        assert usage["transformer_calls"] == 0

    def test_save_transformer_calls(self):
        """Test saving transformer calls to database."""
        tool = self.MockToolWithTransformer(user_identifier="test@example.com")
        tool.tool_func()

        usage = TokenUsage.objects.get_monthly_usage("test@example.com")
        assert usage["total_tokens"] == 0
        assert usage["transformer_calls"] == 1

    @override_settings(MCP_ENABLE_TOOL_RATE_LIMITING=True)
    @mock.patch("baseapp_mcp.tools.base_mcp_tool._rate_limiter")
    def test_rate_limiting(self, mock_rate_limiter):
        """Test that rate limiting works."""
        from baseapp_mcp.rate_limits.utils import RateLimiter

        # Create a fresh rate limiter with test settings
        test_limiter = RateLimiter(calls=2, period=60)
        mock_rate_limiter.check_rate_limit = test_limiter.check_rate_limit

        user_id = "test@abc.de"

        # First 2 calls should succeed
        tool1 = self.MockTool(user_identifier=user_id)
        tool1.tool_func()

        tool2 = self.MockTool(user_identifier=user_id)
        tool2.tool_func()

        # Third call should raise exception
        tool3 = self.MockTool(user_identifier=user_id)
        with pytest.raises(MCPRateError, match="Tool rate limit exceeded"):
            tool3.tool_func()

    @override_settings(MCP_ENABLE_TOOL_RATE_LIMITING=False)
    def test_rate_limiting_disabled(self):
        """Test that rate limiting can be disabled."""
        user_id = "test@example.com"

        # Should be able to call many times
        for _ in range(10):
            tool = self.MockTool(user_identifier=user_id)
            tool.tool_func()

    @override_settings(
        MCP_ENABLE_MONTHLY_LIMITS=True,
        MCP_MONTHLY_TOKEN_LIMIT=100,
    )
    def test_monthly_token_limit(self):
        """Test monthly token limit enforcement."""
        user_id = "test@example.com"

        # Add tokens to exceed limit
        TokenUsage.objects.add_usage(
            user_identifier=user_id,
            total_tokens=150,
        )

        # Tool with uses_tokens=True should raise exception
        tool = self.MockToolWithTokens(user_identifier=user_id)
        with pytest.raises(MCPRateError, match="Monthly token limit exceeded"):
            tool.tool_func()

    @override_settings(
        MCP_ENABLE_MONTHLY_LIMITS=True,
        MCP_MONTHLY_TOKEN_LIMIT=100,
    )
    def test_monthly_token_limit_not_enforced_when_not_using_tokens(self):
        """Test monthly token limit is not enforced for tools that don't use tokens."""
        user_id = "test@example.com"

        # Add tokens to exceed limit
        TokenUsage.objects.add_usage(
            user_identifier=user_id,
            total_tokens=150,
        )

        # Tool with uses_tokens=False should NOT raise exception
        tool = self.MockTool(user_identifier=user_id)
        result = tool.tool_func()
        assert result == {"result": "success"}

    @override_settings(
        MCP_ENABLE_MONTHLY_LIMITS=True,
        MCP_MONTHLY_TRANSFORMER_CALL_LIMIT=5,
    )
    def test_monthly_transformer_limit(self):
        """Test monthly transformer call limit enforcement."""
        user_id = "test@example.com"

        # Add transformer calls to exceed limit
        TokenUsage.objects.add_usage(
            user_identifier=user_id,
            transformer_calls=10,
        )

        # Tool with uses_transformer_calls=True should raise exception
        tool = self.MockToolWithTransformer(user_identifier=user_id)
        with pytest.raises(MCPRateError, match="Monthly transformer call limit exceeded"):
            tool.tool_func()

    @override_settings(
        MCP_ENABLE_MONTHLY_LIMITS=True,
        MCP_MONTHLY_TRANSFORMER_CALL_LIMIT=5,
    )
    def test_monthly_transformer_limit_not_enforced_when_not_using_transformer(self):
        """Test monthly transformer limit is not enforced for tools that don't use transformer."""
        user_id = "test@example.com"

        # Add transformer calls to exceed limit
        TokenUsage.objects.add_usage(
            user_identifier=user_id,
            transformer_calls=10,
        )

        # Tool with uses_transformer_calls=False should NOT raise exception
        tool = self.MockTool(user_identifier=user_id)
        result = tool.tool_func()
        assert result == {"result": "success"}

    @override_settings(MCP_ENABLE_MONTHLY_LIMITS=False)
    def test_monthly_limits_disabled(self):
        """Test that monthly limits can be disabled."""
        user_id = "test@example.com"

        # Add usage to exceed limits
        TokenUsage.objects.add_usage(
            user_identifier=user_id,
            total_tokens=1000000,
            transformer_calls=1000000,
        )

        # Should still work
        tool = self.MockToolWithTokens(user_identifier=user_id)
        result = tool.tool_func()
        assert result == {"result": "success"}

        tool = self.MockToolWithTransformer(user_identifier=user_id)
        result = tool.tool_func()
        assert result == {"result": "success"}

    def test_different_users_have_separate_usage(self):
        """Test that different users have separate usage tracking."""
        user1 = "user1@example.com"
        user2 = "user2@example.com"

        tool1 = self.MockToolWithTokens(user_identifier=user1)
        tool1.tool_func()

        tool2 = self.MockToolWithTokens(user_identifier=user2)
        tool2.tool_func()
        tool2.tool_func()

        usage1 = TokenUsage.objects.get_monthly_usage(user1)
        usage2 = TokenUsage.objects.get_monthly_usage(user2)

        assert usage1["total_tokens"] == 100
        assert usage2["total_tokens"] == 200

    def test_tool_func_core_not_implemented(self):
        """Test that tool_func_core must be implemented."""
        tool = MCPTool(user_identifier="test@example.com")
        tool.name = "broken tool"

        with pytest.raises(NotImplementedError, match="tool_func_core"):
            tool.tool_func()

    @mock.patch("baseapp_mcp.tools.base_mcp_tool.logger")
    def test_save_token_usage_handles_errors(self, mock_logger):
        """Test that errors in saving token usage are logged but don't crash."""
        tool = self.MockToolWithTokens(user_identifier="test@example.com")

        with mock.patch(
            "baseapp_mcp.rate_limits.models.TokenUsage.objects.add_usage",
            side_effect=Exception("DB error"),
        ):
            # Should not raise exception
            result = tool.tool_func()
            assert result == {"result": "success"}

            # Should log error
            mock_logger.error.assert_called_once()
            assert "Failed to save token usage" in str(mock_logger.error.call_args)

    @mock.patch("baseapp_mcp.tools.base_mcp_tool.logger")
    @override_settings(MCP_ENABLE_MONTHLY_LIMITS=True)
    def test_enforce_monthly_limit_handles_errors(self, mock_logger):
        """Test that errors in checking monthly limits are logged but don't crash."""
        tool = self.MockTool(user_identifier="test@example.com")

        with mock.patch(
            "baseapp_mcp.rate_limits.models.TokenUsage.objects.get_monthly_usage",
            side_effect=Exception("DB error"),
        ):
            # Should not raise exception
            result = tool.tool_func()
            assert result == {"result": "success"}

            # Should log error
            mock_logger.error.assert_called_once()
            assert "Failed to retrieve monthly token usage" in str(mock_logger.error.call_args)

    def test_log_response_creates_mcp_log(self):
        """Test that tool execution creates an MCPLog entry."""
        tool = self.MockTool(user_identifier="test@example.com")
        tool.tool_func(test_arg="test_value")

        # Check log was created
        log = MCPLog.objects.get(tool_name="mock_tool")
        assert log.tool_arguments == {"test_arg": "test_value"}
        assert log.response == {"result": "success"}
        assert log.user_identifier == "test@example.com"

    def test_log_response_with_tokens(self):
        """Test that token usage is logged in MCPLog."""
        tool = self.MockToolWithTokens(user_identifier="test@example.com")
        tool.tool_func()

        log = MCPLog.objects.get(tool_name="mock_tool_with_tokens")
        assert log.total_tokens == 100
        assert log.prompt_tokens == 60
        assert log.completion_tokens == 40

    def test_log_response_with_transformer_calls(self):
        """Test that transformer calls are logged in MCPLog."""
        tool = self.MockToolWithTransformer(user_identifier="test@example.com")
        tool.tool_func()

        log = MCPLog.objects.get(tool_name="mock_tool_with_transformer")
        assert log.transformer_calls == 1

    def test_log_response_with_simplified_response(self):
        """Test that simplified response is logged when tool returns tuple."""
        tool = self.MockToolWithSimplifiedResponse(user_identifier="test@example.com")
        full_response = tool.tool_func(query="test query", top_k=3)

        # Full response is returned
        assert "results" in full_response
        assert len(full_response["results"]) == 3

        # Simplified response is logged
        log = MCPLog.objects.get(tool_name="mock_tool_simplified")
        assert log.response == {"query": "test query", "num_results": 3}
        assert "results" not in log.response  # Full results not logged

    def test_combine_arguments_with_positional_args_only(self):
        """Test that positional arguments are correctly combined."""
        tool = self.MockToolWithSimplifiedResponse(user_identifier="test@example.com")
        tool.tool_func("query_value", 2, {})

        log = MCPLog.objects.get(tool_name="mock_tool_simplified")
        # Arguments should be combined with parameter names from tool_func_core signature
        assert log.tool_arguments == {"query": "query_value", "top_k": 2, "options": {}}

    def test_combine_arguments_with_positional_and_keyword_args(self):
        """Test that positional arguments are correctly combined."""
        tool = self.MockToolWithSimplifiedResponse(user_identifier="test@example.com")
        tool.tool_func("query_value", top_k=5, options={})

        log = MCPLog.objects.get(tool_name="mock_tool_simplified")
        # Arguments should be combined with parameter names from tool_func_core signature
        assert log.tool_arguments == {"query": "query_value", "top_k": 5, "options": {}}

    def test_combine_arguments_with_kwargs_only(self):
        """Test that keyword arguments are correctly logged."""
        tool = self.MockToolWithSimplifiedResponse(user_identifier="test@example.com")
        tool.tool_func(query="query_value", top_k=1)

        log = MCPLog.objects.get(tool_name="mock_tool_simplified")
        assert log.tool_arguments == {"query": "query_value", "top_k": 1}

    @mock.patch("baseapp_mcp.tools.base_mcp_tool.logger")
    def test_log_response_handles_errors(self, mock_logger):
        """Test that logging errors don't crash tool execution."""
        tool = self.MockTool(user_identifier="test@example.com")

        with mock.patch("baseapp_mcp.logs.models.MCPLog.save", side_effect=Exception("DB error")):
            # Should not raise exception
            result = tool.tool_func()
            assert result == {"result": "success"}

            # Should log error
            assert mock_logger.error.called
            assert "Failed to log response" in str(mock_logger.error.call_args)

    @mock.patch("baseapp_mcp.tools.base_mcp_tool.logger")
    def test_validation_error_is_logged_and_reraised(self, mock_logger):
        """Test that validation errors are logged and re-raised."""
        tool = self.MockToolThatRaisesValidationError(user_identifier="test@example.com")

        with pytest.raises(MCPValidationError, match="Value cannot be empty"):
            tool.tool_func(value="")

        # Should log error
        mock_logger.error.assert_called_once()
        assert "Validation error in tool 'mock_validation_error'" in str(
            mock_logger.error.call_args
        )

    @mock.patch("baseapp_mcp.tools.base_mcp_tool.logger")
    def test_data_error_is_logged_and_reraised(self, mock_logger):
        """Test that data errors are logged and re-raised."""
        tool = self.MockToolThatRaisesDataError(user_identifier="test@example.com")

        with pytest.raises(MCPDataError, match="Document with ID 123 not found"):
            tool.tool_func(id="123")

        # Should log error
        mock_logger.error.assert_called_once()
        assert "Data error in tool 'mock_data_error'" in str(mock_logger.error.call_args)

    @mock.patch("baseapp_mcp.tools.base_mcp_tool.logger")
    def test_unexpected_error_is_logged_and_reraised(self, mock_logger):
        """Test that unexpected errors are logged and re-raised."""

        class MockToolWithUnexpectedError(MCPTool):
            name = "mock_unexpected_error"
            description = "A mock tool that raises unexpected error"

            def tool_func_core(self):
                raise ValueError("Unexpected error")

        tool = MockToolWithUnexpectedError(user_identifier="test@example.com")

        with pytest.raises(ValueError, match="Unexpected error"):
            tool.tool_func()

        # Should log error
        mock_logger.error.assert_called_once()
        assert "Unexpected error in tool 'mock_unexpected_error'" in str(
            mock_logger.error.call_args
        )

    def test_no_log_created_when_tool_raises_before_completion(self):
        """Test that no log is created if tool raises exception."""
        tool = self.MockToolThatRaisesValidationError(user_identifier="test@example.com")

        with pytest.raises(MCPValidationError):
            tool.tool_func(value="")

        # No log should be created
        assert MCPLog.objects.filter(tool_name="mock_validation_error").count() == 0

    def test_token_usage_saved_even_when_logging_fails(self):
        """Test that token usage is still saved even if response logging fails."""
        tool = self.MockToolWithTokens(user_identifier="test@example.com")

        with mock.patch("baseapp_mcp.logs.models.MCPLog.save", side_effect=Exception("DB error")):
            result = tool.tool_func()
            assert result == {"result": "success"}

        # Token usage should still be saved
        usage = TokenUsage.objects.get_monthly_usage("test@example.com")
        assert usage["total_tokens"] == 100
