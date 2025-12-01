from django.test import override_settings

import pytest


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests in this tests package."""
    with override_settings(
        MCP_ENABLE_TOOL_RATE_LIMITING=False,
        MCP_ENABLE_MONTHLY_LIMITS=False,
    ):
        yield
