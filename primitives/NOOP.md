# NOOP

> The simplest action primitive. Explicitly does nothing, and does it well.

## Philosophy

Sometimes the right thing to do is nothing at all. NOOP makes that choice explicit and visible. Rather than leaving an empty branch in a conditional or commenting out an action, NOOP states clearly: "we considered this step and decided to skip it." This is valuable for readability, tracing, and debugging.

NOOP is particularly useful as a placeholder during development. When designing a workflow, you may know that a step will exist but haven't implemented it yet. NOOP fills that slot cleanly, logs its execution with a reason, and lets the rest of the workflow run. It is also a natural fit for conditional skip patterns, testing, and mocking.

## How It Works

NOOP is an ACTION subclass that wraps a function which simply returns a status dict. On execution, it does no work other than returning `{"status": "noop", "reason": "..."}`. Like all actions, its execution is logged by the ACTION base class, so traces show that NOOP ran and why.

The `reason` parameter is optional but encouraged. It serves as documentation for why nothing is being done, visible in both logs and serialized output.

## Inputs & Configuration

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | No | "noop" | Unique identifier for this action. |
| reason | No | "" | Explanation for why nothing is being done. Appears in logs and return value. |

## Usage

```python
from thoughtflow.actions import NOOP
from thoughtflow import MEMORY

# Explicit placeholder during development
noop = NOOP(name="todo_email", reason="Email step not yet implemented")
memory = noop(MEMORY())

# Conditional skip pattern
enabled = False
action = real_action if enabled else NOOP(reason="Feature disabled")
memory = action(memory)

# Inspect result
result = memory.get_var("noop_result")
# {"status": "noop", "reason": "Feature disabled"}
```

## Relationship to Other Primitives

- **ACTION**: NOOP is the simplest possible ACTION subclass. It inherits memory integration, execution tracking, and serialization, but performs no work.
- **SLEEP**: SLEEP pauses execution for a duration; NOOP returns immediately. Use SLEEP when you need a deliberate delay, NOOP when you need an explicit skip.
- **CALL**: CALL invokes a function; NOOP is a convenient stand-in when you want to skip a CALL conditionally.
- **WORKFLOW**: In workflow definitions, NOOP can fill optional step slots to keep the structure complete without executing logic.

## Considerations for Future Development

- A `NOOP.counted()` variant that tracks how many times a no-op was hit, useful for understanding conditional skip frequency.
- Optional callback on execution (e.g., for metrics) without performing real work.
- Integration with DECIDE so that "do nothing" is a first-class decision outcome rather than a missing branch.
