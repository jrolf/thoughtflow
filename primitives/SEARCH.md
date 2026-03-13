# SEARCH

> Multi-provider web search with a normalized result schema.

## Philosophy

An agent that cannot search the web is an agent that cannot learn anything new after its training cutoff. SEARCH makes web search a first-class operation in ThoughtFlow by providing a single, clean interface that abstracts over multiple search providers. Whether you use DuckDuckGo for free, Brave for quality, EXA for semantic search, or Google Custom Search for completeness, the results come back in the same shape. You write your agent logic once and swap providers with a single parameter.

SEARCH is an ACTION subclass, which means it participates in memory, logging, and error handling exactly like every other action. The developer chooses when and how to call it. When an LLM needs to decide to search, wrap SEARCH in a TOOL so the LLM can select it. When a workflow step needs to search, call SEARCH directly.

Every result includes a core set of always-present fields (title, url, snippet, rank) and enrichment fields (source, date_published, extra) that are populated when the provider supplies the data. This "tight core, optional enrichment" pattern means you can write reliable code against the core fields and opportunistically use richer data when it is available.

## How It Works

SEARCH is constructed with a provider name, a query, and optional configuration. On invocation, the query is resolved (supporting `{variable}` placeholders from memory), the API key is retrieved (from the explicit parameter or the environment), and a provider-specific HTTP request is made using the shared `_http.py` helper (stdlib `urllib` only, no dependencies).

The raw response from each provider is then normalized into a common schema:

```
{
    "query": "original query string",
    "provider": "brave",
    "results": [
        {
            "title": "Page Title",
            "url": "https://example.com/page",
            "snippet": "A brief description of the page...",
            "rank": 1,
            "source": "example.com",
            "date_published": "2026-01-15",
            "extra": { ... provider-specific metadata ... }
        },
        ...
    ],
    "total_found": 12345,
    "timestamp": "2026-03-13T12:00:00Z"
}
```

The `source` field is always a clean domain string extracted from the URL. The `date_published` field is populated when the provider returns publication date metadata. The `extra` dict holds provider-specific data (Brave's favicon, EXA's relevance score, Google's file format) without polluting the common schema.

If the API call fails or the key is missing, the result dict is returned with an `error` field instead of raising, consistent with ACTION's error-handling contract.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `provider` | Search provider: `"duckduckgo"` (default, free), `"brave"`, `"exa"`, or `"google"`. |
| `query` | Search query string. Supports `{variable}` placeholders resolved from memory. Can also be a callable `(memory) -> str`. |
| `api_key` | API key for the provider. If not provided, read from environment: `BRAVE_API_KEY`, `EXA_API_KEY`, or `GOOGLE_SEARCH_API_KEY`. |
| `google_cx` | Google Custom Search engine ID. Only used with the `"google"` provider. Falls back to `GOOGLE_SEARCH_CX` environment variable. |
| `max_results` | Maximum number of results to return (default: 5). Brave caps at 20; Google caps at 20 via two pages of 10. |
| `timeout` | Request timeout in seconds (default: 30). |
| `store_as` | Memory variable name for the result (default: `"{name}_results"`). |
| `name` | Identifier for the action (default: `"search"`). |

## Usage

```python
from thoughtflow.actions import SEARCH
from thoughtflow import MEMORY

# DuckDuckGo (no API key needed)
search = SEARCH(query="Python programming", max_results=5)
memory = search(MEMORY())
results = memory.get_var("search_results")
for item in results["results"]:
    print(item["rank"], item["title"], item["source"])

# Brave Search (reads BRAVE_API_KEY from environment)
search = SEARCH(provider="brave", query="machine learning tutorials")
memory = search(MEMORY())
results = memory.get_var("search_results")

# Google Custom Search
search = SEARCH(
    provider="google",
    query="{user_question}",
    max_results=10,
)
memory = MEMORY()
memory.set_var("user_question", "best Python web frameworks 2026")
memory = search(memory)

# EXA semantic search
search = SEARCH(provider="exa", query="advances in transformer architectures")
```

## Relationship to Other Primitives

- **ACTION**: SEARCH is a subclass of ACTION. It inherits memory integration, error handling, execution tracking, and serialization.
- **TOOL**: To let an LLM decide when to search, wrap SEARCH in a TOOL so the LLM can select it based on user intent. SEARCH itself is developer-invoked.
- **SCRAPE**: SEARCH finds URLs; SCRAPE fetches and extracts content from those URLs. A common pattern is SEARCH followed by SCRAPE on the top results.
- **MEMORY**: The query can reference memory variables via `{variable}` syntax. Results are stored in memory at the configured `store_as` key.
- **AGENT / WORKFLOW**: Agents and workflows can include SEARCH as a step or as a tool available to the agent loop.

## Considerations for Future Development

- Additional providers could be added (Bing, Perplexity, Serper, Tavily) by implementing a new `_search_<provider>` method and adding the provider to the `PROVIDERS` dict.
- Pagination support for providers that offer it (Google already paginates to 2 pages internally).
- Search filters (date range, site restriction, language, safe search) as additional parameters.
- Caching layer to avoid redundant API calls for repeated queries.
- Rate limiting and quota tracking for providers with usage limits.
