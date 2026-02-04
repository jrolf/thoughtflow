"""
Base adapter interface for ThoughtFlow.

All provider adapters implement this interface, ensuring a stable
contract across different LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from thoughtflow.message import MessageList


@dataclass
class AdapterConfig:
    """Configuration for an adapter.

    Attributes:
        api_key: API key for the provider (if required).
        base_url: Optional custom base URL for the API.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retries for failed requests.
        default_model: Default model to use if not specified in params.
        extra: Additional provider-specific configuration.
    """

    api_key: str | None = None
    base_url: str | None = None
    timeout: float = 60.0
    max_retries: int = 3
    default_model: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResponse:
    """Response from an adapter completion call.

    Attributes:
        content: The generated text content.
        model: The model that generated the response.
        usage: Token usage information (prompt, completion, total).
        finish_reason: Why the model stopped (stop, length, tool_calls, etc.).
        raw: The raw response from the provider (for debugging).
    """

    content: str
    model: str | None = None
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    raw: Any = None


class Adapter(ABC):
    """Abstract base class for provider adapters.

    Adapters are responsible for:
    - Translating ThoughtFlow's message format to provider-specific format
    - Making API calls to the provider
    - Translating responses back to ThoughtFlow's format
    - Handling provider-specific errors and retries

    Subclasses must implement:
    - `complete()`: Synchronous completion
    - `complete_async()`: Asynchronous completion (optional)
    - `get_capabilities()`: Report adapter capabilities
    """

    def __init__(self, config: AdapterConfig | None = None, **kwargs: Any) -> None:
        """Initialize the adapter.

        Args:
            config: Adapter configuration object.
            **kwargs: Shorthand for config fields (api_key, base_url, etc.)
        """
        if config is None:
            config = AdapterConfig(**kwargs)
        self.config = config

    @abstractmethod
    def complete(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Generate a completion for the given messages.

        Args:
            messages: List of message dicts.
            params: Optional parameters (model, temperature, max_tokens, etc.)

        Returns:
            AdapterResponse with the generated content.

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError

    async def complete_async(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Async version of complete().

        Default implementation calls the sync version.
        Override for true async support.

        Args:
            messages: List of message dicts.
            params: Optional parameters.

        Returns:
            AdapterResponse with the generated content.
        """
        # Default: fall back to sync
        return self.complete(messages, params)

    def get_capabilities(self) -> dict[str, Any]:
        """Get the capabilities of this adapter.

        Returns:
            Dict describing what this adapter supports:
            - streaming: bool
            - tool_calling: bool
            - vision: bool
            - json_mode: bool
            - etc.
        """
        return {
            "streaming": False,
            "tool_calling": False,
            "vision": False,
            "json_mode": False,
        }
