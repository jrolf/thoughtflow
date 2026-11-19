"""
Variable substitution utilities for ACTION primitives.

Handles {variable} placeholder substitution from MEMORY.
"""

from __future__ import annotations

import re


_ACTION_SUB_RE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute(value, memory, strict=False):
    """
    Substitute ``{identifier}`` placeholders with values from ``memory``.

    Only valid Python identifier placeholders (``{var_name}``) are matched, and
    doubled braces (``{{`` / ``}}``) unescape to literal braces so raw JSON
    objects inside ``POST`` bodies, ``WRITE`` payloads, or ``RUN`` commands are
    never consumed or corrupted (#33).

    Args:
        value: The value to process (``str``, ``callable``, ``dict``, ``list``,
            or scalar).
        memory: ``MEMORY`` instance to retrieve variables from.
        strict (bool): When ``True``, raise ``KeyError`` if a referenced
            ``{identifier}`` variable is missing from ``memory``. When ``False``
            (default), missing identifier placeholders are left intact as
            ``'{identifier}'`` rather than silently erased.

    Returns:
        The value with declared placeholders substituted.
    """
    if value is None:
        return None
    
    if callable(value):
        return value(memory)
    
    if isinstance(value, str):
        return _substitute_string(value, memory, strict=strict)
    
    if isinstance(value, dict):
        return {k: substitute(v, memory, strict=strict) for k, v in value.items()}
    
    if isinstance(value, list):
        return [substitute(item, memory, strict=strict) for item in value]
    
    # Return as-is for other types (int, float, bool, etc.)
    return value


def _lookup_memory_var(memory, var_name):
    """Return ``(found, value)`` for ``var_name`` on ``memory``."""
    if memory is None:
        return False, None
    if hasattr(memory, "has_var") and callable(getattr(memory, "has_var", None)):
        if not memory.has_var(var_name):
            return False, None
        return True, memory.get_var(var_name)
    if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
        val = memory.get_var(var_name)
        return (val is not None), val
    if hasattr(memory, "vars") and isinstance(memory.vars, dict):
        if var_name in memory.vars:
            return True, memory.vars[var_name]
    return False, None


def _substitute_string(text, memory, strict=False):
    """
    Substitute ``{identifier}`` placeholders in a string without consuming JSON braces.
    """
    def replacer(match):
        whole = match.group(0)
        if whole == "{{":
            return "{"
        if whole == "}}":
            return "}"

        var_name = match.group(1)
        found, val = _lookup_memory_var(memory, var_name)
        if not found or val is None:
            if strict:
                raise KeyError(
                    "Missing memory variable '{}' in action parameter substitution".format(
                        var_name
                    )
                )
            return whole
        return str(val)

    return _ACTION_SUB_RE.sub(replacer, text)


def resolve_value(value, memory, default=None, strict=False):
    """
    Resolve a value that may be static, a callable, or contain placeholders.
    
    This is a convenience wrapper around substitute() that also handles
    the default case when the result is None or empty.
    
    Args:
        value: Value to resolve.
        memory: MEMORY instance.
        default: Default value if result is None or empty string.
        strict (bool): Raise ``KeyError`` when an identifier placeholder is unset.
    
    Returns:
        Resolved value, or default if result is None/empty.
    """
    result = substitute(value, memory, strict=strict)
    if result is None or result == '':
        return default
    return result
