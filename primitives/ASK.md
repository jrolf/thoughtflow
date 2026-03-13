# ASK

> Human-in-the-loop input primitive for prompting the user and storing responses.

## Philosophy

Agents sometimes need information only a human can provide: preferences, confirmations, credentials, or clarifications. ASK is the primitive for that. It blocks execution, displays a prompt, waits for input, and stores the response in memory. It is the counterpart to SAY: SAY delivers output; ASK collects input.

ASK supports validation with retry. If the user enters invalid data, a custom validator can reject it and show a retry prompt. Timeout support lets you avoid indefinite blocking in automated or headless contexts; a default value is used when the user does not respond in time. The response is always added to memory as a user message, so the conversation history stays consistent.

## How It Works

ASK is constructed with a prompt, a required `store_as` (memory key for the response), and optional timeout, default, validator, and retry settings. The prompt can be a str with `{variable}` placeholders or a callable `(memory) -> str`.

On execution, the prompt is resolved and displayed. Input is collected via `input()` or, if timeout is set, via a daemon thread that runs `input()` and returns the default if the thread does not finish within the timeout. If a validator is provided, the response is checked; on failure, the retry prompt is shown and input is collected again, up to `max_retries` times.

The final response (or default) is stored in memory at `store_as` and added as a user message via `memory.add_msg("user", response, channel="cli")`. The return value is the response string (or default). Serialization works for static prompts; the validator callable cannot be serialized and must be passed to `from_dict` when reconstructing.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `prompt` | Question to display. Str with `{variable}` placeholders or callable `(memory) -> str`. |
| `store_as` | Memory variable for the response (required). |
| `name` | Identifier for this action (default: `"ask"`). |
| `timeout` | Seconds to wait for input. None = wait forever. |
| `default` | Value to use on timeout or empty input. |
| `validator` | Callable `(input) -> bool` to validate input. Not serializable. |
| `retry_prompt` | Message shown on validation failure (default: `"Invalid input. Please try again:"`). |
| `max_retries` | Maximum validation retry attempts (default: 3). |

## Usage

```python
from thoughtflow.actions import ASK
from thoughtflow import MEMORY

# Simple question
ask = ASK(
    prompt="What is your name?",
    store_as="user_name"
)
memory = ask(MEMORY())
name = memory.get_var("user_name")

# With validation
def valid_number(x):
    return x.isdigit() and 1 <= int(x) <= 10

ask = ASK(
    prompt="Enter a number between 1-10:",
    store_as="choice",
    validator=valid_number,
    retry_prompt="Invalid! Please enter a number 1-10:"
)
memory = ask(memory)

# With timeout and default
ask = ASK(
    prompt="Continue? (y/n):",
    store_as="continue",
    timeout=30,
    default="y"
)

# Dynamic prompt from memory
ask = ASK(
    prompt=lambda m: "Hello {}! What would you like to do?".format(
        m.get_var("user_name", "there")
    ),
    store_as="user_intent"
)
```

## Relationship to Other Primitives

- **ACTION**: ASK is a subclass of ACTION. It inherits memory integration, execution tracking, and serialization (validator excluded).
- **SAY**: ASK gets input; SAY delivers output. They form the basic user interaction pair.
- **CHAT**: CHAT wraps interactive conversation. ASK is a lower-level primitive for single-turn prompts. CHAT may use ASK internally or provide a richer multi-turn interface.
- **MEMORY**: The response is stored at `store_as` and added as a user message. The prompt can reference memory via `{variable}`.
- **WORKFLOW**: ASK can be a workflow step when human approval or input is required mid-flow.

## Considerations for Future Development

- Password-style input (no echo) for sensitive data.
- Choice menus (select from list) as a structured alternative to free text.
- Non-blocking or async variant for environments where blocking input is problematic.
- Integration with CHAT so ASK can be satisfied from the chat stream when available.
- History of previous ASK responses for context in long sessions.
