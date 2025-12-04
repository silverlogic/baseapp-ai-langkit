"""Utility functions for the MCP application."""

from collections.abc import Mapping
from typing import Optional

from starlette.requests import Request


def sanitize_sensitive_dict(
    data: dict,
    sensitive_keys: set[str],
    mask: str = "__REDACTED__",
) -> dict:
    """
    Sanitize a dictionary by replacing sensitive fields (case-insensitive)
    with a mask. Recursively handles nested dictionaries and lists.

    :param data: Input dictionary to sanitize.
    :param sensitive_keys: Keys to mask.
    :param mask: Value to replace sensitive fields with.
    :return: A sanitized copy of the dictionary.
    """

    if not isinstance(data, Mapping):
        return data

    sensitive = {k.lower() for k in sensitive_keys}
    sanitized = {}

    for key, value in data.items():
        if key.lower() in sensitive:
            sanitized[key] = mask
        elif isinstance(value, Mapping):
            sanitized[key] = sanitize_sensitive_dict(value, sensitive_keys, mask)
        elif isinstance(value, list):
            sanitized[key] = [
                (
                    sanitize_sensitive_dict(item, sensitive_keys, mask)
                    if isinstance(item, Mapping)
                    else item
                )
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def get_user_identifier(request: Optional[Request] = None) -> str:
    """Extract user identifier from access token or request as fallback."""

    # Try OAuth access token first (if available)
    try:
        from fastmcp.server.dependencies import get_access_token

        token = get_access_token()
        if token and token.claims:
            email = token.claims.get("email")
            if email:
                return email

            # Fallback to 'sub' (subject) claim
            sub = token.claims.get("sub")
            if sub:
                return sub
    except Exception:
        pass

    # Fallback to request scope user
    if request:
        try:
            if "user" in request.scope:
                user = request.scope["user"]
                if hasattr(user, "identity") and hasattr(user.identity, "email"):
                    return user.identity.email

                if user and not user.is_anonymous:
                    if hasattr(user, "email") and user.email:
                        return user.email
                    return str(user)
        except Exception:
            pass

        # Final fallback to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host

    return "unknown"


def clean_url(url: str) -> str:
    """Normalize and clean a public URL for lookup.

    - Ensures a scheme is present (defaults to https if missing).
    - Removes query string and fragment.
    - Strips a trailing slash from the path.

    Returns the cleaned URL as a string.
    """

    if not url or not url.strip():
        return url

    from urllib.parse import urlsplit, urlunsplit

    candidate = url.strip()
    parts = urlsplit(candidate)

    if not parts.scheme:
        candidate = "https://" + candidate.lstrip("/")
        parts = urlsplit(candidate)
    path = parts.path.rstrip("/")
    clean_parts = ("https", parts.netloc, path, "", "")
    return urlunsplit(clean_parts)
