# SLEEP

> Pause execution for a specified duration. Useful for rate limiting, backoff, and timing control.

## Philosophy

SLEEP provides an explicit, first-class way to introduce delays in agent workflows. Rather than scattering `time.sleep()` calls or ad-hoc backoff logic, SLEEP encapsulates the delay as an ACTION with a clear reason and optional dynamic duration. This makes workflows easier to reason about, serialize, and tune. Negative or invalid durations are clamped to zero so execution never hangs on bad input.

## How It Works

SLEEP extends the base ACTION class. On execution, it resolves `duration` from kwargs or `self.duration`. If duration is a callable, it is invoked with `(memory)` to produce a float; otherwise it is passed through the substitution system. The value is coerced to float; negative or invalid values become 0. If duration is positive, `time.sleep(duration)` is called. The action returns a dict with status, duration, and reason. Callable durations cannot be serialized via `to_dict`; `from_dict` reconstructs only fixed durations.

## Inputs & Configuration

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | No | "sleep" | Unique identifier for this action |
| duration | No | 1.0 | Seconds to sleep; float or callable `(memory) -> float` |
| reason | No | "" | Explanation for the sleep (logged) |

## Usage

```python
from thoughtflow.actions import SLEEP
from thoughtflow import MEMORY

# Fixed delay
sleep = SLEEP(duration=2.5, reason="Rate limit pause")
memory = sleep(MEMORY())

# Dynamic delay from memory
sleep = SLEEP(
    duration=lambda m: m.get_var("retry_delay", 1.0),
    reason="Backoff delay"
)
memory = memory.set_var("retry_delay", 3.0)
memory = sleep(memory)

# Exponential backoff
sleep = SLEEP(
    duration=lambda m: 2 ** m.get_var("attempt", 0),
    reason="Exponential backoff"
)
memory = memory.set_var("attempt", 3)  # sleeps 8 seconds
memory = sleep(memory)
```

## Relationship to Other Primitives

- **WAIT**: Polls a condition until true; SLEEP pauses for a fixed or computed duration. Use SLEEP for known delays, WAIT for event-driven readiness.
- **NOOP**: Does nothing; SLEEP actually blocks. Use NOOP when you want to skip work, SLEEP when you need a real delay.
- **RUN**, **CALL**: May be preceded by SLEEP for rate limiting before external calls.

## Considerations for Future Development

- Async-friendly variant that yields instead of blocking, for use in async workflows.
- Optional jitter parameter for randomized delays to avoid thundering herd.
- Integration with workflow-level rate limiters (e.g., per-domain throttling).
