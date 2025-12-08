import time
from unittest import mock

from baseapp_mcp.rate_limits.utils import RateLimiter


class TestRateLimiter:
    """Test cases for RateLimiter class."""

    def test_allows_requests_within_limit(self):
        """Test that requests within the limit are allowed."""
        limiter = RateLimiter(calls=3, period=60)
        user_id = "test@example.com"

        # First 3 requests should be allowed
        allowed, remaining, _ = limiter.check_rate_limit(user_id)
        assert allowed is True
        assert remaining == 2

        allowed, remaining, _ = limiter.check_rate_limit(user_id)
        assert allowed is True
        assert remaining == 1

        allowed, remaining, _ = limiter.check_rate_limit(user_id)
        assert allowed is True
        assert remaining == 0

    def test_blocks_requests_over_limit(self):
        """Test that requests over the limit are blocked."""
        limiter = RateLimiter(calls=2, period=60)
        user_id = "test@example.com"

        # First 2 requests allowed
        limiter.check_rate_limit(user_id)
        limiter.check_rate_limit(user_id)

        # Third request should be blocked
        allowed, remaining, reset_time = limiter.check_rate_limit(user_id)
        assert allowed is False
        assert remaining == 0
        assert reset_time > time.time()

    def test_different_users_have_separate_limits(self):
        """Test that different users have independent rate limits."""
        limiter = RateLimiter(calls=2, period=60)
        user1 = "user1@example.com"
        user2 = "user2@example.com"

        # User 1 uses their limit
        limiter.check_rate_limit(user1)
        limiter.check_rate_limit(user1)
        allowed, _, _ = limiter.check_rate_limit(user1)
        assert allowed is False

        # User 2 should still be allowed
        allowed, remaining, _ = limiter.check_rate_limit(user2)
        assert allowed is True
        assert remaining == 1

    def test_limit_resets_after_period(self):
        """Test that the rate limit resets after the time period."""
        limiter = RateLimiter(calls=2, period=1)  # 1 second period
        user_id = "test@example.com"

        # Use up the limit
        limiter.check_rate_limit(user_id)
        limiter.check_rate_limit(user_id)
        allowed, _, _ = limiter.check_rate_limit(user_id)
        assert allowed is False

        # Wait for period to expire
        time.sleep(1.1)

        # Should be allowed again
        allowed, remaining, _ = limiter.check_rate_limit(user_id)
        assert allowed is True
        assert remaining == 1

    def test_cleans_old_requests(self):
        """Test that old requests are cleaned up."""
        limiter = RateLimiter(calls=3, period=2)
        user_id = "test@example.com"

        # Make 2 requests
        limiter.check_rate_limit(user_id)
        limiter.check_rate_limit(user_id)

        # Wait for requests to expire
        time.sleep(2.1)

        # Make 3 more requests - should all be allowed
        for i in range(3):
            allowed, _, _ = limiter.check_rate_limit(user_id)
            assert allowed is True

    def test_reset_time_is_in_future(self):
        """Test that reset_time is always in the future."""
        limiter = RateLimiter(calls=1, period=60)
        user_id = "test@example.com"

        now = time.time()
        limiter.check_rate_limit(user_id)
        _, _, reset_time = limiter.check_rate_limit(user_id)

        assert reset_time > now
        assert reset_time <= now + 60

    def test_remaining_decrements_correctly(self):
        """Test that remaining calls decrement correctly."""
        limiter = RateLimiter(calls=5, period=60)
        user_id = "test@example.com"

        for expected_remaining in [4, 3, 2, 1, 0]:
            _, remaining, _ = limiter.check_rate_limit(user_id)
            assert remaining == expected_remaining

    def test_handles_multiple_users_simultaneously(self):
        """Test concurrent usage by multiple users."""
        limiter = RateLimiter(calls=2, period=60)
        users = [f"user{i}@example.com" for i in range(5)]

        # Each user should be able to make 2 requests
        for user in users:
            allowed1, _, _ = limiter.check_rate_limit(user)
            allowed2, _, _ = limiter.check_rate_limit(user)
            allowed3, _, _ = limiter.check_rate_limit(user)

            assert allowed1 is True
            assert allowed2 is True
            assert allowed3 is False

    @mock.patch("time.time")
    def test_time_mocking(self, mock_time):
        """Test rate limiter with mocked time."""
        mock_time.return_value = 1000.0

        limiter = RateLimiter(calls=2, period=60)
        user_id = "test@example.com"

        # Make 2 requests at time 1000
        limiter.check_rate_limit(user_id)
        limiter.check_rate_limit(user_id)
        allowed, _, _ = limiter.check_rate_limit(user_id)
        assert allowed is False

        # Move time forward past the period
        mock_time.return_value = 1061.0

        # Should be allowed again
        allowed, _, _ = limiter.check_rate_limit(user_id)
        assert allowed is True
