# Tracing

Traces capture complete run state: inputs, outputs, tool calls, timing, tokens, and costs. This enables debugging, evaluation, reproducibility, and regression testing.

---

## Session Basics

```python
from thoughtflow.trace import Session

# Create a session
session = Session()

# Pass to agent calls
response = agent.call(messages, session=session)

# Inspect the trace
print(session.events)
print(session.total_tokens)
print(session.total_cost)
print(session.duration_ms)
```

---

## Saving and Loading

```python
# Save a session
session.save("trace.json")

# Load it back
loaded = Session.load("trace.json")

# Get summary
print(session.summary())
# {
#     "session_id": "...",
#     "event_count": 5,
#     "total_tokens": 150,
#     "total_cost": 0.003,
#     "duration_ms": 1250
# }
```

---

## Event Types

```python
from thoughtflow.trace import EventType

# Agent lifecycle
EventType.CALL_START    # Agent call begins
EventType.CALL_END      # Agent call completes
EventType.CALL_ERROR    # Agent call fails

# Model interactions
EventType.MODEL_REQUEST   # Request sent to model
EventType.MODEL_RESPONSE  # Response received
EventType.MODEL_ERROR     # Model call fails

# Tool interactions
EventType.TOOL_CALL      # Tool invoked
EventType.TOOL_RESULT    # Tool returns
EventType.TOOL_ERROR     # Tool fails

# Memory interactions
EventType.MEMORY_RETRIEVE  # Memory lookup
EventType.MEMORY_STORE     # Memory write

# Custom
EventType.CUSTOM         # User-defined events
```

---

## Creating Events

```python
from thoughtflow.trace import Event, EventType
from thoughtflow.trace.events import call_start, call_end, tool_call

# Using factory functions
event = call_start(messages, params={"temperature": 0.7})
event = call_end(response, tokens={"total": 50})
event = tool_call("calculator", {"expression": "2+2"})

# Manual creation
event = Event(
    event_type=EventType.CUSTOM,
    data={"custom_key": "custom_value"},
    metadata={"source": "my_module"}
)

# Add to session
session.add_event(event)
```

---

## Schema Versioning

Trace schemas are versioned for compatibility:

```python
from thoughtflow.trace import TraceSchema

schema = TraceSchema()
print(schema.version)  # "1.0.0"

# Check compatibility
schema.is_compatible("1.2.0")  # True (same major)
schema.is_compatible("2.0.0")  # False (different major)
```

---

## Replay Testing

Use traces for regression testing:

```python
from thoughtflow.eval import Replay

# Save a known-good run
session.save("golden.json")

# Later: replay and compare
replay = Replay.load("golden.json")
result = replay.run(agent)

assert result.success
assert result.replayed_response == result.original_response
```

---

## Design Philosophy

- **Complete capture**: Everything is recorded
- **Serializable**: Save and load sessions
- **Versioned schema**: Backward-compatible evolution
- **Foundation for eval**: Enables regression testing
