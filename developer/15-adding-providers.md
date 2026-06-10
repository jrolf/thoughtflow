# Adding Providers

This guide explains how to add a new LLM (or embedding) provider to ThoughtFlow.

---

## Provider Architecture

The `LLM` class in `src/thoughtflow/llm.py` is a single class that routes to providers based on the `service:model` string. Each provider is one private `_call_<service>` method plus a dispatch entry in `call()`:

```
LLM("myservice:my-model")
       │
       ▼
   LLM.call()                 ← merges params, handles record/stream
       │
       ▼
   _call_myservice()          ← you implement this
       │
       ▼
   _prepare_messages()        ← normalization + PROVIDER_ROLE_MAP translation
   _send_request()            ← shared urllib POST helper
```

`EMBED` in `src/thoughtflow/embed.py` mirrors the same architecture for embedding endpoints. If the provider offers embeddings, add the counterpart there too.

### The Stdlib Constraint

ThoughtFlow has **zero dependencies**. Provider methods must be implemented with `urllib.request` and `json` only — no provider SDKs, no `requests`, no optional extras. Use the shared `_send_request(url, data, headers)` helper for the HTTP POST and JSON parsing.

---

## Step 1: Implement `_call_<service>`

Add a method to `LLM` following the existing pattern (read `_call_groq` for the simplest example):

```python
def _call_myservice(self, msg_list, params):
    url = "https://api.myservice.com/v1/chat/completions"

    output_schema = params.pop('_output_schema', None)
    payload = {
        "model": self.model,
        "messages": self._prepare_messages(msg_list),
        **params
    }
    if output_schema:
        # Use the provider's native structured-output mechanism if it has
        # one; otherwise append self._schema_prompt_instruction(output_schema)
        # to the messages as a fallback.
        payload["response_format"] = {...}

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + self.api_key,
        "Content-Type": "application/json",
    }
    res = self._send_request(url, data, headers)
    return [a["message"]["content"] for a in res.get("choices", [])]
```

Rules the method must follow:

- Always build messages with `self._prepare_messages(msg_list)` — it normalizes structure and applies role translation. Never map roles inline.
- Pop `_output_schema` from params (even if unsupported) so it doesn't leak into the request payload.
- Return `list[str]` — one string per choice.

## Step 2: Add the Dispatch Entry

In `LLM.call()`, add a branch to the service dispatch chain:

```python
elif self.service == 'myservice':
    choices = self._call_myservice(msg_list, call_params)
```

## Step 3: PROVIDER_ROLE_MAP (If Needed)

ThoughtFlow uses internal roles (`action`, `result` for tool traffic) that providers may not accept. If the provider needs translation, add a config entry to `PROVIDER_ROLE_MAP` at the top of `llm.py`:

```python
PROVIDER_ROLE_MAP = {
    ...
    "myservice": {"action": "tool", "result": "tool"},
}
```

Only non-identity mappings are listed; unmapped roles pass through unchanged. Behavior lives in `_map_roles()` — do not add provider conditionals there.

## Step 4: Streaming (Optional)

If the provider supports SSE streaming, extend `_stream()` with the URL/headers/payload for the new service. If not, add it to the fallback branch at the top of `_stream()` so `stream=True` degrades to a single-yield full call. Record/replay works either way — `call()` handles recording above the provider layer.

## Step 5: Unit Tests with a Monkeypatched Transport

Unit tests must not touch the network. Patch the transport (or the provider method) and assert on request construction and response parsing. Follow the patterns in `tests/unit/test_llm.py`:

```python
# tests/unit/test_llm.py

class TestMyServiceProvider:
    def test_request_formatting(self, monkeypatch):
        """_call_myservice must send model, messages, and auth header."""
        captured = {}

        def fake_send(self, url, data, headers):
            captured["url"] = url
            captured["payload"] = json.loads(data)
            captured["headers"] = headers
            return {"choices": [{"message": {"content": "Hi!"}}]}

        monkeypatch.setattr(LLM, "_send_request", fake_send)

        llm = LLM("myservice:my-model", key="test-key")
        result = llm.call([{"role": "user", "content": "Hello"}])

        assert result == ["Hi!"]
        assert captured["payload"]["model"] == "my-model"
        assert "test-key" in captured["headers"]["Authorization"]
```

Also cover: role mapping (send an `action` message and assert the translated role), structured output (`output_schema=` produces the provider's mechanism), and empty/error responses.

## Step 6: Integration Test (Gated)

Add a test class to `tests/integration/test_llm_providers.py`. Integration tests make real API calls, so they are skipped unless explicitly enabled:

```python
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled. Set THOUGHTFLOW_INTEGRATION_TESTS=1 to enable.",
    ),
]
```

Gate additionally on the provider's key env var (e.g. `MYSERVICE_API_KEY`) and keep token limits low — these tests cost money.

```bash
THOUGHTFLOW_INTEGRATION_TESTS=1 MYSERVICE_API_KEY=... pytest tests/integration/test_llm_providers.py -v
```

## Step 7: EMBED Counterpart (If Applicable)

If the provider has an embedding endpoint, mirror Steps 1–6 in `src/thoughtflow/embed.py` (`_call_<service>` method, dispatch entry in `EMBED.call()`) and `tests/unit/test_embed.py`.

## Step 8: Update Documentation

- `primitives/LLM.md` — the canonical API reference. Add the service to the provider table and document any provider-specific params.
- `docs/concepts/llm.md` — add a row to the provider table.
- `primitives/EMBED.md` — if you added embedding support.

---

## Provider Checklist

Before submitting:

- [ ] `_call_<service>` implemented with urllib only (no new dependencies)
- [ ] Dispatch entry added in `LLM.call()`
- [ ] `PROVIDER_ROLE_MAP` entry added (if the provider needs role translation)
- [ ] `_output_schema` handled (native mechanism or prompt-injection fallback)
- [ ] Streaming supported or falls back cleanly
- [ ] Unit tests with monkeypatched transport pass offline
- [ ] Integration test added, gated by `THOUGHTFLOW_INTEGRATION_TESTS=1`
- [ ] `primitives/LLM.md` updated
- [ ] EMBED counterpart added (if the provider has embeddings)

---

## Next Steps

- [13-adding-features.md](13-adding-features.md) - General feature guide
- [12-writing-tests.md](12-writing-tests.md) - Write comprehensive tests
