# WORKFLOW

> Python control flow with guardrails for step-based orchestration.

## Philosophy

WORKFLOW exists because raw Python `if/else` and loops do not give you automatic tracing, serializable execution, or a consistent interface for reusable flows. WORKFLOW adds a thin orchestration layer: define steps as callables, add conditions and branches, and run them in order. Every step is logged. The execution is inspectable. The contract is `memory = workflow(memory)`. It is "Python control flow with guardrails" — no DSL, no graph language, just a thin layer over plain callables.

WORKFLOW composes THOUGHTs, ACTIONs, AGENTs, and DELEGATEs. A step can be any callable that accepts memory and returns memory. Conditional steps run only when their condition returns True. Branching routes to different handlers based on a router function. Error strategies (stop, skip, retry) control what happens when a step fails. The result is a lightweight way to build non-linear flows without leaving Python.

## How It Works

**Step registration** — `step(fn, name=None, condition=None)` adds a step. The step runs when its condition (if any) returns True. Steps execute in definition order. Method chaining is supported.

**Branch registration** — `branch(router_fn, branches, name=None)` adds a branch step. `router_fn(memory)` returns a key; `branches[key]` is the callable to run. A "default" key handles unknown keys.

**Execution** — For each step: evaluate condition, skip if False. Execute the step. If it raises, apply `on_error` strategy:
- `stop` (default): log and break.
- `skip`: continue to next step.
- `retry`: try once more; if it fails again, log and break.

**Logging** — Each step produces an entry in `execution_log` with step name, status (completed, skipped, error, completed_on_retry, retry_failed), duration_ms, and error message if any.

**Status** — After execution, `{name}_status` is stored in memory: total_steps, completed, skipped, errors.

## Inputs & Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| name | Identifier for this workflow | "workflow" |
| on_error | Error strategy: "stop", "skip", "retry" | "stop" |

Step method:

| Parameter | Description |
|-----------|-------------|
| fn | Callable(memory) -> memory |
| name | Step identifier (defaults to fn.__name__ or step_N) |
| condition | Callable(memory) -> bool; step skipped when False |

Branch method:

| Parameter | Description |
|-----------|-------------|
| router_fn | Callable(memory) -> str (branch key) |
| branches | Dict mapping keys to callables |
| name | Branch step identifier |

## Usage

```python
from thoughtflow import MEMORY, WORKFLOW, AGENT, THOUGHT

workflow = WORKFLOW(name="research_flow", on_error="skip")
workflow.step(classify_thought, name="classify")
workflow.step(search_agent, name="search", condition=lambda m: m.get_var("needs_search"))
workflow.step(summarize_thought, name="summarize")

memory = MEMORY()
memory.add_msg("user", "Tell me about quantum computing")
memory = workflow(memory)
print(memory.get_var("research_flow_status"))
print(workflow.execution_log)
```

With branching:

```python
workflow.branch(
    router_fn=lambda m: m.get_var("category"),
    branches={
        "technical": handle_technical,
        "creative": handle_creative,
        "default": handle_default,
    },
    name="route_by_category",
)
```

## Relationship to Other Primitives

- **AGENT, THOUGHT, ACTION** — All can be workflow steps. Each follows `memory = fn(memory)`.
- **DELEGATE** — A step can call `delegate.dispatch(memory, "researcher", task)` and return the updated memory.
- **MEMORY** — Workflow reads and writes memory. Conditions and routers inspect memory; steps transform it.

## Considerations for Future Development

- Parallel steps (steps with same dependency run concurrently).
- Explicit step dependencies (e.g., `after="gather"`) instead of definition order.
- Loop support (step references earlier step as dependency with exit condition).
- Workflow serialization and replay for debugging.
- Step-level timeout configuration.
