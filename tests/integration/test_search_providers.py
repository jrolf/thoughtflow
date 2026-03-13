"""
Integration tests for SEARCH action providers.

These tests make real HTTP calls to search APIs. They are SKIPPED by default
and only run when:
1. THOUGHTFLOW_INTEGRATION_TESTS=1 environment variable is set
2. The required API key environment variable is set (e.g., BRAVE_API_KEY)

These tests verify that:
- Our HTTP request formatting is correct for each provider
- Response normalization handles real API responses properly
- Enriched fields (source, date_published, extra) are populated correctly

Running Integration Tests:
    # Run all search integration tests
    THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_search_providers.py -v

    # Run just Brave tests
    THOUGHTFLOW_INTEGRATION_TESTS=1 BRAVE_API_KEY=xxx pytest tests/integration/test_search_providers.py::TestBraveSearchIntegration -v

Note: Some of these tests incur API costs. Use sparingly.
"""

from __future__ import annotations

import os

import pytest

from thoughtflow import MEMORY
from thoughtflow.actions import SEARCH


# ============================================================================
# Skip Markers
# ============================================================================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason=(
            "Integration tests disabled. "
            "Set THOUGHTFLOW_INTEGRATION_TESTS=1 to enable."
        ),
    ),
]


# ============================================================================
# Brave Search Integration Tests
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("BRAVE_API_KEY"),
    reason="BRAVE_API_KEY not set",
)
class TestBraveSearchIntegration:
    """
    Real API tests for Brave Search integration.

    Requires a valid BRAVE_API_KEY environment variable.
    """

    def test_basic_search(self):
        """
        Verify SEARCH can call the Brave API and return normalized results.

        Searches for a well-known topic to ensure we get results back.
        Validates that all normalized fields are present and populated.
        """
        search = SEARCH(
            query="Python programming language",
            provider="brave",
            max_results=3,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        assert result["provider"] == "brave"
        assert result["query"] == "Python programming language"
        assert len(result["results"]) > 0
        assert len(result["results"]) <= 3
        assert "timestamp" in result
        assert "error" not in result

        # Validate normalized result structure
        first = result["results"][0]
        assert first["rank"] == 1
        assert first["title"]
        assert first["url"].startswith("http")
        assert first["snippet"]
        assert first["source"]
        assert isinstance(first["extra"], dict)

    def test_max_results_honored(self):
        """
        Verify that the max_results parameter limits the number of results.
        """
        search = SEARCH(
            query="Python tutorials",
            provider="brave",
            max_results=2,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        assert len(result["results"]) <= 2

    def test_enriched_fields_populated(self):
        """
        Verify that Brave results include source and extra metadata.

        The source field should be a clean domain string, and extra
        should contain provider-specific metadata when available.
        """
        search = SEARCH(
            query="Wikipedia Python programming",
            provider="brave",
            max_results=5,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        for item in result["results"]:
            assert "source" in item
            assert item["source"]
            assert isinstance(item["extra"], dict)

    def test_obscure_query(self):
        """
        Verify that an unusual query returns gracefully (possibly empty results).
        """
        search = SEARCH(
            query="xyzzy123absurdquery999",
            provider="brave",
            max_results=3,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        assert result["provider"] == "brave"
        assert isinstance(result["results"], list)
        assert "error" not in result


# ============================================================================
# DuckDuckGo Integration Tests (no API key needed)
# ============================================================================


class TestDuckDuckGoIntegration:
    """
    Real API tests for DuckDuckGo Instant Answer API.

    DuckDuckGo does not require an API key. Note that the Instant Answer
    API returns structured answers rather than traditional web results, so
    some queries may return empty results.
    """

    def test_basic_search(self):
        """
        Verify SEARCH can call DuckDuckGo and return normalized results.

        Uses a well-known topic that is likely to produce an abstract answer.
        """
        search = SEARCH(
            query="Python programming language",
            provider="duckduckgo",
            max_results=5,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        assert result["provider"] == "duckduckgo"
        assert result["query"] == "Python programming language"
        assert isinstance(result["results"], list)
        assert "timestamp" in result
        assert "error" not in result

    def test_enriched_fields_present(self):
        """
        Verify that DuckDuckGo results include the enriched schema fields.

        Even if some fields are None, the keys should be present.
        """
        search = SEARCH(
            query="Albert Einstein",
            provider="duckduckgo",
            max_results=3,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        for item in result["results"]:
            assert "source" in item
            assert "date_published" in item
            assert "extra" in item


# ============================================================================
# Google Custom Search Integration Tests (placeholder)
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("GOOGLE_SEARCH_API_KEY") or not os.getenv("GOOGLE_SEARCH_CX"),
    reason="GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_CX not set",
)
class TestGoogleSearchIntegration:
    """
    Real API tests for Google Custom Search integration.

    Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX environment variables.
    """

    def test_basic_search(self):
        """Verify SEARCH can call Google Custom Search and return results."""
        search = SEARCH(
            query="Python programming",
            provider="google",
            max_results=3,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        assert result["provider"] == "google"
        assert len(result["results"]) > 0
        assert "error" not in result

        first = result["results"][0]
        assert first["title"]
        assert first["url"].startswith("http")
        assert first["source"]


# ============================================================================
# EXA Integration Tests (placeholder)
# ============================================================================


@pytest.mark.skipif(
    not os.getenv("EXA_API_KEY"),
    reason="EXA_API_KEY not set",
)
class TestEXASearchIntegration:
    """
    Real API tests for EXA semantic search integration.

    Requires EXA_API_KEY environment variable.
    """

    def test_basic_search(self):
        """Verify SEARCH can call EXA and return normalized results."""
        search = SEARCH(
            query="Python machine learning frameworks",
            provider="exa",
            max_results=3,
        )
        memory = search(MEMORY())
        result = memory.get_var("search_results")

        assert result["provider"] == "exa"
        assert len(result["results"]) > 0
        assert "error" not in result
