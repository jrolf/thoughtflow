# IDE Configuration

This guide helps you configure VS Code or PyCharm for ThoughtFlow development.

---

## VS Code (Recommended)

### Required Extensions

Install these extensions for the best experience:

1. **Python** (Microsoft) - Core Python support
2. **Ruff** (Astral Software) - Linting and formatting
3. **Pylance** (Microsoft) - Type checking and IntelliSense

### Install via Command Line

```bash
code --install-extension ms-python.python
code --install-extension charliermarsh.ruff
code --install-extension ms-python.vscode-pylance
```

### Recommended Settings

Create or update `.vscode/settings.json` in your project:

```json
{
    // Python
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",

    // Ruff (linting + formatting)
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    },

    // Type checking
    "python.analysis.typeCheckingMode": "basic",
    "python.analysis.diagnosticMode": "workspace",

    // Testing
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests/unit",
        "-v"
    ],

    // Editor
    "editor.rulers": [88],
    "files.trimTrailingWhitespace": true,
    "files.insertFinalNewline": true
}
```

### Select Python Interpreter

1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "Python: Select Interpreter"
3. Choose the interpreter from `.venv/bin/python`

### Running Tests in VS Code

1. Open the Testing sidebar (flask icon)
2. Click "Configure Python Tests"
3. Select "pytest"
4. Select "tests" as the test directory
5. Click the play button to run tests

### Debugging in VS Code

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "debugpy",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "env": {
                "PYTHONPATH": "${workspaceFolder}/src"
            }
        },
        {
            "name": "Python: pytest",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["tests/unit/", "-v", "-s"],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        },
        {
            "name": "Python: Example Script",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/examples/01_hello_world.py",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

---

## PyCharm

### Configure Project Interpreter

1. Go to **Settings/Preferences** → **Project** → **Python Interpreter**
2. Click the gear icon → **Add**
3. Select **Existing environment**
4. Browse to `.venv/bin/python`
5. Click **OK**

### Enable Ruff

1. Go to **Settings/Preferences** → **Tools** → **External Tools**
2. Click **+** to add a new tool
3. Configure:
   - Name: `Ruff Format`
   - Program: `$PyInterpreterDirectory$/ruff`
   - Arguments: `format $FilePath$`
   - Working directory: `$ProjectFileDir$`

4. Add another tool:
   - Name: `Ruff Check`
   - Program: `$PyInterpreterDirectory$/ruff`
   - Arguments: `check --fix $FilePath$`
   - Working directory: `$ProjectFileDir$`

### Configure pytest

1. Go to **Settings/Preferences** → **Tools** → **Python Integrated Tools**
2. Set **Default test runner** to `pytest`
3. Go to **Run** → **Edit Configurations**
4. Add a new **pytest** configuration:
   - Target: `tests/unit`
   - Additional arguments: `-v`

### Enable Type Checking

1. Go to **Settings/Preferences** → **Editor** → **Inspections**
2. Search for "Type checker"
3. Enable **Type checker compatible with Mypy**
4. Set severity to **Warning** or **Error**

### File Watchers (Auto-format on Save)

1. Go to **Settings/Preferences** → **Tools** → **File Watchers**
2. Click **+** → **Custom**
3. Configure:
   - Name: `Ruff Format`
   - File type: `Python`
   - Program: `$PyInterpreterDirectory$/ruff`
   - Arguments: `format $FilePath$`
   - Output paths: `$FilePath$`
   - Working directory: `$ProjectFileDir$`

---

## Common IDE Tasks

### Format Current File

**VS Code**: `Shift+Alt+F` (or save if format-on-save is enabled)
**PyCharm**: Use the Ruff external tool, or `Ctrl+Alt+L` with plugin

### Run Current Test

**VS Code**: Click the green play button next to the test
**PyCharm**: Click the green play button in the gutter

### Go to Definition

**VS Code**: `F12` or `Cmd+Click`
**PyCharm**: `Ctrl+B` or `Cmd+Click`

### Find All References

**VS Code**: `Shift+F12`
**PyCharm**: `Alt+F7`

### Rename Symbol

**VS Code**: `F2`
**PyCharm**: `Shift+F6`

---

## Terminal Integration

### VS Code Terminal

The integrated terminal automatically activates your virtual environment if configured correctly.

If not, add to settings.json:
```json
{
    "python.terminal.activateEnvironment": true
}
```

### PyCharm Terminal

PyCharm automatically activates the project interpreter in its terminal.

---

## Useful Keyboard Shortcuts

### VS Code

| Action | Mac | Windows/Linux |
|--------|-----|---------------|
| Command Palette | `Cmd+Shift+P` | `Ctrl+Shift+P` |
| Go to File | `Cmd+P` | `Ctrl+P` |
| Find in Files | `Cmd+Shift+F` | `Ctrl+Shift+F` |
| Toggle Terminal | `` Ctrl+` `` | `` Ctrl+` `` |
| Run Tests | `Cmd+; A` | `Ctrl+; A` |

### PyCharm

| Action | Mac | Windows/Linux |
|--------|-----|---------------|
| Search Everywhere | `Shift Shift` | `Shift Shift` |
| Go to File | `Cmd+Shift+O` | `Ctrl+Shift+N` |
| Find in Files | `Cmd+Shift+F` | `Ctrl+Shift+F` |
| Run | `Ctrl+R` | `Shift+F10` |
| Debug | `Ctrl+D` | `Shift+F9` |

---

## Troubleshooting

### VS Code: "Import could not be resolved"

1. Check Python interpreter is set to `.venv`
2. Reload window: `Cmd+Shift+P` → "Reload Window"
3. Ensure package is installed: `pip install -e ".[dev]"`

### PyCharm: Tests not discovered

1. Mark `tests/` as **Test Sources Root**: Right-click → "Mark Directory as" → "Test Sources Root"
2. Invalidate caches: **File** → **Invalidate Caches** → **Invalidate and Restart**

### Ruff not working

1. Ensure Ruff is installed: `pip install ruff`
2. Check extension is installed and enabled
3. Check extension settings point to correct ruff binary

---

## Next Steps

- [04-branching-workflow.md](04-branching-workflow.md) - Start making changes
- [06-running-tests.md](06-running-tests.md) - Run and debug tests
