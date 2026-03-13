# READ

> File-reading primitive with multiple parse modes and graceful handling of missing files.

## Philosophy

Agents need to read files: configs, data, templates. READ makes that a first-class action with consistent memory integration and error handling. It supports multiple parse modes so you get the right shape—text, JSON, YAML, lines, or raw bytes—without writing boilerplate. Missing files are handled explicitly: raise, return empty, or use a default value.

READ uses only the standard library except for YAML parsing, which requires PyYAML. Paths support `{variable}` substitution and `~` expansion for user home. The result is stored in memory at a configurable key, so downstream steps can access it without extra wiring. A callable parser allows custom parsing logic when the built-in modes are not enough.

## How It Works

READ is constructed with a path (required), parse mode, encoding, and missing-file behavior. The path can be a str with `{variable}` placeholders or a callable `(memory) -> str`. On execution, the path is resolved, `~` is expanded, and the file is opened. For `parse="bytes"`, the file is read in binary mode; otherwise it is read as text with the specified encoding.

If the file does not exist, `on_missing` controls the outcome: `"raise"` (default) raises `FileNotFoundError`; `"empty"` returns `""`, `[]`, `{}`, or `b""` depending on parse mode; `"default"` returns the `default` parameter. Parsing is applied to the content: `"text"` returns the raw string; `"json"` uses `json.loads`; `"yaml"` uses `yaml.safe_load` (PyYAML required); `"lines"` returns `content.splitlines()`; `"bytes"` returns raw bytes; a callable receives `(content, path)` and returns the parsed value.

The result is stored in memory at `store_as` and returned. Serialization via `to_dict`/`from_dict` works for static paths and parse modes; callables are not serialized.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| `path` | File path to read (required). Supports `{variable}` and `~` expansion. Callable `(memory) -> str` allowed. |
| `name` | Identifier for this action (default: `"read"`). |
| `parse` | Parse mode: `"text"` (default), `"json"`, `"yaml"`, `"lines"`, `"bytes"`, or callable `(content, path) -> parsed`. |
| `encoding` | Text encoding (default: `"utf-8"`). |
| `on_missing` | Behavior when file does not exist: `"raise"` (default), `"empty"`, or `"default"`. |
| `default` | Value to return when file is missing and `on_missing="default"`. |
| `store_as` | Memory variable for result (default: `"{name}_content"`). |

## Usage

```python
from thoughtflow.actions import READ
from thoughtflow import MEMORY

# Read text file
read = READ(path="/path/to/file.txt")
memory = read(MEMORY())
content = memory.get_var("read_content")

# Read JSON config
read = READ(
    path="config.json",
    parse="json",
    store_as="config"
)
memory = read(memory)
config = memory.get_var("config")

# Handle missing file gracefully
read = READ(
    path="optional.txt",
    on_missing="default",
    default=""
)

# Dynamic path from memory
read = READ(
    path=lambda m: m.get_var("file_path"),
    parse="json"
)

# Read as lines
read = READ(path="data.txt", parse="lines")
memory = read(memory)
lines = memory.get_var("read_content")
```

## Relationship to Other Primitives

- **ACTION**: READ is a subclass of ACTION. It inherits memory integration, error handling, execution tracking, and serialization.
- **WRITE**: READ reads files; WRITE writes them. They are the file I/O pair.
- **FETCH**: READ reads from the filesystem; FETCH reads from the network. Both store results in memory.
- **MEMORY**: Path supports `{variable}` substitution. The result is stored at `store_as`.
- **TOOL**: Wrap READ in a TOOL to let an LLM decide when to read a file.
- **AGENT / WORKFLOW**: READ is a common step when agents need to load configs or data before processing.

## Considerations for Future Development

- Directory reading (list files, recursive read).
- Large file support: streaming or chunked reads for files that do not fit in memory.
- File watching or change detection for reactive workflows.
- Caching layer to avoid re-reading unchanged files.
- Symlink and permission handling options.
