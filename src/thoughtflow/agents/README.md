# `src/thoughtflow/agents/` — Agentic Methodology Subclasses

> **Scope:** Methodology-specific subclasses of [`AGENT`](../agent.py) (`ReactAgent`, `ReflectAgent`, `PlanActAgent`).
> **Parent class:** [`AGENT`](../agent.py) · **Specs:** [`primitives/AGENT.md`](../../../primitives/AGENT.md), [`primitives/ReactAgent.md`](../../../primitives/ReactAgent.md), [`primitives/ReflectAgent.md`](../../../primitives/ReflectAgent.md), [`primitives/PlanActAgent.md`](../../../primitives/PlanActAgent.md)

---

## Strategy & When to Choose Which Agent

Base `AGENT` (in `src/thoughtflow/agent.py`, along with the `tool_loop` helper) implements ThoughtFlow's **governed, write-ahead native tool loop** over `LLM.chat()` for providers with native tool calling (`openai`, `openrouter`, `groq`), falling back automatically to JSON-in-text for `call()`-only models.

The three subclasses in `agents/` encode classic reasoning topologies on top of `AGENT` while preserving the `memory = agent(memory)` contract:

| Module | Class | Loop Topology | Best Used When |
|--------|-------|---------------|----------------|
| `../agent.py` | `AGENT` / `tool_loop` | **Native write-ahead tool loop** (persist assistant `tool_calls` -> policy/approval/budget check -> execute `TOOL` -> persist `tool` result -> checkpoint) | Default choice for modern tool-calling models, governed side effects (`allow`, `policy`, `budget`), crash recovery, and human-in-the-loop suspend/resume (`decision=`) |
| `react.py` | `ReactAgent` | **Reason + Act text loop** (`Thought:` -> `Action:` -> `Action Input:` -> `Observation:` -> `Final Answer:`) | Local or text-only models without native function-calling APIs, or when you want explicit human-readable `Thought:` traces in the prompt |
| `reflect.py` | `ReflectAgent` | **Generate -> Critique -> Revise** (runs `super().__call__`, then critiques against `{task}` and `{system_prompt}` up to `max_revisions`) | High-stakes writing, synthesis, or analysis where self-review improves output quality; records `approved`, `revisions`, and `final_critique` in `{name}_outcome` |
| `planact.py` | `PlanActAgent` | **Plan -> Execute -> Replan** (generates JSON step list, runs tools sequentially, replans on failure, summarizes) | Multi-step tool workflows where upfront decomposition helps smaller models stay on track (for strict production governance, prefer `PLAN` + `WORKFLOW` or [`examples/reference/`](../../../examples/reference/README.md)) |

---

## Key Implementation Nuances

- **`ReactAgent` (`react.py`):** Extracts everything after `Final Answer:` across multiple lines (preserving markdown lists and code blocks) and writes `"Observation: Tool '<name>' was blocked by policy."` into `MEMORY` when `on_tool_call` returns `False` so the model can adapt instead of looping blindly.
- **`ReflectAgent` (`reflect.py`):** Respects native suspension (`if memory.is_suspended(): return memory` before critiquing), feeds `{task}`, `{system_prompt}`, and `{response}` to the critic, uses negation-safe word-boundary approval matching (`REJECT_SIGNALS`), appends each revised draft to `MEMORY` so `last_asst_msg()` stays in sync with `{name}_result`, and performs a final verification pass when `max_revisions` is reached.
- **`PlanActAgent` (`planact.py`):** Executes initial plans and adaptive replans inside a bounded `while` loop (`max_replans=2`), substitutes both `{task}` / `{tool_list}` and legacy `{{task}}` / `{{tool_list}}` placeholders, coerces non-string step labels safely, detects structured tool error dicts without misjudging prose starting with `"Error"`, and writes `{name}_status` and `{name}_outcome`.
