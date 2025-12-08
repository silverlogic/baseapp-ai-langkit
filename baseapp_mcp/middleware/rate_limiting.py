from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from baseapp_mcp.rate_limits.utils import RateLimiter
from baseapp_mcp.utils import get_user_identifier


class UserRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware based on authenticated user."""

    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.rate_limiter = RateLimiter(calls, period)

    async def dispatch(self, request: Request, call_next):
        user_id = get_user_identifier(request)
        allowed, remaining, reset_time = self.rate_limiter.check_rate_limit(user_id)

        # Check if user exceeded rate limit
        if not allowed:
            return JSONResponse(
                {
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.calls} requests per {self.period} seconds allowed",
                    "user": user_id,
                },
                status_code=429,
                headers={
                    "Retry-After": str(self.period),
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response
