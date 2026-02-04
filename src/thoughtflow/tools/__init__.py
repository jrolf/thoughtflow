"""
Tool interfaces for ThoughtFlow.

Tools are functions with contracts that agents can invoke.
ThoughtFlow makes tool use explicit, testable, and auditable.

Example:
    >>> from thoughtflow.tools import Tool
    >>>
    >>> class Calculator(Tool):
    ...     name = "calculator"
    ...     description = "Perform arithmetic operations"
    ...
    ...     def call(self, payload):
    ...         return eval(payload["expression"])
"""

from __future__ import annotations

from thoughtflow.tools.base import Tool, ToolResult
from thoughtflow.tools.registry import ToolRegistry

__all__ = [
    "Tool",
    "ToolResult",
    "ToolRegistry",
]
