"""
Integration tests for SCRAPE action.

These tests make real HTTP calls to fetch web pages. They are SKIPPED by default
and only run when THOUGHTFLOW_INTEGRATION_TESTS=1 is set.

These tests verify that:
- HTML fetching works against real servers
- Text, markdown, links, and structured extraction work on live HTML
- The _MarkdownExtractor produces sensible output on real-world pages
- The structured mode collects metadata correctly

Running Integration Tests:
    THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_scrape.py -v

Note: These tests require network access but do not incur API costs.
"""

from __future__ import annotations

import os

import pytest

from thoughtflow import MEMORY
from thoughtflow.actions import SCRAPE


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
# Tests against example.com (always available, minimal HTML)
# ============================================================================


class TestScrapeExampleDotCom:
    """
    Integration tests using https://example.com.

    This domain is maintained by IANA and always returns a simple, stable
    HTML page, making it ideal for repeatable integration testing.
    """

    def test_text_extraction(self):
        """
        Verify SCRAPE can fetch example.com and extract readable text.

        The page should contain "Example Domain" as its main heading text.
        """
        scrape = SCRAPE(url="https://example.com", extract="text")
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, str)
        assert "Example Domain" in result

    def test_html_extraction(self):
        """
        Verify SCRAPE returns raw HTML from example.com.
        """
        scrape = SCRAPE(url="https://example.com", extract="html")
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, str)
        assert "<html" in result.lower()
        assert "Example Domain" in result

    def test_links_extraction(self):
        """
        Verify SCRAPE extracts links from example.com.

        example.com has a "More information..." link pointing to IANA.
        """
        scrape = SCRAPE(url="https://example.com", extract="links")
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, list)
        assert len(result) >= 1

        urls = [link["url"] for link in result]
        has_iana_link = any("iana.org" in url for url in urls)
        assert has_iana_link, "Expected a link to iana.org"

    def test_markdown_extraction(self):
        """
        Verify SCRAPE converts example.com HTML to readable markdown.

        The heading "Example Domain" should appear as a markdown heading.
        """
        scrape = SCRAPE(url="https://example.com", extract="markdown")
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, str)
        assert "Example Domain" in result
        # Should contain a markdown link
        assert "](http" in result or "](https" in result

    def test_structured_extraction(self):
        """
        Verify SCRAPE structured mode returns a complete dict from example.com.

        Checks that all standard keys are present and contain reasonable
        values for this simple page.
        """
        scrape = SCRAPE(url="https://example.com", extract="structured")
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, dict)
        assert result["url"] == "https://example.com"

        # Title should be present (example.com has a <title> tag)
        assert result["title"], "Expected a non-empty title"

        # Content should mention "Example Domain"
        assert "Example Domain" in result["content_text"]
        assert "Example Domain" in result["content_markdown"]

        # Links should contain the IANA link
        assert isinstance(result["links"], list)
        assert len(result["links"]) >= 1

        # Word count should be a small positive number
        assert result["word_count"] > 0
        assert result["word_count"] < 500

        # Timestamp should be an ISO string
        assert "T" in result["timestamp"]


# ============================================================================
# Tests against a richer page (Wikipedia)
# ============================================================================


class TestScrapeWikipedia:
    """
    Integration tests using a Wikipedia article.

    Wikipedia pages have rich HTML structure including headings, links,
    images, tables, and extensive metadata -- good for testing extraction
    robustness on real-world content.
    """

    WIKI_URL = "https://en.wikipedia.org/wiki/Python_(programming_language)"

    def test_text_extraction_has_content(self):
        """
        Verify SCRAPE extracts substantial text from a Wikipedia article.
        """
        scrape = SCRAPE(
            url=self.WIKI_URL,
            extract="text",
            timeout=30,
        )
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, str)
        assert len(result) > 500
        assert "Python" in result

    def test_markdown_has_headings(self):
        """
        Verify SCRAPE markdown mode produces headings from a Wikipedia article.

        Wikipedia articles use h2/h3 for section headings, which should appear
        as ## / ### in the markdown output.
        """
        scrape = SCRAPE(
            url=self.WIKI_URL,
            extract="markdown",
            timeout=30,
        )
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, str)
        assert len(result) > 500
        # Should have at least some markdown headings
        assert "##" in result or "# " in result

    def test_structured_has_rich_metadata(self):
        """
        Verify SCRAPE structured mode collects rich metadata from Wikipedia.

        Wikipedia pages have title, description, headings, links, and images.
        """
        scrape = SCRAPE(
            url=self.WIKI_URL,
            extract="structured",
            timeout=30,
        )
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, dict)
        assert result["title"]
        assert "Python" in result["title"]

        # Should have many headings
        assert len(result["headings"]) > 3

        # Should have many links
        assert len(result["links"]) > 10

        # Should have images
        assert len(result["images"]) > 0

        # Word count should be substantial
        assert result["word_count"] > 1000

    def test_links_extraction(self):
        """
        Verify SCRAPE extracts a large number of links from Wikipedia.
        """
        scrape = SCRAPE(
            url=self.WIKI_URL,
            extract="links",
            timeout=30,
        )
        memory = scrape(MEMORY())
        result = memory.get_var("scrape_content")

        assert isinstance(result, list)
        assert len(result) > 50
