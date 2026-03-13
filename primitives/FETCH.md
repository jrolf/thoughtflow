# FETCH

> Generic HTTP client using only Python standard library (urllib).

## Philosophy

Agents need to talk to the web: REST APIs, webhooks, data endpoints. FETCH provides a single, dependency-free way to make HTTP requests. It uses only `urllib` from the standard library, so it runs anywhere Python runs—including constrained environments like AWS Lambda. No requests, httpx, or aiohttp required.

FETCH is an ACTION subclass, so it integrates with memory, logging, and error handling like every other action. Results are stored in memory at a configurable key. Variable substitution in URLs, headers, params, and body lets you build dynamic requests from memory state. Built-in retry with configurable attempts and delay handles transient failures without extra code.

## How It Works

FETCH is constructed with a URL (required), method, headers, params, body, and parsing options. On invocation, `{variable}` placeholders in url, headers, params, and body are resolved from memory. The URL can also be a callable `(memory) -> str` for fully dynamic URLs.

The request is made via the shared `_http.http_request` helper. Response parsing is controlled by `parse`: `"auto"` detects JSON or text from Content-Type; `"json"`, `"text"`, and `"bytes"` force explicit parsing. If retry is configured, failed requests are retried after `retry_delay` seconds until success or max attempts.

The return value is a dict:

```
{
    "status_code": 200,
    "headers": {...},
    "data": <parsed body>,
    "url": "final URL after redirects",
    "elapsed_ms": 123.45,
    "success": True,
    "error": None
}
```

On HTTP errors or network failures, the dict is still returned with `success: False` and an `error` string. FETCH does not raise; the caller inspects the result and decides how to proceed.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `url` | Request URL (required). Supports `{variable}` placeholders or callable `(memory) -> str`. |
| `name` | Identifier for this action (default: `"fetch"`). |
| `method` | HTTP method (default: `"GET"`). |
| `headers` | Request headers dict. Values support `{variable}` substitution. |
| `params` | Query parameters dict, appended to URL. |
| `body` | Request body. Dict is auto-serialized to JSON. Supports `{variable}` substitution. |
| `parse` | Response parsing: `"auto"` (default), `"json"`, `"text"`, or `"bytes"`. |
| `timeout` | Request timeout in seconds (default: 30). |
| `retry` | Number of retry attempts on failure (default: 0). |
| `retry_delay` | Delay between retries in seconds (default: 1.0). |
| `store_as` | Memory variable for response (default: `"{name}_response"`). |

## Usage

```python
from thoughtflow.actions import FETCH
from thoughtflow import MEMORY

# Simple GET request
fetch = FETCH(url="https://api.example.com/data")
memory = fetch(MEMORY())
result = memory.get_var("fetch_response")
print(result["data"], result["elapsed_ms"])

# GET with headers and parameters
fetch = FETCH(
    url="https://api.example.com/search",
    headers={"Authorization": "Bearer {api_key}"},
    params={"q": "{query}", "limit": 10}
)
memory = MEMORY()
memory.set_var("api_key", "sk-...")
memory.set_var("query", "Python")
memory = fetch(memory)

# POST with JSON body
fetch = FETCH(
    url="https://api.example.com/submit",
    method="POST",
    body={"name": "{user_name}", "data": "{payload}"}
)

# With retry logic for flaky endpoints
fetch = FETCH(
    url="https://flaky-api.com/data",
    retry=3,
    retry_delay=2.0
)
```

## Relationship to Other Primitives

- **ACTION**: FETCH is a subclass of ACTION. It inherits memory integration, error handling, execution tracking, and serialization.
- **POST**: POST is a subclass of FETCH with method fixed to POST and a simpler interface for sending data (json, form, raw).
- **NOTIFY**: NOTIFY uses the same `_http.http_request` helper for webhook delivery. FETCH is the general-purpose HTTP primitive; NOTIFY is for fire-and-forget notifications.
- **SEARCH / SCRAPE**: These actions may use FETCH internally or share the same HTTP utilities. FETCH is the low-level building block.
- **MEMORY**: URL, headers, params, and body support `{variable}` substitution from memory. The response is stored at `store_as`.
- **TOOL**: Wrap FETCH in a TOOL to let an LLM decide when to call an API.

## Considerations for Future Development

- Async variant for non-blocking requests in agent loops with many concurrent fetches.
- Request/response interceptors for auth refresh, logging, or rate limiting.
- Connection pooling if urllib ever supports it without third-party deps.
- Explicit support for streaming response bodies (chunked reads).
- Certificate pinning or custom CA bundles for stricter TLS.
