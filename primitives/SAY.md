# SAY

> Primary output primitive for agent-to-user communication.

## Philosophy

An agent that cannot speak is an agent that cannot be understood. SAY is the primitive for agents to communicate with users. It is the counterpart to ASK: ASK gets input from the user; SAY delivers output. Every agent needs a way to report progress, show results, or explain what it is doing.

SAY supports multiple channels so the same action can print to the console, append to memory as an assistant message, or invoke a custom handler (e.g. websocket, UI callback). Style hints (info, warning, error, success) add prefixes to console output for quick visual scanning. Variable substitution in the message lets agents personalize output from memory state.

## How It Works

SAY is constructed with a message (str or callable), a channel, and an optional style. The message can include `{variable}` placeholders resolved from memory, or be a callable `(memory) -> str` for fully dynamic content.

On execution, the message is resolved, optionally prefixed with a style string (`[INFO] `, `[WARNING] `, etc.), and sent to the channel. For `channel="console"`, the styled text is printed. For `channel="memory"`, the raw text (without style prefix) is added as an assistant message via `memory.add_msg("assistant", text, channel="api")`. For a callable channel, the handler receives `(raw_text, memory)`.

The return value is a dict: `{"status": "said", "message": str, "channel": str, "style": str}`. Serialization via `to_dict`/`from_dict` works for static messages and built-in channels; callable messages and channels are not serialized.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `message` | Text to output. Str with `{variable}` placeholders or callable `(memory) -> str`. |
| `name` | Identifier for this action (default: `"say"`). |
| `channel` | Output destination: `"console"` (default), `"memory"`, or callable `(text, memory) -> None`. |
| `style` | Optional style hint: `"info"`, `"warning"`, `"error"`, or `"success"`. Prefixes console output. |

## Usage

```python
from thoughtflow.actions import SAY
from thoughtflow import MEMORY

# Simple output
say = SAY(message="Hello, world!")
memory = say(MEMORY())
# Hello, world!

# With variable substitution
memory = MEMORY()
memory.set_var("name", "Alice")
say = SAY(message="Hello, {name}!")
memory = say(memory)
# Hello, Alice!

# Store in memory instead of printing
say = SAY(
    message="Task completed successfully",
    channel="memory"
)
memory = say(memory)

# Style hints for console
say = SAY(message="Something went wrong", style="error")
# [ERROR] Something went wrong

# Custom output handler
def send_to_ui(text, mem):
    websocket.send(text)

say = SAY(message="Status update", channel=send_to_ui)
```

## Relationship to Other Primitives

- **ACTION**: SAY is a subclass of ACTION. It inherits memory integration, execution tracking, and serialization (for non-callable config).
- **ASK**: ASK gets input from the user; SAY delivers output. Together they form the basic user interaction loop.
- **NOTIFY**: NOTIFY is for async, fire-and-forget notifications (console, webhook, email). SAY is for synchronous, in-conversation output. Use SAY when the user is waiting; use NOTIFY when you are alerting someone in the background.
- **MEMORY**: Message supports `{variable}` substitution. With `channel="memory"`, the output is added as an assistant message.
- **CHAT / AGENT**: CHAT and AGENT use SAY (or equivalent) to display agent responses to the user. SAY is the low-level primitive they build on.

## Considerations for Future Development

- Rich output (markdown, tables, syntax highlighting) when channel supports it.
- Streaming: yield message chunks for long outputs instead of one-shot.
- Channel-specific style handling (e.g. memory might store style metadata).
- Localization hooks for message translation before output.
