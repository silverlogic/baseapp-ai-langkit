"""
Custom exceptions for MCP tools.
"""


class MCPToolError(Exception):
    """Base exception for all MCP tool errors."""

    def __init__(self, message: str, error_type: str = "tool_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)


class MCPValidationError(MCPToolError):
    """Exception raised for invalid input parameters."""

    def __init__(self, message: str):
        super().__init__(message, error_type="validation_error")


class MCPConfigurationError(MCPToolError):
    """Exception raised for configuration issues (API keys, settings, etc.)."""

    def __init__(self, message: str):
        super().__init__(message, error_type="configuration_error")


class MCPDataError(MCPToolError):
    """Exception raised for data processing or database issues (query failures, data corruption, etc.)."""

    def __init__(self, message: str):
        super().__init__(message, error_type="data_error")


class MCPExternalServiceError(MCPToolError):
    """Exception raised for external service logic errors (API limits, invalid responses, service unavailable, etc.)."""

    def __init__(self, message: str):
        super().__init__(message, error_type="external_service_error")


class MCPRateError(MCPToolError):
    """Exception raised when any rate limit (number of calls per period, token usage per month, etc.) is exceeded"""

    def __init__(self, message: str):
        super().__init__(message, error_type="rate_error")
