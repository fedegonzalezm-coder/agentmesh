from __future__ import annotations

import subprocess
from pathlib import Path

_BASH_ALLOWLIST = ("grep", "find", "cat", "ls", "git log", "git show", "git diff", "git blame", "wc", "head", "tail")

READ_FILE_SCHEMA: dict = {
    "name": "read_file",
    "description": "Read the contents of a file. Path is relative to the project working directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative or absolute path to the file"},
        },
        "required": ["path"],
    },
}

BASH_READONLY_SCHEMA: dict = {
    "name": "bash_readonly",
    "description": (
        "Run a read-only shell command to investigate the codebase. "
        f"Allowed commands: {', '.join(_BASH_ALLOWLIST)}. "
        "No write operations, no network calls."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
        },
        "required": ["command"],
    },
}

BUILTIN_TOOLS: dict[str, dict] = {
    "read_file": READ_FILE_SCHEMA,
    "bash_readonly": BASH_READONLY_SCHEMA,
}


def execute_tool(name: str, input: dict, working_dir: str | Path) -> str:
    working_dir = Path(working_dir)
    if name == "read_file":
        return _read_file(input["path"], working_dir)
    if name == "bash_readonly":
        return _bash_readonly(input["command"], working_dir)
    return f"Unknown tool: {name}"


def _read_file(path: str, working_dir: Path) -> str:
    target = Path(path) if Path(path).is_absolute() else working_dir / path
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except IsADirectoryError:
        return f"Error: {path} is a directory, not a file"
    except Exception as exc:
        return f"Error reading file: {exc}"


def _bash_readonly(command: str, working_dir: Path) -> str:
    stripped = command.strip()
    if not any(stripped.startswith(allowed) for allowed in _BASH_ALLOWLIST):
        allowed_list = ", ".join(_BASH_ALLOWLIST)
        return (
            f"Error: command not allowed. Only read-only commands are permitted: {allowed_list}. "
            f"Received: {stripped!r}"
        )
    try:
        result = subprocess.run(
            stripped,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(working_dir),
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        return output or "(empty output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds"
    except Exception as exc:
        return f"Error running command: {exc}"
