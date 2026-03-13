# ACTION

> Wraps an external or internal operation with consistent logging, state management, and error handling.

## Philosophy

Agents need to do things: search the web, read files, call APIs, run shell commands. ACTION is the primitive that wraps those operations so they integrate cleanly with ThoughtFlow's memory and tracing. Unlike TOOL, which is LLM-selected and declarative, ACTION is imperative: your code calls it directly. The developer or orchestration logic decides when and with what parameters to invoke an action.

ACTION provides a uniform contract: every action receives memory and keyword arguments, executes a function, stores the result in memory via `set_var`, and logs execution details. Exceptions are caught and logged rather than raised, so a workflow can continue and decide how to handle failures. Execution history (count, timing, success/error) is tracked for debugging and optimization.

Within the ThoughtFlow ecosystem, ACTION is the execution layer. THOUGHT and DECIDE produce decisions; PLAN produces a blueprint; ACTION performs the work. Fourteen built-in action subclasses (SAY, ASK, NOTIFY, SEARCH, FETCH, SCRAPE, READ, WRITE, POST, SLEEP, WAIT, NOOP, RUN, CALL) cover common operations. Custom actions wrap any callable with the same `fn(memory, **kwargs) -> result` signature.

## How It Works

An ACTION is constructed with a name, a callable `fn`, optional default `config`, and optional `result_key` (defaults to `{name}_result`). On call, `config` is merged with call-specific `kwargs`, and `fn(memory, **merged_kwargs)` is invoked. The return value is stored in memory at `result_key` and logged as a JSON event.

If the function raises, the exception is caught. Error details are logged, stored in memory at `result_key`, and recorded in `execution_history`. The action does not re-raise; the caller receives the updated memory and can inspect `action.last_error` or `action.was_successful()`.

`execution_count` and `execution_history` track every run: stamp, memory id, duration, success flag, and error message. `copy()` creates a new instance with a fresh id and reset stats. `to_dict`/`from_dict` support serialization (the function is represented by name; a registry is required for deserialization).

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `name` | Identifier for this action (logging, result key). |
| `fn` | Callable with signature `fn(memory, **kwargs) -> result`. |
| `config` | Default parameters merged with call-time kwargs. |
| `result_key` | Key where result is stored in memory. Default: `{name}_result`. |
| `description` | Human-readable description. |

**Built-in action subclasses:** SAY, ASK, NOTIFY, SEARCH, FETCH, SCRAPE, READ, WRITE, POST, SLEEP, WAIT, NOOP, RUN, CALL. Each has constructor params appropriate to its purpose (e.g. SEARCH takes `query`, WRITE takes `path` and `content`).

## Usage

```python
from thoughtflow import ACTION, MEMORY

def my_search(memory, query, max_results=3):
    # Simulate or call real search API
    return {"hits": ["result1", "result2"], "query": query}

search_action = ACTION(
    name="web_search",
    fn=my_search,
    config={"max_results": 5},
    description="Searches the web for information",
)

memory = MEMORY()
memory = search_action(memory, query="ThoughtFlow Python")
result = memory.get_var("web_search_result")
print(search_action.execution_count, search_action.was_successful())
```

```python
# Using a built-in action
from thoughtflow import SAY, WRITE, MEMORY

memory = MEMORY()
memory.set_var("user_name", "Alice")
memory = SAY(message="Hello, {user_name}!")(memory)
memory = WRITE(name="save", path="/tmp/notes.txt", content="Hello world")(memory)
```

## Relationship to Other Primitives

- **TOOL**: TOOL is LLM-selected; ACTION is developer-invoked. A TOOL can wrap an ACTION as its execution function. ACTION is the "hands and feet"; TOOL is the schema the LLM sees.
- **THOUGHT / DECIDE / PLAN**: These produce decisions or plans. ACTION executes operations. WORKFLOW or agent loops typically chain THOUGHT/PLAN with ACTION.
- **MEMORY**: ACTION reads from and writes to memory. Results are stored via `set_var`; logs are added via `add_log`.
- **WORKFLOW**: WORKFLOW steps can be ACTIONs. The workflow invokes `action(memory)` for each step.

## Considerations for Future Development

- Async support for IO-bound actions (e.g. FETCH, SEARCH) without blocking the loop.
- Timeout configuration for long-running actions.
- Retry policy (e.g. retry on transient errors with backoff).
- Action composition: chain or compose multiple actions into a single unit.
- Stricter validation of `fn` signature (e.g. require `memory` as first arg).
