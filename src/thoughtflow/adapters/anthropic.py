"""
Anthropic adapter for ThoughtFlow.

Provides integration with Anthropic's API (Claude models).

Requires: pip install thoughtflow[anthropic]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from thoughtflow.adapters.base import Adapter, AdapterConfig, AdapterResponse

if TYPE_CHECKING:
    from thoughtflow.message import MessageList


class AnthropicAdapter(Adapter):
    """Adapter for Anthropic's API.

    Supports Claude 3, Claude 2, and other Anthropic models.

    Example:
        >>> adapter = AnthropicAdapter(api_key="sk-ant-...")
        >>> response = adapter.complete([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
        >>> print(response.content)

    Attributes:
        config: Adapter configuration.
        client: Anthropic client instance (created lazily).
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        api_key: str | None = None,
        config: AdapterConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key. Can also be set via ANTHROPIC_API_KEY env var.
            config: Full adapter configuration.
            **kwargs: Additional config options.
        """
        if config is None:
            config = AdapterConfig(api_key=api_key, **kwargs)
        super().__init__(config)
        self._client = None

    @property
    def client(self) -> Any:
        """Lazy-load the Anthropic client.

        Returns:
            Anthropic client instance.

        Raises:
            ImportError: If anthropic package is not installed.
        """
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise ImportError(
                    "Anthropic package not installed. "
                    "Install with: pip install thoughtflow[anthropic]"
                ) from e

            self._client = Anthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
        return self._client

    def complete(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Generate a completion using Anthropic's API.

        Args:
            messages: List of message dicts.
            params: Optional parameters (model, temperature, max_tokens, etc.)

        Returns:
            AdapterResponse with the generated content.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement actual Anthropic API call
        # Note: Anthropic uses a different message format (system as separate param)
        raise NotImplementedError(
            "AnthropicAdapter.complete() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )

    def get_capabilities(self) -> dict[str, Any]:
        """Get Anthropic adapter capabilities.

        Returns:
            Dict of supported features.
        """
        return {
            "streaming": True,
            "tool_calling": True,
            "vision": True,
            "json_mode": False,  # Anthropic doesn't have native JSON mode
            "seed": False,
        }
