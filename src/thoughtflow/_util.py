"""
Internal utilities for ThoughtFlow.

This module contains helper functions used internally by ThoughtFlow.
These are NOT part of the public API and may change without notice.

Note: The underscore prefix indicates this is internal/private.
"""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def get_timestamp() -> float:
    """Get current timestamp in seconds since epoch.

    Returns:
        Current time as a float.
    """
    return time.time()


def get_timestamp_ms() -> int:
    """Get current timestamp in milliseconds since epoch.

    Returns:
        Current time in milliseconds as an integer.
    """
    return int(time.time() * 1000)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Values from `override` take precedence. Nested dicts are merged recursively.

    Args:
        base: The base dictionary.
        override: The dictionary to merge on top.

    Returns:
        A new merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate a string to a maximum length.

    Args:
        s: The string to truncate.
        max_length: Maximum length (including suffix).
        suffix: Suffix to add if truncated.

    Returns:
        The truncated string.
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> T:
    """Retry a function with exponential backoff.

    Note: This is an EXPLICIT retry mechanism - callers must opt-in.
    ThoughtFlow does not retry implicitly.

    Args:
        func: The function to retry.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.

    Returns:
        The function's return value.

    Raises:
        Exception: The last exception if all retries fail.
    """
    last_exception: Exception | None = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(min(delay, max_delay))
                delay *= 2  # Exponential backoff

    raise last_exception  # type: ignore[misc]
