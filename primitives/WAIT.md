# WAIT

> Poll a condition at regular intervals until it returns True or a timeout occurs.

## Philosophy

WAIT enables event-driven and polling patterns within agent workflows. Instead of busy-waiting or ad-hoc loops, WAIT encapsulates the logic of checking a condition repeatedly with configurable timeout behavior. Condition errors are logged but do not stop the wait, so transient failures (e.g., network blips) do not abort the loop. The caller can choose to raise on timeout, continue with a default, or store the timeout status in memory for downstream branching.

## How It Works

WAIT extends the base ACTION class. On execution, it enters a loop: each iteration invokes the `condition` callable with `(memory)`. If it returns True, WAIT returns immediately with status "completed". If the condition raises, the error is logged via `memory.add_log` and the loop continues. After each check, WAIT sleeps for `poll_interval` seconds. If `timeout` is set and elapsed time exceeds it, WAIT handles according to `on_timeout`: "raise" (default) raises `TimeoutError`, "continue" returns the result dict, or "default" returns the `default` value. When `store_timeout_as` is set, WAIT stores True (timeout) or False (completed) in that memory variable. The condition callable cannot be serialized; it must be provided when reconstructing via `from_dict`.

## Inputs & Configuration

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | No | "wait" | Unique identifier for this action |
| condition | Yes | - | Callable `(memory) -> bool`; returns True when wait should end |
| timeout | No | None | Maximum wait time in seconds; None means wait forever |
| poll_interval | No | 1.0 | Seconds between condition checks |
| on_timeout | No | "raise" | Behavior when timeout: raise, continue, or default |
| default | No | None | Value returned when on_timeout is "default" |
| store_timeout_as | No | None | Memory variable to store True/False for timeout status |

## Usage

```python
from thoughtflow.actions import WAIT
from thoughtflow import MEMORY
import os

# Wait for approval flag
wait = WAIT(
    condition=lambda m: m.get_var("approved") == True,
    timeout=300,
    poll_interval=5
)
memory = wait(memory)

# Wait with graceful timeout (no exception)
wait = WAIT(
    condition=lambda m: m.get_var("data_ready"),
    timeout=60,
    on_timeout="continue"
)
result = wait(memory)
if result.get("timed_out"):
    # handle timeout
    pass

# Wait for file to appear
wait = WAIT(
    condition=lambda m: os.path.exists(m.get_var("expected_file")),
    timeout=120,
    poll_interval=2
)
memory = wait(memory)

# Store timeout status for downstream logic
wait = WAIT(
    condition=lambda m: m.get_var("job_done"),
    timeout=30,
    store_timeout_as="timed_out"
)
memory = wait(memory)
if memory.get_var("timed_out"):
    # fallback logic
    pass
```

## Relationship to Other Primitives

- **SLEEP**: Fixed or computed delay; WAIT polls until a condition is met. Use SLEEP for known delays, WAIT for readiness checks.
- **NOOP**: Does nothing; WAIT actively polls. Use NOOP to skip, WAIT to block until ready.
- **RUN**, **CALL**: Often followed by WAIT when waiting for external processes or APIs to complete.

## Considerations for Future Development

- Async variant that uses asyncio.sleep and async condition callables.
- Configurable backoff for poll_interval (e.g., exponential) to reduce load on slow conditions.
- Optional max_checks to limit iterations independent of timeout.
