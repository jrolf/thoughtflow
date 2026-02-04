"""
Tool registry for ThoughtFlow.

Provides an explicit registry for tools. This is optional - you can
also pass tools directly to agents. The registry is useful for
organizing and discovering available tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thoughtflow.tools.base import Tool


class ToolRegistry:
    """Registry for managing available tools.

    The registry provides a central place to register and lookup tools.
    This is completely optional - ThoughtFlow doesn't require using a registry.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(calculator_tool)
        >>> registry.register(web_search_tool)
        >>>
        >>> # Get a tool by name
        >>> calc = registry.get("calculator")
        >>>
        >>> # Get all tools
        >>> all_tools = registry.list()
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: The tool to register.

        Raises:
            ValueError: If a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                "Use replace=True to override."
            )
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name.

        Args:
            name: Name of the tool to unregister.

        Raises:
            KeyError: If no tool with that name exists.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        del self._tools[name]

    def get(self, name: str) -> Tool:
        """Get a tool by name.

        Args:
            name: Name of the tool.

        Returns:
            The registered Tool.

        Raises:
            KeyError: If no tool with that name exists.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def list(self) -> list[Tool]:
        """List all registered tools.

        Returns:
            List of all registered tools.
        """
        return list(self._tools.values())

    def names(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    def to_openai_tools(self) -> list[dict]:
        """Convert all tools to OpenAI format.

        Returns:
            List of tool dicts in OpenAI format.
        """
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def to_anthropic_tools(self) -> list[dict]:
        """Convert all tools to Anthropic format.

        Returns:
            List of tool dicts in Anthropic format.
        """
        return [tool.to_anthropic_tool() for tool in self._tools.values()]

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
