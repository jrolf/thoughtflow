"""
OpenAI adapter for ThoughtFlow.

Provides integration with OpenAI's API (GPT-4, GPT-3.5, etc.)

Requires: pip install thoughtflow[openai]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from thoughtflow.adapters.base import Adapter, AdapterConfig, AdapterResponse

if TYPE_CHECKING:
    from thoughtflow.message import MessageList


class OpenAIAdapter(Adapter):
    """Adapter for OpenAI's API.

    Supports GPT-4, GPT-3.5-turbo, and other OpenAI models.

    Example:
        >>> adapter = OpenAIAdapter(api_key="sk-...")
        >>> response = adapter.complete([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
        >>> print(response.content)

    Attributes:
        config: Adapter configuration.
        client: OpenAI client instance (created lazily).
    """

    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: str | None = None,
        config: AdapterConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the OpenAI adapter.

        Args:
            api_key: OpenAI API key. Can also be set via OPENAI_API_KEY env var.
            config: Full adapter configuration.
            **kwargs: Additional config options.
        """
        if config is None:
            config = AdapterConfig(api_key=api_key, **kwargs)
        super().__init__(config)
        self._client = None

    @property
    def client(self) -> Any:
        """Lazy-load the OpenAI client.

        Returns:
            OpenAI client instance.

        Raises:
            ImportError: If openai package is not installed.
        """
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    "OpenAI package not installed. "
                    "Install with: pip install thoughtflow[openai]"
                ) from e

            self._client = OpenAI(
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
        """Generate a completion using OpenAI's API.

        Args:
            messages: List of message dicts.
            params: Optional parameters (model, temperature, max_tokens, etc.)

        Returns:
            AdapterResponse with the generated content.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement actual OpenAI API call
        raise NotImplementedError(
            "OpenAIAdapter.complete() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )

    def get_capabilities(self) -> dict[str, Any]:
        """Get OpenAI adapter capabilities.

        Returns:
            Dict of supported features.
        """
        return {
            "streaming": True,
            "tool_calling": True,
            "vision": True,
            "json_mode": True,
            "seed": True,
        }
