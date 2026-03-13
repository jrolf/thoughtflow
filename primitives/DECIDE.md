# DECIDE

> A specialized THOUGHT subclass for constrained decision-making from a finite set of choices.

## Philosophy

DECIDE exists because many agent workflows require the LLM to make a discrete choice rather than produce free-form text. Routing a support ticket, classifying intent, approving or rejecting a request, selecting a category — these are all cases where the output must be one of a fixed set of options. A plain THOUGHT can ask for a choice, but it cannot guarantee the response will match. DECIDE enforces that constraint.

By subclassing THOUGHT, DECIDE inherits the full cognitive pipeline: prompt construction, context injection, LLM invocation, parsing, and validation. It adds choice-specific behavior: automatic presentation of options in the prompt, smart parsing to extract the selection from varied LLM output, validation against allowed choices, and choice-specific repair prompts when retries are needed. This keeps decision logic explicit and reliable.

Within the ThoughtFlow ecosystem, DECIDE sits between raw THOUGHT (unconstrained) and PLAN (structured multi-step output). It is the right primitive when the answer is "which one?" rather than "what?" or "how?"

## How It Works

DECIDE builds a prompt by appending a formatted list of choices to the base prompt, then instructs the LLM to respond with only its choice. When the LLM responds, `parse_response` attempts to extract the selection: first by exact match (after normalization), then by substring search using longest-match-first to avoid partial overlaps. Matching is case-insensitive by default.

If the parsed result fails validation (not in the allowed set), DECIDE appends a repair suffix to the prompt and retries. The repair prompt explicitly lists the valid choices. After `max_retries` attempts (default 5), if no valid choice is obtained and a `default` was configured, that value is stored. Otherwise the last parsed value (or None) is stored.

The result is written to memory at `{name}_result`, consistent with THOUGHT.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `name` | Unique identifier for this decision. |
| `llm` | LLM instance for execution. |
| `prompt` | Prompt template with `{variable}` placeholders. |
| `choices` | Required. List (`["approve", "reject"]`) or dict (`{"approve": "Accept the request", "reject": "Deny the request"}`). Dict values are descriptions shown to the LLM. |
| `default` | Optional. Fallback choice when all retries fail. |
| `case_sensitive` | Whether matching is case-sensitive. Default: False. |
| `max_retries` | Maximum retry attempts. Default: 5. |
| `**kwargs` | Additional THOUGHT parameters (e.g. `context_vars`, `pre_hook`). |

## Usage

```python
from thoughtflow import DECIDE, MEMORY, LLM

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# Simple list of choices
decide = DECIDE(
    name="sentiment",
    llm=llm,
    choices=["positive", "negative", "neutral"],
    prompt="Classify the sentiment of: {text}",
)
memory.set_var("text", "I love this product!")
memory = decide(memory)
result = memory.get_var("sentiment_result")  # "positive", "negative", or "neutral"
```

```python
# Dict with descriptions (shown to LLM)
decide = DECIDE(
    name="route",
    llm=llm,
    choices={
        "approve": "Accept and proceed with the request",
        "reject": "Deny the request",
        "escalate": "Send to human reviewer",
    },
    prompt="Decide how to handle: {request}",
    default="escalate",
)
memory.set_var("request", "Customer wants a refund.")
memory = decide(memory)
result = memory.get_var("route_result")
```

## Relationship to Other Primitives

- **THOUGHT**: DECIDE is a subclass. It inherits prompt building, context injection, execution history, serialization (`to_dict`/`from_dict`), and the `memory = decide(memory)` contract.
- **PLAN**: Both constrain LLM output. DECIDE constrains to a single choice; PLAN constrains to a structured multi-step plan. Use DECIDE for routing or classification; use PLAN when you need a sequence of actions.
- **WORKFLOW**: WORKFLOW can orchestrate DECIDE steps (e.g. decide, then branch on the result).
- **AGENT**: An agent loop may use DECIDE internally for routing or confirmation steps.

## Considerations for Future Development

- Support for weighted or ranked choices (e.g. top-k).
- Optional confidence score alongside the chosen value.
- Integration with structured output APIs when available (native schema enforcement instead of text parsing).
- Allow choices to be dynamically loaded from memory (e.g. `choices="{available_options}"`).
