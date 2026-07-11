# PLAN

> A specialized THOUGHT subclass for generating structured multi-step execution plans.

## Philosophy

Agents often need to break a goal into a sequence of concrete steps before acting. PLAN exists to produce that structure explicitly: a list of steps, each containing one or more tasks, with actions, parameters, and reasons. The output is machine-readable and can be executed by a WORKFLOW or agent loop. Unlike free-form THOUGHT output, a PLAN result has a well-defined shape that downstream code can validate and interpret.

PLAN inherits from THOUGHT, so it uses the same prompt-and-parse pipeline. It adds an `actions` dictionary that defines what the LLM can plan for: action names, descriptions, and optional parameter schemas. The LLM is instructed to return a JSON array of steps, each step an array of tasks. Validation ensures the structure is correct, action names are valid, required parameters are present, and each task has a non-empty `reason` field.

In the ThoughtFlow ecosystem, PLAN bridges high-level goals and low-level execution. It produces the blueprint that WORKFLOW or PLANACT-style agents consume. It is the right primitive when the question is "what steps should we take?" rather than "what is the answer?" or "which option?"

## How It Works

PLAN builds a prompt by appending a formatted list of available actions (with descriptions and parameter schemas when provided) and format instructions. The LLM is asked to return a JSON array: outer list = sequential steps, inner list = tasks that can run in parallel within that step. Each task is an object with `action`, optional `params`, and required `reason`.

`parse_response` extracts JSON from the LLM output, handling markdown code blocks and stray text. Subclasses may override `normalize_plan(parsed)` to apply deterministic repairs before validation (unwrap string plans, lift params, etc.). `validate` checks: the result is a list, step count does not exceed `max_steps`, task count per step does not exceed `max_parallel`, each task has a valid `action` from the actions dict, all missing required params are reported together when schemas exist, and `reason` is a non-empty string without newlines.

On validation failure, PLAN appends a repair suffix and retries (default `max_retries` 3). Repair text is humanized (no raw JSONPath or `NoneType` noise) via the shared THOUGHT repair helpers. The result is stored at `{name}_result`. Tasks can reference previous step results via `{step_N_result}` in parameter values.

### `normalize_plan()` hook

Override this method in a subclass when the model returns structurally correct JSON that needs deterministic cleanup before validation:

```python
class MyPlanner(PLAN):
    def normalize_plan(self, parsed_result):
        # Example: model sometimes wraps the plan in a string
        if isinstance(parsed_result, str):
            parsed_result = json.loads(parsed_result)
        # Example: lift flat params onto task dicts
        if isinstance(parsed_result, list):
            for step in parsed_result:
                for task in step:
                    if "params" not in task and "query" in task:
                        task["params"] = {"query": task.pop("query")}
        return parsed_result
```

Default implementation is a no-op pass-through. The hook runs at the start of `validate()`, before step/task checks.

### Aggregate missing-param errors

When a task references an action with a parameter schema, PLAN collects **all** missing required params before returning a validation failure. Earlier behavior reported one missing param per retry, burning `max_retries` on a single fixable mistake. Now one retry message lists every required param the task omitted:

```
Step 0 Task 1: action 'search' requires params: query, max_results
```

Optional params use the `?` suffix in the schema, same convention as THOUGHT `parsing_rules`.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `name` | Unique identifier for this planner. |
| `llm` | LLM instance for plan generation. |
| `prompt` | Prompt template with `{variable}` placeholders. |
| `actions` | Required. Dict of available actions. Simple: `{"action_name": "description"}`. With params: `{"action_name": {"description": "...", "params": {"arg": "type?"}}}`. Use `?` suffix for optional params. |
| `max_steps` | Maximum steps allowed in plan. Default: 10. |
| `max_parallel` | Maximum parallel tasks per step. Default: 5. |
| `allow_empty` | Whether empty plans are valid. Default: False. |
| `validate_params` | Validate params against schema. Default: True. |
| `max_retries` | Retry attempts for invalid plans. Default: 3. |
| `**kwargs` | Additional THOUGHT parameters (`on_failure`, `hold_msg`, etc.). |

## Usage

```python
from thoughtflow import PLAN, MEMORY, LLM

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# Simple actions (descriptions only)
planner = PLAN(
    name="research",
    llm=llm,
    actions={
        "search": "Search the web for information",
        "analyze": "Analyze content for insights",
        "summarize": "Create a summary",
    },
    prompt="Create a plan to: {goal}",
)
memory.set_var("goal", "Research ThoughtFlow")
memory = planner(memory)
plan = memory.get_var("research_result")
# [[{"action": "search", "params": {...}, "reason": "..."}], [{"action": "analyze", ...}], ...]
```

```python
# Actions with parameter schemas and step references
planner = PLAN(
    name="workflow",
    llm=llm,
    actions={
        "search": {"description": "Search for information", "params": {"query": "str", "max_results": "int?"}},
        "fetch": {"description": "Fetch a resource", "params": {"url": "str"}},
        "summarize": {"description": "Summarize text", "params": {"text": "str"}},
    },
    prompt="Plan to achieve: {goal}\nContext: {context}",
)
memory.set_var("goal", "Research and summarize ThoughtFlow")
memory.set_var("context", "Focus on API design")
memory = planner(memory)
plan = memory.get_var("workflow_result")
# Tasks can use {step_0_result} in params to reference previous step output
```

```python
# Subclass with normalize_plan for production harnesses
class RobustPlanner(PLAN):
    def normalize_plan(self, parsed_result):
        if isinstance(parsed_result, dict) and "steps" in parsed_result:
            return parsed_result["steps"]
        return parsed_result

planner = RobustPlanner(
    name="robust",
    llm=llm,
    actions={"search": "Search"},
    prompt="Plan: {goal}",
    on_failure=my_metrics_hook,
)
```

## Relationship to Other Primitives

- **THOUGHT**: PLAN is a subclass. It inherits the cognitive pipeline, execution history, failure visibility (`{name}_last_error`), and serialization. See [docs/concepts/thought.md](../docs/concepts/thought.md).
- **DECIDE**: Both constrain output. DECIDE constrains to a single choice; PLAN constrains to a structured plan. Use DECIDE for routing; use PLAN for multi-step orchestration.
- **ACTION**: PLAN's `actions` dict describes actions that may be executed. The actual execution is done by ACTION instances or WORKFLOW.
- **WORKFLOW**: WORKFLOW can consume a PLAN result and execute each step, invoking the corresponding ACTIONs.
- **PLANACT**: The PLANACT agent subclass uses PLAN-like logic to generate and adapt plans during execution.

## Considerations for Future Development

- Native structured output (JSON schema) when provider supports it, reducing parse failures.
- Support for conditional steps (e.g. "if step_0 fails, do X").
- Plan revision: accept partial execution results and regenerate remaining steps.
- Integration with TOOL schemas so PLAN actions align with available TOOLs.
- Optional plan explanation or summary field for human review.
