"""
SEARCH action - web search across multiple providers.

Supports DuckDuckGo, Brave Search, and EXA search APIs.
Uses only Python standard library (urllib).
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute
from thoughtflow.actions._http import http_request


class SEARCH(ACTION):
    """
    An action that performs web searches across multiple providers.
    
    SEARCH supports three search providers:
    - DuckDuckGo (free, no API key required)
    - Brave Search (requires API key)
    - EXA (requires API key)
    
    All results are normalized to a common format regardless of provider.
    
    Args:
        name (str): Unique identifier for this action.
        provider (str): Search provider:
            - "duckduckgo": Free, no API key (default)
            - "brave": Requires BRAVE_API_KEY
            - "exa": Requires EXA_API_KEY
        query (str|callable): Search query with optional {variable} placeholders.
        api_key (str): API key for provider. If None, reads from environment:
            - Brave: BRAVE_API_KEY
            - EXA: EXA_API_KEY
        max_results (int): Maximum results to return (default: 5).
        timeout (float): Request timeout in seconds (default: 30).
        store_as (str): Memory variable for results (default: "{name}_results").
    
    Example:
        >>> from thoughtflow.actions import SEARCH
        >>> from thoughtflow import MEMORY
        
        # DuckDuckGo (no API key needed)
        >>> search = SEARCH(
        ...     query="thoughtflow python library",
        ...     max_results=10
        ... )
        >>> memory = search(MEMORY())
        >>> results = memory.get_var("search_results")
        
        # Brave Search with API key
        >>> search = SEARCH(
        ...     provider="brave",
        ...     query="{user_question}",
        ...     api_key="your-brave-api-key"  # or set BRAVE_API_KEY env var
        ... )
        
        # EXA semantic search
        >>> search = SEARCH(
        ...     provider="exa",
        ...     query="machine learning frameworks comparison"
        ... )
    
    Returns:
        dict: Normalized search results:
            {
                "query": "original query",
                "provider": "brave",
                "results": [
                    {"title": "...", "url": "...", "snippet": "...", "rank": 1},
                    ...
                ],
                "total_found": 12345,
                "timestamp": "2026-02-06T..."
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
    }
    
    def __init__(
        self,
        name=None,
        provider="duckduckgo",
        query=None,
        api_key=None,
        max_results=5,
        timeout=30,
        store_as=None,
    ):
        """
        Initialize a SEARCH action.
        
        Args:
            name: Optional name (defaults to "search").
            provider: Search provider name.
            query: Search query.
            api_key: API key (or from environment).
            max_results: Maximum results.
            timeout: Request timeout.
            store_as: Memory variable name.
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
        # Explicit key takes precedence
        if self.api_key:
            return substitute(self.api_key, memory)
        
        # Check environment variable
        env_key = self.PROVIDERS[self.provider]["env_key"]
        if env_key:
            return os.environ.get(env_key)
        
        return None
    
    def _execute(self, memory, **kwargs):
        """
        Execute the SEARCH action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override 'query', 'max_results'.
        
        Returns:
            dict: Normalized search results.
        """
        # Get parameters
        query = kwargs.get('query', self.query)
        max_results = kwargs.get('max_results', self.max_results)
        
        # Resolve query
        query = substitute(query, memory)
        if not query:
            raise ValueError("SEARCH query cannot be empty")
        query = str(query)
        
        # Get API key
        api_key = self._get_api_key(memory)
        
        # Check if API key required
        if self.provider in ("brave", "exa") and not api_key:
            env_var = self.PROVIDERS[self.provider]["env_key"]
            raise ValueError(
                "SEARCH provider '{}' requires API key. "
                "Set '{}' environment variable or pass 'api_key' parameter.".format(
                    self.provider, env_var
                )
            )
        
        # Dispatch to provider-specific method
        if self.provider == "duckduckgo":
            return self._search_duckduckgo(query, max_results)
        elif self.provider == "brave":
            return self._search_brave(query, max_results, api_key)
        elif self.provider == "exa":
            return self._search_exa(query, max_results, api_key)
    
    def _search_duckduckgo(self, query, max_results):
        """
        Search using DuckDuckGo Instant Answer API.
        
        Note: DuckDuckGo's public API returns instant answers and related topics,
        not traditional web search results. For full web results, you would need
        to scrape, which we avoid here.
        
        Args:
            query: Search query.
            max_results: Maximum results.
        
        Returns:
            dict: Normalized results.
        """
        from datetime import datetime, timezone
        
        # DuckDuckGo Instant Answer API
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
        
        if not response.get("success"):
            return {
                "query": query,
                "provider": "duckduckgo",
                "results": [],
                "total_found": 0,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "error": response.get("error")
            }
        
        data = response.get("data", {})
        
        # Parse DuckDuckGo response
        results = []
        rank = 1
        
        # Abstract (main answer)
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", ""),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("Abstract", ""),
                "rank": rank
            })
            rank += 1
        
        # Related Topics
        for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
            if isinstance(topic, dict) and topic.get("FirstURL"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                    "rank": rank
                })
                rank += 1
        
        # Results
        for result in data.get("Results", [])[:max_results - len(results)]:
            if isinstance(result, dict) and result.get("FirstURL"):
                results.append({
                    "title": result.get("Text", "")[:100],
                    "url": result.get("FirstURL", ""),
                    "snippet": result.get("Text", ""),
                    "rank": rank
                })
                rank += 1
        
        return {
            "query": query,
            "provider": "duckduckgo",
            "results": results[:max_results],
            "total_found": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
                "count": min(max_results, 20),  # Brave max is 20
            },
            timeout=self.timeout,
            parse_response="json"
        )
        
        if not response.get("success"):
            return {
                "query": query,
                "provider": "brave",
                "results": [],
                "total_found": 0,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "error": response.get("error")
            }
        
        data = response.get("data", {})
        
        # Parse Brave response
        results = []
        web_results = data.get("web", {}).get("results", [])
        
        for rank, item in enumerate(web_results[:max_results], 1):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
                "rank": rank
            })
        
        return {
            "query": query,
            "provider": "brave",
            "results": results,
            "total_found": data.get("web", {}).get("total", len(results)),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
        
        if not response.get("success"):
            return {
                "query": query,
                "provider": "exa",
                "results": [],
                "total_found": 0,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "error": response.get("error")
            }
        
        data = response.get("data", {})
        
        # Parse EXA response
        results = []
        exa_results = data.get("results", [])
        
        for rank, item in enumerate(exa_results[:max_results], 1):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("text", item.get("snippet", "")),
                "rank": rank
            })
        
        return {
            "query": query,
            "provider": "exa",
            "results": results,
            "total_found": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    
    def to_dict(self):
        """
        Serialize SEARCH to dictionary.
        
        Note: API key is not serialized for security.
        
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
        # Note: api_key is intentionally not serialized
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct SEARCH from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Can include 'api_key'.
        
        Returns:
            SEARCH: Reconstructed instance.
        """
        search = cls(
            name=data.get("name"),
            provider=data.get("provider", "duckduckgo"),
            query=data.get("query"),
            api_key=kwargs.get("api_key"),
            max_results=data.get("max_results", 5),
            timeout=data.get("timeout", 30),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            search.id = data["id"]
        return search
    
    def __repr__(self):
        query = "<callable>" if callable(self.query) else repr(self.query[:30] + "..." if len(str(self.query)) > 30 else self.query)
        return "SEARCH(name='{}', provider='{}', query={})".format(
            self.name, self.provider, query
        )
    
    def __str__(self):
        if callable(self.query):
            return "SEARCH [{}] <dynamic query>".format(self.provider)
        preview = str(self.query)[:30]
        if len(str(self.query)) > 30:
            preview += "..."
        return "SEARCH [{}]: {}".format(self.provider, preview)
