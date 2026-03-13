# RUN

> Execute shell commands from within a workflow, with output capture, timeout, and error handling.

## Philosophy

Agents sometimes need to interact with the operating system: run a build, execute a script, invoke a CLI tool, or check a system resource. RUN provides a safe, structured way to do this. It wraps Python's `subprocess` module with sensible defaults, integrates with memory for variable substitution, and captures stdout, stderr, return codes, and timing.

RUN is deliberately explicit about security. Shell command execution is powerful but dangerous if user-controlled input flows into commands unsanitized. RUN does not attempt to sanitize automatically; instead, it provides the tools (list-based commands with `shell=False`, variable substitution from controlled memory) and trusts the developer to use them responsibly.

## How It Works

RUN accepts a command as a string, list, or callable. On execution:

1. The command is resolved via variable substitution from memory. If it is a callable, it receives memory and returns the command.
2. The working directory (`cwd`) is resolved and expanded. Custom environment variables are merged with the current environment.
3. If the command is a string, it runs through the shell by default (`shell=True`). If it is a list, `shell` defaults to `False`, which is safer for commands with arguments.
4. `subprocess.run` executes the command with optional timeout. stdout and stderr are captured by default.
5. The result is returned as a structured dict:

```
{
    "command": "echo hello",
    "return_code": 0,
    "stdout": "hello\n",
    "stderr": "",
    "elapsed_ms": 12.34,
    "success": True
}
```

On non-zero exit codes or exceptions, `on_error` controls behavior: `"log"` records the error to memory and returns the result dict, `"raise"` re-raises the exception, `"ignore"` silently returns the result dict.

## Inputs & Configuration

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| command | Yes | - | Command to execute. String (shell), list (no shell), or callable `(memory) -> str\|list`. |
| name | No | "run" | Unique identifier for this action. |
| cwd | No | None | Working directory. Supports `{variable}` substitution and `~` expansion. |
| env | No | None | Extra environment variables (merged with current env). |
| timeout | No | None | Command timeout in seconds. |
| capture | No | True | Capture stdout and stderr. |
| shell | No | auto | Use shell execution. Defaults to True for string commands, False for lists. |
| on_error | No | "log" | Error handling: `"log"`, `"raise"`, or `"ignore"`. |
| store_as | No | "{name}_result" | Memory variable for the result dict. |

## Usage

```python
from thoughtflow.actions import RUN
from thoughtflow import MEMORY

# Simple command
run = RUN(command="echo 'Hello, World!'")
memory = run(MEMORY())
result = memory.get_var("run_result")
print(result["stdout"])  # Hello, World!

# Command with memory variables
memory = MEMORY()
memory.set_var("pattern", "error")
memory.set_var("file", "/var/log/app.log")
run = RUN(command="grep '{pattern}' {file}", timeout=30)
memory = run(memory)

# Safer list-based command (no shell injection)
run = RUN(command=["python", "-c", "print('safe')"], shell=False)
memory = run(MEMORY())

# With working directory and custom environment
run = RUN(
    command="make build",
    cwd="/path/to/project",
    env={"DEBUG": "1"}
)

# Dynamic command from memory
run = RUN(
    command=lambda m: "process {}".format(m.get_var("input_file"))
)
```

## Relationship to Other Primitives

- **ACTION**: RUN is an ACTION subclass. It inherits memory integration, error handling, execution tracking, and serialization.
- **CALL**: CALL invokes Python functions in-process; RUN executes external shell commands. Use CALL for library code, RUN for CLI tools and system operations.
- **FETCH**: FETCH makes HTTP requests; RUN executes local commands. For curl-like operations, prefer FETCH for its structured response handling.
- **WRITE / READ**: RUN can produce files as a side effect of commands. For direct file I/O, prefer WRITE and READ for their structured handling and error modes.
- **MEMORY**: Command strings, cwd, and env values support `{variable}` substitution from memory. Results are stored in memory under `store_as`.

## Considerations for Future Development

- Streaming output for long-running commands (line-by-line stdout/stderr).
- Async execution so workflows can start a command and continue other steps while it runs.
- Built-in command sanitization helpers for common patterns (e.g., shell-escaping user input).
- Process groups or signal handling for graceful cleanup on timeout.
- Support for piping between multiple RUN steps.
