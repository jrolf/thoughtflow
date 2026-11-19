# PlanActAgent

> Plan first, then execute: structured decomposition with adaptive replanning.

## Philosophy

PlanActAgent exists for complex multi-step tasks where acting blindly leads to wasted effort or wrong order. By generating a plan first, the agent decomposes the task into concrete steps, each with an optional tool and arguments. The plan is then executed in order. If a step fails and `replan_on_failure` is True, the agent generates a new plan for the remaining work. This plan-then-execute pattern with adaptive replanning suits research, analysis, and multi-tool workflows.

PlanActAgent is a subclass of AGENT. It does not use the standard tool-use loop. Instead, it runs in two phases: planning (LLM produces a JSON list of steps) and execution (each step runs in sequence). The plan format is `{"step": "description", "tool": "tool_name" or null, "args": {...}}`. If plan parsing fails, PlanActAgent falls back to base AGENT behavior.

## How It Works

1. **Extract task** — Get the last user message from memory as the task text.
2. **Generate plan** — Call the LLM with `planner_prompt` (supports both `{task}`/`{tool_list}` and `{{task}}`/`{{tool_list}}` placeholders while preserving literal JSON braces). Parse the response as a JSON list, coercing non-string step labels cleanly via `str(...)`. If parsing fails, fall back to `super().__call__(memory)`.
3. **Execute steps (with bounded replanning)** — Run an outer execution loop bounded by `max_replans` (default `2`):
   - If the step names a tool, invoke `_execute_tool(tool_name, args, context={'memory': memory, 'agent': self})`, log the observation, and append to `execution_log`.
   - Structural tool failures (exceptions, vetoed calls, `{name}_status == 'error'`, or structured failure dicts) — rather than `"Error"` string prefixes — mark the step failed. When `replan_on_failure=True` and `replan_count < max_replans`, `_replan` generates a revised remaining plan and the outer loop executes the new plan immediately.
   - Reasoning-only steps (`tool: null`) log and continue.
4. **Generate summary** — Call the LLM with execution results to produce a final answer, storing `{name}_result`, `{name}_status` (`'final'` or `'incomplete'`), and `{name}_outcome` (`ok`, `steps_executed`, `replans`, `execution_log`).

`execution_log` records each step's description, tool, args, result, and success. `current_plan` holds the active plan. Replanning replaces `current_plan` with a new list for the remaining task.

## Inputs & Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `planner_prompt` | Template for plan generation; supports `{task}`, `{tool_list}` (or `{{task}}`, `{{tool_list}}`) | Default prompt requesting JSON list of steps |
| `replan_on_failure` | Regenerate and execute a revised plan when a step fails | `True` |
| `max_replans` | Maximum replanning cycles executed per run | `2` |
| `llm`, `tools`, `system_prompt`, `name` | Same as AGENT | (see AGENT) |

Note: `max_iterations` and `on_tool_call` are inherited but the plan-execute loop does not use them in the same way as base AGENT.

## Usage

```python
from thoughtflow import LLM, MEMORY, TOOL, PlanActAgent

llm = LLM("openai:gpt-4o", key="sk-...")
tools = [
    TOOL("search", "Search the web", {"query": {"type": "string"}}, search_fn),
    TOOL("write", "Write to file", {"path": {"type": "string"}, "content": {"type": "string"}}, write_fn),
]
agent = PlanActAgent(llm=llm, tools=tools, system_prompt="You are a research assistant.")

memory = MEMORY()
memory.add_msg("user", "Research Python frameworks and write a summary to summary.txt.")
memory = agent(memory)
print(memory.get_var("agent_result"))
print(agent.execution_log)   # Step-by-step log
print(agent.current_plan)    # Final plan state
```

## Relationship to Other Primitives

- **AGENT** — PlanActAgent subclasses AGENT. It overrides `__call__` entirely and uses `_execute_tool` and `_tool_map` from the base. Falls back to `super().__call__` when planning fails.
- **TOOL** — Used for plan generation (descriptions in prompt) and step execution.
- **MEMORY** — Task extracted from last user message; step results and final summary stored in memory.

## Considerations for Future Development

- Richer plan schema (dependencies between steps, parallel steps).
- Plan validation before execution (check tool names, required args).
- Optional human approval of the plan before execution.
