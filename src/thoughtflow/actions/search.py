"""
SEARCH action - web search across multiple providers.

Supports DuckDuckGo, Brave Search, EXA, and Google Custom Search APIs.
Uses only Python standard library (urllib).
"""

from __future__ import annotations

import os
import urllib.parse

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute
from thoughtflow.actions._http import http_request


def _extract_domain(url):
    """
    Extract the domain from a URL string.

    Strips the scheme and www prefix to produce a clean source label.

    Args:
        url: Full URL string.

    Returns:
        Domain string (e.g. "en.wikipedia.org"), or empty string on failure.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


class SEARCH(ACTION):
    """
    An action that performs web searches across multiple providers.

    SEARCH supports four search providers:
    - DuckDuckGo (free, no API key required)
    - Brave Search (requires API key)
    - EXA (requires API key, semantic search)
    - Google Custom Search (requires API key + search engine ID)

    All results are normalized to a common format regardless of provider.
    Each result contains a core set of fields that are always present plus
    optional enrichment fields that are populated when the provider supplies
    the data.

    Args:
        name (str): Unique identifier for this action.
        provider (str): Search provider:
            - "duckduckgo": Free, no API key (default)
            - "brave": Requires BRAVE_API_KEY
            - "exa": Requires EXA_API_KEY
            - "google": Requires GOOGLE_SEARCH_API_KEY + GOOGLE_SEARCH_CX
        query (str|callable): Search query with optional {variable} placeholders.
        api_key (str): API key for provider. If None, reads from environment:
            - Brave: BRAVE_API_KEY
            - EXA: EXA_API_KEY
            - Google: GOOGLE_SEARCH_API_KEY
        google_cx (str): Google Custom Search engine ID. If None, reads
            GOOGLE_SEARCH_CX from environment. Only used with the google provider.
        max_results (int): Maximum results to return (default: 5).
        timeout (float): Request timeout in seconds (default: 30).
        store_as (str): Memory variable for results (default: "{name}_results").

    Example:
        >>> from thoughtflow.actions import SEARCH
        >>> from thoughtflow import MEMORY

        # DuckDuckGo (no API key needed)
        >>> search = SEARCH(query="python", max_results=3)
        >>> memory = search(MEMORY())
        >>> results = memory.get_var("search_results")

        # Brave Search
        >>> search = SEARCH(
        ...     provider="brave",
        ...     query="{user_question}",
        ... )

        # Google Custom Search
        >>> search = SEARCH(
        ...     provider="google",
        ...     query="machine learning",
        ... )

    Returns:
        dict: Normalized search results::

            {
                "query": "original query",
                "provider": "brave",
                "results": [
                    {
                        "title": "...",
                        "url": "...",
                        "snippet": "...",
                        "rank": 1,
                        "source": "example.com",
                        "date_published": "2026-01-15",
                        "extra": {}
                    },
                    ...
                ],
                "total_found": 12345,
                "timestamp": "2026-03-13T..."
            }
    """

    # Provider configuration
    PROVIDERS = {
        "duckduckgo": {
            "env_key": None,
            "base_url": "https://api.duckduckgo.com/",
        },
        "brave": {
            "env_key": "BRAVE_API_KEY",
            "base_url": "https://api.search.brave.com/res/v1/web/search",
        },
        "exa": {
            "env_key": "EXA_API_KEY",
            "base_url": "https://api.exa.ai/search",
        },
        "google": {
            "env_key": "GOOGLE_SEARCH_API_KEY",
            "base_url": "https://www.googleapis.com/customsearch/v1",
        },
    }

    def __init__(
        self,
        name=None,
        provider="duckduckgo",
        query=None,
        api_key=None,
        google_cx=None,
        max_results=5,
        timeout=30,
        store_as=None,
    ):
        """
        Initialize a SEARCH action.

        Args:
            name: Optional name (defaults to "search").
            provider: Search provider name.
            query: Search query string or callable.
            api_key: API key (or read from environment).
            google_cx: Google Custom Search engine ID (or from env).
            max_results: Maximum number of results to return.
            timeout: Request timeout in seconds.
            store_as: Memory variable name for results.
        """
        if query is None:
            raise ValueError("SEARCH requires 'query' parameter")

        provider = provider.lower()
        if provider not in self.PROVIDERS:
            raise ValueError(
                "Unknown provider '{}'. Supported: {}".format(
                    provider, list(self.PROVIDERS.keys())
                )
            )

        self.provider = provider
        self.query = query
        self.api_key = api_key
        self.google_cx = google_cx
        self.max_results = max_results
        self.timeout = timeout

        name = name or "search"

        super().__init__(
            name=name,
            fn=self._execute,
            result_key=store_as or "{}_results".format(name),
            description="SEARCH: {} web search".format(provider.capitalize())
        )

    def _get_api_key(self, memory):
        """
        Get API key from explicit value or environment.

        Args:
            memory: MEMORY instance (for potential variable lookup).

        Returns:
            str: API key or None.
        """
        if self.api_key:
            return substitute(self.api_key, memory)

        env_key = self.PROVIDERS[self.provider]["env_key"]
        if env_key:
            return os.environ.get(env_key)

        return None

    def _get_google_cx(self, memory):
        """
        Get Google Custom Search engine ID from explicit value or environment.

        Args:
            memory: MEMORY instance (for potential variable lookup).

        Returns:
            str: CX string or None.
        """
        if self.google_cx:
            return substitute(self.google_cx, memory)
        return os.environ.get("GOOGLE_SEARCH_CX")

    def _execute(self, memory, **kwargs):
        """
        Execute the SEARCH action.

        Resolves the query (with variable substitution), validates that required
        credentials are present, then dispatches to the provider-specific method.

        Args:
            memory: MEMORY instance.
            **kwargs: Can override 'query', 'max_results'.

        Returns:
            dict: Normalized search results.
        """
        query = kwargs.get('query', self.query)
        max_results = kwargs.get('max_results', self.max_results)

        query = substitute(query, memory)
        if not query:
            raise ValueError("SEARCH query cannot be empty")
        query = str(query)

        api_key = self._get_api_key(memory)

        # Providers that require an API key
        key_required = {"brave", "exa", "google"}
        if self.provider in key_required and not api_key:
            env_var = self.PROVIDERS[self.provider]["env_key"]
            raise ValueError(
                "SEARCH provider '{}' requires API key. "
                "Set '{}' environment variable "
                "or pass 'api_key' parameter.".format(
                    self.provider, env_var
                )
            )

        if self.provider == "duckduckgo":
            return self._search_duckduckgo(query, max_results)
        elif self.provider == "brave":
            return self._search_brave(query, max_results, api_key)
        elif self.provider == "exa":
            return self._search_exa(query, max_results, api_key)
        elif self.provider == "google":
            cx = self._get_google_cx(memory)
            if not cx:
                raise ValueError(
                    "SEARCH provider 'google' requires a search engine ID. "
                    "Set 'GOOGLE_SEARCH_CX' environment variable "
                    "or pass 'google_cx' parameter."
                )
            return self._search_google(query, max_results, api_key, cx)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _search_duckduckgo(self, query, max_results):
        """
        Search using DuckDuckGo Instant Answer API.

        Note: DuckDuckGo's public API returns instant answers and related topics,
        not traditional web search results. For full web results you would need
        to scrape, which we avoid here.

        Args:
            query: Search query.
            max_results: Maximum results.

        Returns:
            dict: Normalized results.
        """
        from datetime import datetime, timezone

        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }

        url = self.PROVIDERS["duckduckgo"]["base_url"]

        response = http_request(
            url=url,
            method="GET",
            params=params,
            timeout=self.timeout,
            parse_response="json"
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if not response.get("success"):
            return {
                "query": query,
                "provider": "duckduckgo",
                "results": [],
                "total_found": 0,
                "timestamp": now,
                "error": response.get("error"),
            }

        data = response.get("data", {})
        results = []
        rank = 1

        # Abstract (main answer)
        if data.get("Abstract"):
            abstract_url = data.get("AbstractURL", "")
            results.append({
                "title": data.get("Heading", ""),
                "url": abstract_url,
                "snippet": data.get("Abstract", ""),
                "rank": rank,
                "source": _extract_domain(abstract_url),
                "date_published": None,
                "extra": {
                    "abstract_source": data.get("AbstractSource", ""),
                },
            })
            rank += 1

        # Related Topics
        remaining = max_results - len(results)
        for topic in data.get("RelatedTopics", [])[:remaining]:
            if isinstance(topic, dict) and topic.get("FirstURL"):
                topic_url = topic.get("FirstURL", "")
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic_url,
                    "snippet": topic.get("Text", ""),
                    "rank": rank,
                    "source": _extract_domain(topic_url),
                    "date_published": None,
                    "extra": {},
                })
                rank += 1

        # Results
        remaining = max_results - len(results)
        for result in data.get("Results", [])[:remaining]:
            if isinstance(result, dict) and result.get("FirstURL"):
                result_url = result.get("FirstURL", "")
                results.append({
                    "title": result.get("Text", "")[:100],
                    "url": result_url,
                    "snippet": result.get("Text", ""),
                    "rank": rank,
                    "source": _extract_domain(result_url),
                    "date_published": None,
                    "extra": {},
                })
                rank += 1

        return {
            "query": query,
            "provider": "duckduckgo",
            "results": results[:max_results],
            "total_found": len(results),
            "timestamp": now,
        }

    def _search_brave(self, query, max_results, api_key):
        """
        Search using Brave Search API.

        Args:
            query: Search query.
            max_results: Maximum results.
            api_key: Brave API key.

        Returns:
            dict: Normalized results.
        """
        from datetime import datetime, timezone

        url = self.PROVIDERS["brave"]["base_url"]

        response = http_request(
            url=url,
            method="GET",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": min(max_results, 20),
            },
            timeout=self.timeout,
            parse_response="json"
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if not response.get("success"):
            return {
                "query": query,
                "provider": "brave",
                "results": [],
                "total_found": 0,
                "timestamp": now,
                "error": response.get("error"),
            }

        data = response.get("data", {})
        results = []
        web_results = data.get("web", {}).get("results", [])

        for rank, item in enumerate(web_results[:max_results], 1):
            item_url = item.get("url", "")
            results.append({
                "title": item.get("title", ""),
                "url": item_url,
                "snippet": item.get("description", ""),
                "rank": rank,
                "source": _extract_domain(item_url),
                "date_published": item.get("page_age", None),
                "extra": {
                    k: item[k]
                    for k in ("language", "family_friendly", "favicon")
                    if k in item
                },
            })

        total = data.get("web", {}).get("total", len(results))

        return {
            "query": query,
            "provider": "brave",
            "results": results,
            "total_found": total,
            "timestamp": now,
        }

    def _search_exa(self, query, max_results, api_key):
        """
        Search using EXA API (semantic search).

        Args:
            query: Search query.
            max_results: Maximum results.
            api_key: EXA API key.

        Returns:
            dict: Normalized results.
        """
        from datetime import datetime, timezone

        url = self.PROVIDERS["exa"]["base_url"]

        response = http_request(
            url=url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            data={
                "query": query,
                "numResults": max_results,
                "useAutoprompt": True,
            },
            timeout=self.timeout,
            parse_response="json"
        )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if not response.get("success"):
            return {
                "query": query,
                "provider": "exa",
                "results": [],
                "total_found": 0,
                "timestamp": now,
                "error": response.get("error"),
            }

        data = response.get("data", {})
        results = []
        exa_results = data.get("results", [])

        for rank, item in enumerate(exa_results[:max_results], 1):
            item_url = item.get("url", "")
            results.append({
                "title": item.get("title", ""),
                "url": item_url,
                "snippet": item.get("text", item.get("snippet", "")),
                "rank": rank,
                "source": _extract_domain(item_url),
                "date_published": item.get("publishedDate", None),
                "extra": {
                    k: item[k]
                    for k in ("score", "author")
                    if k in item
                },
            })

        return {
            "query": query,
            "provider": "exa",
            "results": results,
            "total_found": len(results),
            "timestamp": now,
        }

    def _search_google(self, query, max_results, api_key, cx):
        """
        Search using Google Custom Search JSON API.

        Google limits results to 10 per request. If max_results exceeds 10
        a second page is fetched automatically.

        Args:
            query: Search query.
            max_results: Maximum results (capped at 20 in practice).
            api_key: Google API key.
            cx: Custom Search engine ID.

        Returns:
            dict: Normalized results.
        """
        from datetime import datetime, timezone

        url = self.PROVIDERS["google"]["base_url"]
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        results = []
        # Google returns at most 10 per page; fetch up to 2 pages
        pages_needed = 1 if max_results <= 10 else 2

        for page in range(pages_needed):
            start_index = 1 + page * 10
            num = min(max_results - len(results), 10)
            if num <= 0:
                break

            response = http_request(
                url=url,
                method="GET",
                params={
                    "key": api_key,
                    "cx": cx,
                    "q": query,
                    "num": num,
                    "start": start_index,
                },
                timeout=self.timeout,
                parse_response="json"
            )

            if not response.get("success"):
                if not results:
                    return {
                        "query": query,
                        "provider": "google",
                        "results": [],
                        "total_found": 0,
                        "timestamp": now,
                        "error": response.get("error"),
                    }
                break

            data = response.get("data", {})
            items = data.get("items", [])

            for item in items:
                item_url = item.get("link", "")
                # Google embeds page metadata in the "pagemap" field
                pagemap = item.get("pagemap", {})
                metatags = {}
                if pagemap.get("metatags"):
                    metatags = pagemap["metatags"][0]

                date_published = (
                    metatags.get("article:published_time")
                    or metatags.get("og:updated_time")
                    or item.get("snippet", "")[:0]  # empty fallback
                ) or None

                results.append({
                    "title": item.get("title", ""),
                    "url": item_url,
                    "snippet": item.get("snippet", ""),
                    "rank": len(results) + 1,
                    "source": item.get("displayLink", _extract_domain(item_url)),
                    "date_published": date_published,
                    "extra": {
                        k: item[k]
                        for k in ("mime", "fileFormat", "formattedUrl")
                        if k in item
                    },
                })

            if len(results) >= max_results:
                break

        # Total from Google's search information
        total_str = "0"
        if response.get("data", {}).get("searchInformation"):
            total_str = response["data"]["searchInformation"].get(
                "totalResults", "0"
            )
        try:
            total_found = int(total_str)
        except (ValueError, TypeError):
            total_found = len(results)

        return {
            "query": query,
            "provider": "google",
            "results": results[:max_results],
            "total_found": total_found,
            "timestamp": now,
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        """
        Serialize SEARCH to dictionary.

        Note: API keys and google_cx are not serialized for security.

        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "SEARCH"
        base["provider"] = self.provider
        base["max_results"] = self.max_results
        base["timeout"] = self.timeout
        if not callable(self.query):
            base["query"] = self.query
        return base

    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct SEARCH from dictionary.

        Args:
            data: Dictionary representation.
            **kwargs: Can include 'api_key' and 'google_cx'.

        Returns:
            SEARCH: Reconstructed instance.
        """
        search = cls(
            name=data.get("name"),
            provider=data.get("provider", "duckduckgo"),
            query=data.get("query"),
            api_key=kwargs.get("api_key"),
            google_cx=kwargs.get("google_cx"),
            max_results=data.get("max_results", 5),
            timeout=data.get("timeout", 30),
            store_as=data.get("result_key"),
        )
        if data.get("id"):
            search.id = data["id"]
        return search

    def __repr__(self):
        if callable(self.query):
            query_repr = "<callable>"
        else:
            q = str(self.query)
            query_repr = repr(q[:30] + "..." if len(q) > 30 else q)
        return "SEARCH(name='{}', provider='{}', query={})".format(
            self.name, self.provider, query_repr
        )

    def __str__(self):
        if callable(self.query):
            return "SEARCH [{}] <dynamic query>".format(self.provider)
        preview = str(self.query)[:30]
        if len(str(self.query)) > 30:
            preview += "..."
        return "SEARCH [{}]: {}".format(self.provider, preview)
