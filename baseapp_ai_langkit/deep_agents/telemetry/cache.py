"""Prompt-cache accounting for a deep-agent run.

Prompt caching itself comes for free on Anthropic models: deepagents' tail middleware
stack appends ``AnthropicPromptCachingMiddleware``, and a deep agent's prompt is
cache-stable because the todo, skills and filesystem middlewares append only static
text to the system prompt. This module only *measures* it, so a caching regression
shows up as a number rather than as a silent cost increase: on one production
incident ~93% of input tokens were cache reads (billed at 0.1x), turning a ~$150 run
into $11.67.

Caveat worth knowing before reading a zero as a regression: on providers that cache
server-side without reporting through ``input_token_details`` (OpenAI among them), the
middleware is inert and every figure here except ``input_tokens`` / ``output_tokens``
reads 0. That is the provider's accounting, not a broken cache.
"""

from typing import List, TypedDict

from langchain_core.messages import AIMessage, AnyMessage


class CacheUsage(TypedDict):
    """One run's prompt-cache telemetry."""

    cache_read_tokens: int
    cache_creation_tokens: int
    uncached_input_tokens: int
    input_tokens: int
    output_tokens: int
    cache_hit_rate: float


def cache_usage(messages: List[AnyMessage]) -> CacheUsage:
    """Aggregate prompt-cache statistics across the run's model calls.

    ``cache_read`` / ``cache_creation`` come from ``usage_metadata.input_token_details``;
    older langchain-anthropic versions report creation only through the per-TTL
    ``ephemeral_*_input_tokens`` keys, so those are the fallback. ``input_tokens``
    already includes both, so uncached input is the remainder.
    """
    cache_read = cache_creation = input_tokens = output_tokens = 0
    for message in messages:
        if not (isinstance(message, AIMessage) and message.usage_metadata):
            continue
        usage = message.usage_metadata
        details = usage.get("input_token_details") or {}
        cache_read += details.get("cache_read") or 0
        creation = details.get("cache_creation") or 0
        if not creation:
            creation = (details.get("ephemeral_5m_input_tokens") or 0) + (
                details.get("ephemeral_1h_input_tokens") or 0
            )
        cache_creation += creation
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
    return {
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "uncached_input_tokens": max(input_tokens - cache_read - cache_creation, 0),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_hit_rate": round(cache_read / input_tokens, 4) if input_tokens else 0.0,
    }
