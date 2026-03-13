# ReactAgent

> Reason + Act: structured Thought, Action, and Observation in each iteration.

## Philosophy

ReactAgent exists for two reasons. First, not every LLM supports function-calling APIs. Text-based tool selection works with any model that can follow instructions. Second, explicit Thought/Action/Observation structure makes the agent's reasoning visible. You can see what it was thinking before each action and what it observed afterward. This transparency is valuable for debugging, auditing, and understanding agent behavior.

ReactAgent is a subclass of AGENT. It inherits the tool execution and memory handling but replaces the prompt structure and response parsing. Instead of JSON tool calls, the LLM outputs plain text in a fixed format. The system prompt injects instructions and tool descriptions as text, and the parser extracts "Action:" and "Action Input:" lines. "Final Answer:" signals completion.

## How It Works

Each iteration follows the same loop as AGENT, but with different message building and parsing:

1. **Build messages** — System prompt plus ReAct instructions (format rules for Thought, Action, Action Input, Final Answer) plus tool descriptions as text. No tool schemas in params.
2. **Call the LLM** — With empty params (no function-calling).
3. **Parse response** — Look for "Action: &lt;tool_name&gt;" and "Action Input: &lt;json&gt;" lines. If "Final Answer:" appears, treat the rest as the answer and stop.
4. **If Final Answer** — Extract the answer text, store in memory, set `{name}_result`, exit.
5. **If Action** — Execute the tool, add the full assistant response and "Observation: &lt;result&gt;" as a user message, repeat.

Observations are added as user messages with the "Observation: ..." prefix so the LLM sees them in context on the next turn. The full ReAct trace (Thought, Action, Observation) remains in memory for transparency.

## Inputs & Configuration

ReactAgent accepts the same parameters as AGENT:

| Parameter | Description | Default |
|-----------|-------------|---------|
| llm | LLM instance | Required |
| tools | List of TOOL instances | [] |
| system_prompt | Base instructions (ReAct format rules are appended) | "You are a helpful assistant." |
| max_iterations | Max loop iterations | 10 |
| name | Identifier | "agent" |
| on_tool_call | Pre-execution hook | None |

## Usage

```python
from thoughtflow import LLM, MEMORY, TOOL, ReactAgent

llm = LLM("ollama:llama3", key=None)  # Works with models that lack function-calling
tools = [TOOL("calculator", "Do math", {"expr": {"type": "string"}}, calc_fn)]
agent = ReactAgent(llm=llm, tools=tools, system_prompt="You are a problem-solving assistant.")

memory = MEMORY()
memory.add_msg("user", "What is 23 * 47?")
memory = agent(memory)
print(memory.get_var("agent_result"))
```

The LLM output will look like:

```
Thought: I need to multiply 23 and 47.
Action: calculator
Action Input: {"expr": "23 * 47"}

Observation: 1081

Thought: I have the answer.
Final Answer: 23 times 47 equals 1081.
```

## Relationship to Other Primitives

- **AGENT** — ReactAgent subclasses AGENT. It overrides `_build_messages`, `_build_params`, `_parse_tool_calls`, and `__call__` to implement text-based tool selection.
- **TOOL** — ReactAgent uses TOOLs but injects their descriptions as text into the prompt instead of using `to_schema()`. Tool execution is unchanged.
- **LLM, MEMORY** — Same as AGENT.

## Considerations for Future Development

- Configurable format keywords (e.g., "Action:" vs "Tool:").
- Support for multi-tool calls in a single response.
- Fallback to base AGENT behavior when the model outputs malformed ReAct text.
- Optional Thought extraction for separate storage or display.
