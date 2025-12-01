import time
from collections import defaultdict
from typing import Dict


class RateLimiter:
    """Enforce rate limits per user"""

    def __init__(self, calls: int, period: int):
        self.user_requests: Dict[str, list] = defaultdict(list)
        self.calls = calls
        self.period = period

    def check_rate_limit(self, user_id: str) -> tuple[bool, int, int]:
        """
        Check if user has exceeded rate limit.

        Returns:
            tuple: (is_allowed, remaining_calls, reset_time)
        """
        now = time.time()
        reset_time = int(now + self.period)

        # Clean old requests
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id] if now - req_time < self.period
        ]

        current_count = len(self.user_requests[user_id])
        remaining = self.calls - current_count

        if remaining <= 0:
            return False, 0, reset_time

        # Record this request
        self.user_requests[user_id].append(now)
        return True, remaining - 1, reset_time
