"""
Base tool interface for ThoughtFlow.

Tools are functions with contracts. Tool invocation is an explicit step,
tool results are recorded in the trace, and tools can be simulated/stubbed
for deterministic tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool invocation.

    Attributes:
        success: Whether the tool call succeeded.
        output: The tool's output (if successful).
        error: Error message (if failed).
        metadata: Additional metadata about the call.
    """

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: Any, **metadata: Any) -> ToolResult:
        """Create a successful result.

        Args:
            output: The tool's output.
            **metadata: Additional metadata.

        Returns:
            A successful ToolResult.
        """
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> ToolResult:
        """Create a failed result.

        Args:
            error: Error message.
            **metadata: Additional metadata.

        Returns:
            A failed ToolResult.
        """
        return cls(success=False, error=error, metadata=metadata)


class Tool(ABC):
    """Abstract base class for tools.

    Tools are the mechanism for agents to interact with the outside world.
    Each tool has:
    - A unique name
    - A description (for the LLM to understand when to use it)
    - A schema (JSON Schema for the expected input)
    - A call method that executes the tool

    Example:
        >>> class WebSearch(Tool):
        ...     name = "web_search"
        ...     description = "Search the web for information"
        ...
        ...     def get_schema(self):
        ...         return {
        ...             "type": "object",
        ...             "properties": {
        ...                 "query": {"type": "string"}
        ...             },
        ...             "required": ["query"]
        ...         }
        ...
        ...     def call(self, payload, params=None):
        ...         query = payload["query"]
        ...         # ... perform search ...
        ...         return ToolResult.ok(results)
    """

    # Subclasses should override these
    name: str = "unnamed_tool"
    description: str = "No description provided"

    @abstractmethod
    def call(
        self,
        payload: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute the tool with the given payload.

        Args:
            payload: The input data for the tool.
            params: Optional execution parameters.

        Returns:
            ToolResult indicating success/failure and output.
        """
        raise NotImplementedError

    def get_schema(self) -> dict[str, Any]:
        """Get the JSON Schema for the tool's input.

        Override this to provide a schema for the LLM.

        Returns:
            JSON Schema dict describing expected input.
        """
        return {"type": "object", "properties": {}}

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI tool format.

        Returns:
            Dict in OpenAI's tool specification format.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_schema(),
            },
        }

    def to_anthropic_tool(self) -> dict[str, Any]:
        """Convert to Anthropic tool format.

        Returns:
            Dict in Anthropic's tool specification format.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_schema(),
        }
