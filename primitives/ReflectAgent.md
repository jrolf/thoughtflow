# ReflectAgent

> Self-critique and revision loop for quality-sensitive responses.

## Philosophy

ReflectAgent exists because first-pass LLM output is often good but not great. For writing, analysis, and complex reasoning, a second look can catch errors, improve clarity, and align the response with the user's intent. ReflectAgent adds a critique step: a separate LLM call evaluates the response. If the critique approves it, the response is final. If not, the agent revises and the cycle repeats until approved or `max_revisions` is reached.

ReflectAgent is a subclass of AGENT. It does not change the base tool-use loop. Instead, it wraps it: run the base agent to get an initial response, then run the critique/revision cycle on that response. The result is stored in `{name}_result` just like AGENT, but it may have been revised one or more times. This is useful when quality matters more than speed.

## How It Works

1. **Generate** — Call the base AGENT `__call__` to produce an initial response. The response is stored in `{name}_result`.
2. **Critique** — Call the LLM with `critique_prompt.format(response=current_response)`. The critique prompt must contain a `{response}` placeholder.
3. **Approval check** — Look for approval signals in the critique: "APPROVED", "looks good", "no issues", "no changes needed". If found, stop.
4. **Revise** — Call `_revise()`: build messages from memory, append a revision prompt (previous response + critique), call the LLM for an improved version.
5. **Update** — Store the revised response in memory and `{name}_result`. Append to `revision_history`. Repeat from step 2 until approved or `max_revisions` exhausted.

Each revision is recorded in `revision_history` with the response, critique, and revision number. The final response in memory is the last (possibly revised) version.

## Inputs & Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| critique_prompt | Prompt template for critique; must contain `{response}` | Default prompt asking for review, "APPROVED" if good |
| max_revisions | Max critique/revision cycles | 2 |
| llm, tools, system_prompt, max_iterations, name, on_tool_call | Same as AGENT | (see AGENT) |

## Usage

```python
from thoughtflow import LLM, MEMORY, ReflectAgent

llm = LLM("openai:gpt-4o", key="sk-...")
agent = ReflectAgent(
    llm=llm,
    system_prompt="You are a careful writer.",
    max_revisions=2,
)

memory = MEMORY()
memory.add_msg("user", "Write a haiku about programming.")
memory = agent(memory)
print(memory.get_var("agent_result"))
print(agent.revision_history)  # List of {revision, response, critique}
```

Custom critique prompt:

```python
agent = ReflectAgent(
    llm=llm,
    critique_prompt="Check this for factual accuracy and tone. Say APPROVED if fine.\n\n{response}",
    max_revisions=3,
)
```

## Relationship to Other Primitives

- **AGENT** — ReflectAgent subclasses AGENT. It calls `super().__call__(memory)` for the initial response, then runs the critique/revision loop.
- **LLM** — Used for both the base agent loop and the separate critique and revision calls.
- **MEMORY** — Reads context for revision; updates `{name}_result` with each revision.

## Considerations for Future Development

- Configurable approval signals (beyond the hardcoded list).
- Structured critique output (e.g., JSON with categories: accuracy, clarity, completeness).
- Optional human-in-the-loop approval instead of LLM critique.
- Cost control: limit total critique+revision tokens or calls.
