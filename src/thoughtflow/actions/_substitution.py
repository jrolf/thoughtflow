"""
Variable substitution utilities for ACTION primitives.

Handles {variable} placeholder substitution from MEMORY.
"""

from __future__ import annotations

import re


def substitute(value, memory):
    """
    Substitute {variable} placeholders with values from memory.
    
    Args:
        value: The value to process. Can be:
            - str: Replace {var} with memory.get_var(var)
            - callable: Call with memory and return result
            - dict: Recursively substitute all values
            - list: Recursively substitute all elements
            - other: Return as-is
        memory: MEMORY instance to retrieve variables from.
    
    Returns:
        The value with all placeholders substituted.
    
    Example:
        >>> substitute("Hello {name}!", memory)  # memory has name="World"
        'Hello World!'
        >>> substitute(lambda m: m.get_var("count") * 2, memory)
        20  # if count=10
    """
    if value is None:
        return None
    
    if callable(value):
        return value(memory)
    
    if isinstance(value, str):
        return _substitute_string(value, memory)
    
    if isinstance(value, dict):
        return {k: substitute(v, memory) for k, v in value.items()}
    
    if isinstance(value, list):
        return [substitute(item, memory) for item in value]
    
    # Return as-is for other types (int, float, bool, etc.)
    return value


def _substitute_string(text, memory):
    """
    Substitute {variable} placeholders in a string.
    
    Args:
        text: String with {variable} placeholders.
        memory: MEMORY instance.
    
    Returns:
        String with placeholders replaced by memory values.
        Missing variables are left as empty strings.
    """
    # Find all {variable} patterns
    pattern = re.compile(r'\{([^}]+)\}')
    
    def replacer(match):
        var_name = match.group(1)
        if hasattr(memory, 'get_var') and callable(getattr(memory, 'get_var', None)):
            val = memory.get_var(var_name)
        elif hasattr(memory, 'vars'):
            val = memory.vars.get(var_name)
        else:
            val = None
        
        if val is None:
            return ''
        return str(val)
    
    return pattern.sub(replacer, text)


def resolve_value(value, memory, default=None):
    """
    Resolve a value that may be static, a callable, or contain placeholders.
    
    This is a convenience wrapper around substitute() that also handles
    the default case when the result is None or empty.
    
    Args:
        value: Value to resolve.
        memory: MEMORY instance.
        default: Default value if result is None or empty string.
    
    Returns:
        Resolved value, or default if result is None/empty.
    """
    result = substitute(value, memory)
    if result is None or result == '':
        return default
    return result
