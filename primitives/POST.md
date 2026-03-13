# POST

> Convenience wrapper around FETCH for sending data via HTTP POST.

## Philosophy

Many agent operations involve sending data: webhooks, form submissions, API payloads. POST exists so you do not have to remember to set `method="POST"` and `Content-Type` every time. It is a thin wrapper over FETCH with sensible defaults for the common case of "send this data to that URL."

POST inherits everything from FETCH: retry, response parsing, variable substitution, serialization. The only difference is the interface: you pass `data` and `format` instead of `body` and `method`. POST handles encoding (JSON, form, or raw) and sets the appropriate Content-Type header automatically.

## How It Works

POST is a subclass of FETCH. Its constructor sets `method="POST"` and builds headers based on `format`. For `format="json"` (default), it sets `Content-Type: application/json` and passes the data as the body. For `format="form"`, it sets `Content-Type: application/x-www-form-urlencoded` and URL-encodes the data dict. For `format="raw"`, the data is sent as-is with no Content-Type override.

On execution, POST resolves `data` via variable substitution, encodes it according to `format`, and delegates to FETCH's `_execute`. The parent handles the actual HTTP request, retry, and response parsing. The result is the same dict shape as FETCH: `status_code`, `headers`, `data`, `url`, `elapsed_ms`, `success`, `error`.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `url` | Request URL (required). Supports `{variable}` placeholders or callable `(memory) -> str`. |
| `name` | Identifier for this action (default: `"post"`). |
| `data` | Payload to send. Dict, str, or callable `(memory) -> data`. Dict is serialized per format. |
| `headers` | Additional request headers. Content-Type is set automatically based on format. |
| `format` | Payload format: `"json"` (default), `"form"` (URL-encoded), or `"raw"`. |
| `timeout` | Request timeout in seconds (default: 30). |
| `store_as` | Memory variable for response (default: `"{name}_response"`). |

## Usage

```python
from thoughtflow.actions import POST
from thoughtflow import MEMORY

# Simple webhook
post = POST(
    url="https://hooks.example.com/trigger",
    data={"event": "complete", "status": "success"}
)
memory = post(MEMORY())

# Dynamic data from memory
post = POST(
    url="https://api.example.com/submit",
    data=lambda m: {
        "result": m.get_var("result"),
        "timestamp": m.get_var("timestamp")
    }
)

# Form-encoded submission
post = POST(
    url="https://example.com/form",
    data={"name": "{user_name}", "email": "{email}"},
    format="form"
)

# With authentication
post = POST(
    url="https://api.example.com/data",
    data={"query": "{user_query}"},
    headers={"Authorization": "Bearer {api_token}"}
)
```

## Relationship to Other Primitives

- **FETCH**: POST is a subclass of FETCH. It fixes method to POST and simplifies the data-sending interface. Use FETCH when you need other methods (GET, PUT, DELETE) or more control.
- **ACTION**: POST inherits from ACTION via FETCH. Same memory integration, error handling, and serialization.
- **NOTIFY**: NOTIFY uses HTTP POST for webhook delivery. POST is the general "send data" primitive; NOTIFY is for notifications with console/email/webhook dispatch.
- **MEMORY**: Data supports `{variable}` substitution. The response is stored at `store_as`.
- **TOOL**: Wrap POST in a TOOL to let an LLM trigger webhooks or submit data.

## Considerations for Future Development

- Multipart form support for file uploads.
- Optional request signing (e.g. HMAC for webhook verification).
- Batch mode: send multiple payloads in one action (e.g. for bulk APIs).
- Response validation hooks (e.g. require 2xx or retry).
