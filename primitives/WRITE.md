# WRITE

> Write content to the filesystem with multiple output modes and flexible path/content resolution.

## Philosophy

WRITE treats file output as a first-class primitive in agent workflows. Rather than scattering ad-hoc file writes across code, WRITE provides a consistent, configurable interface that supports text, structured data (JSON/YAML), append operations, and raw bytes. Parent directories are created by default, and overwrite behavior is explicit. Path and content can be static, templated with `{variable}` placeholders, or fully dynamic via callables.

## How It Works

WRITE extends the base ACTION class. On execution, it resolves `path` and `content` through the substitution system: strings support `{variable}` placeholders filled from memory; callables receive `(memory)` and return the resolved value. If `overwrite` is False and the file exists (and mode is not append), WRITE raises `FileExistsError`. When `mkdir` is True, parent directories are created before writing. Content is prepared according to `mode`: text (default), json (auto-serializes dicts/lists), yaml (requires PyYAML), append (adds to existing file), or bytes (raw binary). The result is written and a summary dict is returned.

## Inputs & Configuration

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | No | "write" | Unique identifier for this action |
| path | Yes | - | File path; str with `{variable}` or callable `(memory) -> str` |
| content | No | None | Content to write; str, dict, list, bytes, or callable `(memory) -> content` |
| mode | No | "text" | Output mode: text, json, yaml, append, bytes |
| encoding | No | "utf-8" | Text encoding |
| mkdir | No | True | Create parent directories if needed |
| overwrite | No | True | Overwrite existing file; False raises FileExistsError |
| indent | No | 2 | JSON indentation when mode is json |

## Usage

```python
from thoughtflow.actions import WRITE
from thoughtflow import MEMORY

# Write plain text
write = WRITE(path="output.txt", content="Hello, world!")
memory = write(MEMORY())

# Write JSON from memory variable
write = WRITE(
    path="results.json",
    content=lambda m: m.get_var("results"),
    mode="json"
)
memory = write(memory)

# Append to log file with variable substitution
write = WRITE(
    path="agent.log",
    content="{timestamp}: {message}\n",
    mode="append"
)
memory = memory.set_var("timestamp", "2025-03-13").set_var("message", "Task done")
memory = write(memory)

# Dynamic path from memory
write = WRITE(
    path=lambda m: "output_{}.txt".format(m.get_var("run_id")),
    content=lambda m: m.get_var("output")
)
memory = write(memory)

# Prevent overwrite
write = WRITE(path="config.json", content=data, overwrite=False)
```

## Relationship to Other Primitives

- **READ**: Reads files; WRITE writes them. Use together for file-based workflows.
- **POST**: Sends data over the network; WRITE persists locally.
- **NOOP**: Use `NOOP(reason="...")` instead of WRITE when you want to skip writing conditionally.
- **CALL**: Can wrap custom write logic; WRITE is the standard primitive for filesystem output.

## Considerations for Future Development

- Add atomic write support (write to temp, then rename) for crash safety.
- Consider a `backup` option to preserve existing files before overwrite.
- Support for streaming/large file writes to reduce memory usage.
- Optional checksum or integrity verification after write.
