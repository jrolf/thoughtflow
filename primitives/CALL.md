# CALL

> Call external functions with structured parameters resolved from memory. A cleaner interface than base ACTION for invoking any callable.

## Philosophy

CALL bridges the gap between the base ACTION (which requires `fn(memory, **kwargs)`) and ordinary Python functions that accept `(**kwargs)` only. It provides parameter resolution from memory via `{variable}` substitution and optional callables, so you can invoke existing libraries and APIs without wrapping them in memory-aware signatures. Timeout support via threading and configurable error handling make CALL suitable for both fast in-process calls and potentially slow external invocations.

## How It Works

CALL extends the base ACTION class. On execution, it resolves `params` through the substitution system: a dict with `{variable}` placeholders is filled from memory; a callable `(memory) -> dict` produces the params directly. Additional kwargs passed at call time are merged in (excluding control params like `params`, `timeout`, `on_error`). The function is invoked with `**resolved_params`. If `timeout` is set, CALL runs the function in a daemon thread and joins with that timeout; if the thread is still alive, it raises `TimeoutError`. On exception, CALL handles according to `on_error`: "raise" re-raises, "log" records to memory and returns an error dict, "ignore" returns the error dict. The result is stored in memory under `store_as` (default `{name}_result`). The function itself cannot be serialized; `from_dict` requires either a `function` argument or a `fn_registry` mapping function names to callables.

## Inputs & Configuration

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | No | function name | Unique identifier for this action |
| function | Yes | - | Callable to invoke; does NOT receive memory as first arg |
| params | No | {} | Parameters; dict with `{variable}` or callable `(memory) -> dict` |
| timeout | No | None | Execution timeout in seconds (uses threading) |
| on_error | No | "log" | Error behavior: log, raise, or ignore |
| store_as | No | "{name}_result" | Memory variable for result |

## Usage

```python
from thoughtflow.actions import CALL
from thoughtflow import MEMORY

# Simple function call
def greet(name):
    return "Hello, {}!".format(name)

call = CALL(function=greet, params={"name": "Alice"})
memory = call(MEMORY())
result = memory.get_var("call_result")  # "Hello, Alice!"

# With memory variables
def process(data, multiplier=1):
    return data * multiplier

call = CALL(
    function=process,
    params={"data": "{input_data}", "multiplier": 2}
)
memory = memory.set_var("input_data", 10)
memory = call(memory)

# Dynamic parameters from memory
call = CALL(
    function=external_api.query,
    params=lambda m: {
        "query": m.get_var("user_query"),
        "limit": m.get_var("max_results", 10)
    }
)
memory = call(memory)

# With timeout
call = CALL(
    function=slow_api_call,
    params={"url": "{target_url}"},
    timeout=30
)
memory = call(memory)
```

## Relationship to Other Primitives

- **ACTION (base)**: Requires `fn(memory, **kwargs)`; CALL wraps any `fn(**kwargs)` and resolves params from memory. Use CALL when integrating existing functions.
- **RUN**: Executes shell commands; CALL invokes Python functions. Use CALL for in-process logic, RUN for external processes.
- **WRITE**, **READ**: CALL can wrap custom file logic; the primitives provide standard patterns.
- **NOOP**: Replace CALL with NOOP to skip the function call (e.g., when mocking).

## Considerations for Future Development

- Async variant using asyncio for non-blocking calls in async workflows.
- Support for passing memory explicitly to functions that need it (e.g., `params={"memory": "{_memory}"}`).
- Thread pool or process pool option for CPU-bound functions to avoid blocking the main thread.
