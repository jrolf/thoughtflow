"""
Local model adapter for ThoughtFlow.

Provides integration with locally-running models via Ollama, LM Studio,
or other local inference servers.

Requires: pip install thoughtflow[local]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from thoughtflow.adapters.base import Adapter, AdapterConfig, AdapterResponse

if TYPE_CHECKING:
    from thoughtflow.message import MessageList


class LocalAdapter(Adapter):
    """Adapter for locally-running models.

    Supports Ollama, LM Studio, and other OpenAI-compatible local servers.

    Example:
        >>> # Using Ollama
        >>> adapter = LocalAdapter(base_url="http://localhost:11434/v1")
        >>> response = adapter.complete([
        ...     {"role": "user", "content": "Hello!"}
        ... ], params={"model": "llama3"})

        >>> # Using LM Studio
        >>> adapter = LocalAdapter(base_url="http://localhost:1234/v1")

    Attributes:
        config: Adapter configuration.
        client: HTTP client for making requests.
    """

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "llama3"

    def __init__(
        self,
        base_url: str | None = None,
        config: AdapterConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the local adapter.

        Args:
            base_url: URL of the local inference server.
            config: Full adapter configuration.
            **kwargs: Additional config options.
        """
        if config is None:
            config = AdapterConfig(
                base_url=base_url or self.DEFAULT_BASE_URL,
                **kwargs,
            )
        super().__init__(config)
        self._client = None

    @property
    def client(self) -> Any:
        """Lazy-load the HTTP client.

        Returns:
            Ollama client or httpx client instance.

        Raises:
            ImportError: If required packages are not installed.
        """
        if self._client is None:
            # Try Ollama first, fall back to generic OpenAI-compatible client
            try:
                from ollama import Client

                self._client = Client(host=self.config.base_url)
            except ImportError:
                # Fall back to using OpenAI client with custom base_url
                try:
                    from openai import OpenAI

                    self._client = OpenAI(
                        base_url=self.config.base_url,
                        api_key="not-needed",  # Local servers often don't need keys
                    )
                except ImportError as e:
                    raise ImportError(
                        "No local model client available. "
                        "Install with: pip install thoughtflow[local] or thoughtflow[openai]"
                    ) from e
        return self._client

    def complete(
        self,
        messages: MessageList,
        params: dict[str, Any] | None = None,
    ) -> AdapterResponse:
        """Generate a completion using a local model.

        Args:
            messages: List of message dicts.
            params: Optional parameters (model, temperature, etc.)

        Returns:
            AdapterResponse with the generated content.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement actual local model call
        raise NotImplementedError(
            "LocalAdapter.complete() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )

    def get_capabilities(self) -> dict[str, Any]:
        """Get local adapter capabilities.

        Note: Capabilities depend on the specific model being used.

        Returns:
            Dict of supported features.
        """
        return {
            "streaming": True,
            "tool_calling": False,  # Depends on model
            "vision": False,  # Depends on model
            "json_mode": False,
            "seed": True,
        }
