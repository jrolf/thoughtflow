# THOUGHT

> The atomic unit of cognition — the fundamental building block for LLM-based reasoning.

## Philosophy

THOUGHT is the discrete unit of cognition in ThoughtFlow. It answers the question: what is one step of reasoning? The equation is THOUGHT = Prompt + Context + LLM + Parsing + Validation. A thought takes a prompt template, fills it with context from MEMORY, sends it to an LLM, parses the response, validates it, and optionally retries if validation fails. By making this a first-class primitive, ThoughtFlow gives you a composable, traceable way to build multi-step cognitive systems.

THOUGHT exists because raw LLM calls are messy. Models add prose, code fences, and formatting you did not ask for. They sometimes return invalid JSON or miss required keys. THOUGHT encapsulates the full cycle — prompt construction, LLM invocation, parsing, validation, retry — so that higher-level primitives (AGENT, WORKFLOW) can compose clean steps without reimplementing this logic. It also enforces the framework contract: `memory = thought(memory)` or `memory = thought(memory, vars)`.

## How It Works

THOUGHT is callable. When you invoke it with a MEMORY (and optionally a vars dict), it dispatches to one of four operation types: llm_call, memory_query, variable_set, or conditional. For llm_call, it builds messages from the prompt template and context, calls the LLM, parses the response with a built-in or custom parser, validates with a built-in or custom validator, and retries with a repair prompt if validation fails. The result is stored in memory as `{name}_result`.

### llm_call pipeline order

This order is fixed and matters for authoring:

1. Build messages from prompt + MEMORY context
2. Call LLM (optional `on_token` streaming)
3. `parse_response` — schema via `valid_extract` when `parsing_rules` set
4. `validate` — callable or built-in; runs only after parse succeeds (unless `validation_mode='rescue'`)
5. Store result, logs, optional assistant message, reflection

Schema validation and callable validation are **not** parallel gates. A `validation=` lambda does not run when schema rejects the payload unless rescue mode is enabled.

### Default lane vs production lane

**Default lane (no flags):** flat `format` dict, existing retry semantics, failure logs and `{name}_last_error` on MEMORY, assistant messages recorded on failed attempts. Conversation history is included via `MEMORY.get_llm_msgs()` and is never rewritten by prompt templating.

**Production lane (opt-in):** `strict_schema=True`, `validation_mode='rescue'`, `on_failure=`, `hold_msg=True`, `template_mode='substitute'`, `include_history=False`, `oneOf` schema dialect. See [docs/concepts/thought.md](../docs/concepts/thought.md) for the full guide.

### Prompt templates vs conversation history

Template rendering and history inclusion are separate concerns:

- **`template_mode='format'`** (default): renders the configured prompt with `str.format(**ctx)` and raises `TemplateRenderError` before calling the LLM if formatting fails (missing placeholders, malformed braces, or type/index errors). Use `template_mode='substitute'` (or `{{...}}`) when a prompt contains literal JSON braces.
- **`template_mode='substitute'`**: replaces only explicit `{key}` placeholders for keys present in context. Literal JSON braces and unknown placeholders stay untouched; bare words such as `messages` are not replaced unless the template contains `{messages}`.
- **`include_history=True`** (default): prior turns come from `MEMORY.get_llm_msgs()` and are forwarded without template substitution.
- **`include_history=False`**: sends only the configured system prompt plus one rendered user prompt.

Both user and system prompt strings follow the selected rendering mode. Dict-shaped prompts retain their legacy unrendered sections in format mode; substitute mode renders each string section before assembly. MEMORY variables enter template context as their latest values, not their internal event histories. `include_history=False` disables automatic history messages, but an explicit context placeholder such as `{messages}` or `{last_user_msg}` can still place MEMORY content in the configured prompt.

JSON-heavy prompts should prefer `template_mode='substitute'`.

## Schema parsing (`parsing_rules`)

Prompt templates use `{variable}` placeholders filled from memory context. Parsers include text, json, list, custom callables, and schema-based parsing via `valid_extract`.

| Concept | Meaning |
|---------|---------|
| Exemplar `""` or `str` | field must be a string when present |
| Exemplar `0` or `int` | field must be an int when present |
| `"key?"` | key is optional (may be omitted) |
| `"key"` without `?` | key is required |
| `None` exemplar | value must be null — **not** "optional field" |
| `oneOf: [...]` | optional dialect; first matching branch wins |

Exemplar values are type markers only. They are not defaults the model should fall back to.

```python
# Good: optional age, required name
parsing_rules={"kind": "python", "format": {"name": str, "age?": int}}

# Branch-shaped locator (found vs absent)
parsing_rules={
    "kind": "python",
    "format": {
        "oneOf": [
            {"verdict": "found", "matched_span": ""},
            {"verdict": "absent", "note": ""},
        ]
    },
}
```

### Schema dialect additions

Inside `parsing_rules['format']`, a string that names a type is treated as that type: `"int"`, `"str"`, `"float"`, `"bool"`, `"null"`, `"list"`, `"dict"` (plus `"number"`). Join names with a pipe for a union, such as `"int|null"`. `{"enum": ["pos", "neg"]}` accepts only those literals, inline or at the top level (a bare word reply like `pos` is accepted for a top-level enum). Ordinary exemplar strings such as `"Ada"` still mean "any str". On the first attempt THOUGHT appends `Expected format: ...` to the final user message so the model sees the schema before it fails; pass `instruct_schema=False` to turn that off.

### Retry policy

`retry={"on": {"length": "double_budget", "http": "backoff"}, "backoff_base": 0.5, "max_backoff": 8.0, "fallback_llm": other_llm}` is opt-in. On `finish_reason == "length"` the next attempt doubles `max_tokens`; on transport errors it sleeps with exponential backoff; after retries are exhausted one final attempt runs on `fallback_llm` and `{name}_outcome` gains `"used_fallback_llm": True`. Without `retry`, behavior is unchanged.

### Visibility

`visibility="public"` (default) writes the assistant reply to MEMORY. `"internal"` and `"silent"` keep the result in `output_var` but skip the transcript write, so classifier or router thoughts do not leak into chat history. `record_prompt=True` stores the rendered prompt at `{name}_prompt`. When the template references `{last_user_msg}`, the history copy of that message is dropped so the model does not see it twice.

## Validation

Validation is configured via the canonical `validation=` parameter (config alias `validator=`). Accepts built-in strings (`any`, `has_keys:k1,k2`, `list_min_len:N`, `summary_v1`), a callable returning `(bool, why)` or bare `bool`, or a JSON-serializable list of declarative rule dicts (`in`, `non_empty`, `range`, `regex`, `has_keys`):

```python
validation=[
    {"op": "in", "field": "decision", "allowed": ["approve", "deny", "escalate"]},
    {"op": "range", "field": "confidence", "min": 1, "max": 100},
    {"op": "non_empty", "field": "rationale"},
]
```

Declarative rule lists survive `json.dumps(thought.to_dict())` and `THOUGHT.from_dict(...)` with no external function registry. Callable hooks and validators are stripped from `to_dict()["config"]` so JSON export always succeeds. Compressed large objects (`_obj_ref`) stored in `MEMORY` are resolved lazily only when referenced by the prompt or explicit var lists.

`validation_mode='strict'` (default) — schema must pass before callable runs. `validation_mode='rescue'` — on schema miss, structurally parsed payload may be accepted by callable validator.

## Outcomes & Failure Visibility

Every `THOUGHT` (as well as `DECIDE` and `PLAN`) writes a uniform, JSON-safe `{name}_outcome` dict to `MEMORY` on both success and failure (`ok`, `error_class`, `error`, `finish_reason`, `usage`, `attempts`, `validation_messages`), emits `thought_completed` / `thought_failed` via `MEMORY.emit()`, and sets `{name}_attempts` to the total number of attempts executed.

Failed attempts write structured JSON to MEMORY logs (`event: thought_failure`) and update `{name}_last_error`. Optional `on_failure(thought, attempt, failure_kind, reason, raw_response=None)` hook fires per attempt. `failure_kind` / `error_class` values: `template`, `length`, `empty`, `http`, `replay_miss`, `schema`, `validation`, `contract`, `exception`. Prompt rendering errors and `ReplayMissError` fail fast before burning retries.

`hold_msg` defaults to `True` so failed or rejected LLM drafts do not pollute conversation history (pass `hold_msg=False` to record failed assistant messages), and `add_reflection` defaults to `False` so successful runs do not write a duplicate truncated copy of the assistant reply into `MEMORY` reflections.

After retry exhaustion, `{name}_result` is `None` and THOUGHT returns MEMORY without raising. Execution events include `failed: true` when retries were exhausted with an error.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| name | Unique identifier for this thought |
| llm | LLM instance (required for llm_call) |
| prompt | Template string with {variable} placeholders, or dict for variable_set |
| operation | llm_call, memory_query, variable_set, or conditional |
| system_prompt | Optional system prompt for LLM context |
| parser | text, json, list, or callable |
| parsing_rules | Schema for valid_extract. Keys ending in `?` are optional. Optional `oneOf` dialect for branch shapes. |
| validation | Canonical validator: any, has_keys:k1,k2, list_min_len:N, callable (bool or tuple) |
| validation_mode | `strict` (default) or `rescue` — rescue lets callable accept schema misses |
| strict_schema | Opt-in: raise at construction if format uses bare None exemplars |
| validator | Config-style alias for `validation`; behaves identically |
| on_failure | Hook: fn(thought, attempt, failure_kind, reason, raw_response=None) |
| hold_msg | Hold failed assistant messages out of history until success (default: True) |
| repair_target | For dict prompts, which section key receives repair suffix text |
| template_mode | Opt-in prompt rendering: `format` (default, str.format) or `substitute` ({key} only) |
| include_history | Opt-in history control: True (default) forwards MEMORY turns via get_llm_msgs; False sends system + user only |
| max_retries | Retry attempts on validation failure |
| retry_delay | Delay between retries in seconds |
| required_vars | Variables required from memory |
| optional_vars | Optional variables from memory |
| output_var | Variable name for result (default: {name}_result) |
| pre_hook, post_hook | Callables for custom processing |
| on_token | Callable receiving each streamed text chunk: fn(chunk) |
| output_schema | Optional JSON Schema dict passed natively to `LLM.call(output_schema=...)`, automatically degrading to prompt-guided JSON + repair retries when an endpoint rejects `response_format` |
| reasoning | Optional per-thought reasoning dict (e.g. `{'effort': 'low'}`) or `reasoning_effort='low'`, normalized across `openrouter`, `openai`, and `groq` |
| channel | Channel for message tracking |
| add_reflection | Whether to add reflection on success (default: False) |

### Standalone execution (`thought.run`)

For single-step calls without manual `MEMORY` setup, `thought.run(vars=None, memory=None)` runs the thought (or `DECIDE` / `PLAN`) against a fresh or supplied `MEMORY`, seeds `vars`, and returns the parsed `{name}_result` directly. Built-in template variables (`('last_user_msg', 'last_asst_msg', 'messages')`) are listed on `THOUGHT.BUILTIN_TEMPLATE_VARS`, and prompt helpers `render_vars(...)` and `require_grounded_quotes(...)` live in `thoughtflow._util`.

## Usage

```python
from thoughtflow import MEMORY, THOUGHT, LLM

memory = MEMORY()
memory.add_msg('user', 'Summarize the key points.', channel='api')
llm = LLM(model_id='openai:gpt-4o-mini', key='...')

thought = THOUGHT(
    name='summarize',
    llm=llm,
    prompt='Summarize the last user message: {last_user_msg}',
    operation='llm_call'
)
memory = thought(memory)
result = memory.get_var('summarize_result')
```

```python
# Schema parsing with optional key
thought = THOUGHT(
    name='extract_info',
    llm=llm,
    prompt='Extract name and optional age from: {text}',
    parsing_rules={'kind': 'python', 'format': {'name': str, 'age?': int}},
)
```

```python
# Production lane: observability + strict schema guard
thought = THOUGHT(
    name='locator',
    llm=llm,
    prompt='Find the relevant span.',
    parsing_rules={'kind': 'python', 'format': {'oneOf': [...]}},
    validation=my_validator,
    validation_mode='rescue',
    strict_schema=True,
    on_failure=my_metrics_hook,
    hold_msg=True,
    max_retries=3,
)
```

```python
# JSON-heavy prompt: safe substitution without rewriting history
thought = THOUGHT(
    name='extract',
    llm=llm,
    prompt='Extract fields from: {text}. Example shape: {"name": "", "score": 0}',
    template_mode='substitute',
    include_history=False,
)
```

```python
# Memory query (no LLM)
thought = THOUGHT(
    name='get_context',
    operation='memory_query',
    required_vars=['user_name', 'session_id']
)
memory = thought(memory)

# Variable set
thought = THOUGHT(
    name='init',
    operation='variable_set',
    prompt={'status': 'active', 'count': 0}
)
memory = thought(memory)
```

## Relationship to Other Primitives

THOUGHT consumes LLM (for llm_call) and MEMORY (for context and result storage). It is composed by AGENT (as atomic steps), WORKFLOW (as orchestrated steps), and CHAT (as the underlying turn logic). DECIDE and PLAN extend THOUGHT for specific patterns. ACTION is distinct — imperative operations invoked by code, not by LLM selection.

## Considerations for Future Development

- DECIDE and PLAN documented in their own primitive files
- Execution history integration with workflow observability
