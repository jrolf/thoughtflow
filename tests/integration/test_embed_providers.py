"""
Integration smoke tests for EMBED provider APIs.

These tests make real HTTP calls. They are skipped unless
THOUGHTFLOW_INTEGRATION_TESTS=1 and the required API key (or local Ollama)
is available.

Running:
    THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_embed_providers.py -v
"""

from __future__ import annotations

import os

import pytest

from thoughtflow import EMBED

from tests.integration.smoke_helpers import assert_embed_smoke, ollama_reachable


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled. Set THOUGHTFLOW_INTEGRATION_TESTS=1 to enable.",
    ),
]


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestOpenAIEmbedIntegration:
    """Smoke OpenAI text-embedding-3-small."""

    def test_single_text_embedding(self):
        embed = EMBED(
            model_id="openai:text-embedding-3-small",
            key=os.getenv("OPENAI_API_KEY"),
        )
        vector = embed.call("integration smoke test")
        assert_embed_smoke(embed, vector, "OpenAI EMBED")
        assert len(vector) >= 100


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set",
)
class TestGeminiEmbedIntegration:
    """Smoke Gemini embeddings (legacy slug aliases to gemini-embedding-001)."""

    def test_text_embedding_004_alias(self):
        embed = EMBED(
            model_id="gemini:text-embedding-004",
            key=os.getenv("GOOGLE_API_KEY"),
        )
        vector = embed.call("integration smoke test")
        assert_embed_smoke(embed, vector, "Gemini EMBED")
        assert len(vector) >= 100


@pytest.mark.skipif(
    not ollama_reachable(),
    reason="Ollama not reachable at OLLAMA_HOST (default http://localhost:11434)",
)
class TestOllamaEmbedIntegration:
    """Smoke local Ollama /api/embed (all-minilm when available)."""

    def test_ollama_embedding(self):
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        embed = EMBED(model_id="ollama:all-minilm:33m", key="")
        vector = embed.call("integration smoke test", {"ollama_url": host})
        assert_embed_smoke(embed, vector, "Ollama EMBED")
        assert len(vector) >= 32


@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set",
)
class TestGroqEmbedIntegration:
    """
    Smoke Groq embeddings when the account exposes an embedding model.

    Groq's public model list may omit embeddings entirely; skip on account/model
    errors rather than failing the suite.
    """

    def test_groq_embedding_when_available(self):
        embed = EMBED(
            model_id="groq:nomic-embed-text",
            key=os.getenv("GROQ_API_KEY"),
        )
        vector = embed.call("integration smoke test")
        assert_embed_smoke(embed, vector, "Groq EMBED")
        assert len(vector) >= 32


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)
class TestOpenRouterEmbedIntegration:
    """Smoke OpenRouter embeddings gateway."""

    def test_openrouter_embedding(self):
        embed = EMBED(
            model_id="openrouter:openai/text-embedding-3-small",
            key=os.getenv("OPENROUTER_API_KEY"),
        )
        vector = embed.call(
            "integration smoke test",
            {
                "referer": "https://github.com/jrolf/thoughtflow",
                "title": "ThoughtFlow",
            },
        )
        assert_embed_smoke(embed, vector, "OpenRouter EMBED")
        assert len(vector) >= 100
