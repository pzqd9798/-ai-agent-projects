"""
Tool Definitions & Dispatch Map — the agent's "hands."

Pattern: Dispatch Map (from learn-claude-code s02)
    - TOOLS: list of tool schemas sent to the LLM
    - TOOL_HANDLERS: dict mapping tool name → handler function
    - Adding a new tool = append to TOOLS + add entry to TOOL_HANDLERS
    - The agent loop NEVER changes when tools are added (Open/Closed Principle)

Each handler returns: {"ok": bool, "output": str}
"""

import os
import subprocess
import glob as glob_mod
from pathlib import Path
from typing import Any

WORKDIR = Path.cwd()

# ═══════════════════════════════════════════════════════════════
# Safety: path sandbox
# ═══════════════════════════════════════════════════════════════

def safe_path(p: str) -> Path:
    """Resolve a path and ensure it stays within WORKDIR."""
    path = (WORKDIR / p).resolve()
    if not str(path).startswith(str(WORKDIR.resolve())):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


# ═══════════════════════════════════════════════════════════════
# Tool Handlers
# ═══════════════════════════════════════════════════════════════

def run_bash(command: str) -> dict:
    """
    Execute a shell command. Blocks dangerous patterns.
    Returns {"ok": bool, "output": str}.
    """
    dangerous = ["rm -rf /", "sudo ", "shutdown", "reboot",
                 "> /dev/sda", "mkfs.", "dd if=", ":(){ :|:& };:"]
    for pattern in dangerous:
        if pattern in command.lower():
            return {
                "ok": False,
                "output": f"[BLOCKED] Dangerous command pattern detected: '{pattern}'"
            }

    try:
        r = subprocess.run(
            command, shell=True, cwd=str(WORKDIR),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        output = out[:50000] if out else "(no output)"
        return {"ok": r.returncode == 0, "output": output}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "[ERROR] Command timed out (120s limit)"}
    except (FileNotFoundError, OSError) as e:
        return {"ok": False, "output": f"[ERROR] {e}"}


def run_read_file(path: str, limit: int | None = None) -> dict:
    """Read file contents, optionally truncated to `limit` lines."""
    try:
        file_path = safe_path(path)
        if not file_path.exists():
            return {"ok": False, "output": f"[ERROR] File not found: {path}"}
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)
        if limit and limit < total:
            lines = lines[:limit]
            lines.append(f"... (truncated: {total - limit} more lines, {total} total)")
        return {"ok": True, "output": "\n".join(lines)}
    except ValueError as e:
        return {"ok": False, "output": f"[ERROR] {e}"}
    except Exception as e:
        return {"ok": False, "output": f"[ERROR] Read failed: {e}"}


def run_write_file(path: str, content: str) -> dict:
    """Write content to a file. Creates parent directories if needed."""
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        size = len(content.encode("utf-8"))
        return {"ok": True, "output": f"Wrote {size} bytes to {path}"}
    except ValueError as e:
        return {"ok": False, "output": f"[ERROR] {e}"}
    except Exception as e:
        return {"ok": False, "output": f"[ERROR] Write failed: {e}"}


def run_edit_file(path: str, old_text: str, new_text: str) -> dict:
    """Replace first occurrence of old_text with new_text in a file."""
    try:
        file_path = safe_path(path)
        if not file_path.exists():
            return {"ok": False, "output": f"[ERROR] File not found: {path}"}
        text = file_path.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            return {
                "ok": False,
                "output": f"[ERROR] Text not found in {path}. "
                          f"File has {len(text)} characters.",
            }
        new_text_actual = text.replace(old_text, new_text, 1)
        file_path.write_text(new_text_actual, encoding="utf-8")
        return {
            "ok": True,
            "output": f"Edited {path}: replaced 1 occurrence ({count} total matches in file)"
        }
    except ValueError as e:
        return {"ok": False, "output": f"[ERROR] {e}"}
    except Exception as e:
        return {"ok": False, "output": f"[ERROR] Edit failed: {e}"}


def run_glob(pattern: str) -> dict:
    """Find files matching a glob pattern within WORKDIR."""
    try:
        results = []
        for match in glob_mod.glob(pattern, root_dir=WORKDIR, recursive=True):
            full_path = (WORKDIR / match).resolve()
            if str(full_path).startswith(str(WORKDIR.resolve())):
                results.append(match)
        if not results:
            return {"ok": True, "output": "(no files matched)"}
        return {"ok": True, "output": "\n".join(sorted(results))}
    except Exception as e:
        return {"ok": False, "output": f"[ERROR] Glob failed: {e}"}


# ═══════════════════════════════════════════════════════════════
# Tool Schemas (sent to LLM)
# ═══════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command in the workspace directory. "
                       "Use for: creating dirs, running Python, installing packages, "
                       "git operations, file operations not covered by other tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute."
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file. "
                       "Use before editing to understand current content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to workspace."
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional: max lines to read."
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with new content. "
                       "Use for: creating new files, or completely replacing file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to workspace."
                },
                "content": {
                    "type": "string",
                    "description": "The complete file content to write."
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace one occurrence of old_text with new_text in a file. "
                       "Use for: small targeted changes without rewriting the entire file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to workspace."
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to replace (must match, including whitespace)."
                },
                "new_text": {
                    "type": "string",
                    "description": "The replacement text."
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern (e.g., '**/*.py', 'src/**/*.ts'). "
                       "Use for: discovering project structure, finding files by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (supports ** for recursive)."
                },
            },
            "required": ["pattern"],
        },
    },
]

# ═══════════════════════════════════════════════════════════════
# Dispatch Map (tool name → handler function)
#
# The core insight from learn-claude-code s02:
#   Adding a tool = adding an entry here + a schema above.
#   The agent loop code (core.py) NEVER changes.
# ═══════════════════════════════════════════════════════════════

TOOL_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read_file,
    "write_file": run_write_file,
    "edit_file": run_edit_file,
    "glob": run_glob,
}


def execute_tool(name: str, params: dict) -> dict:
    """
    Execute a tool by name. Returns {"ok": bool, "output": str}.
    This is the single entry point the agent loop calls.
    """
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "output": f"[ERROR] Unknown tool: '{name}'"}
    try:
        return handler(**params)
    except TypeError as e:
        return {"ok": False, "output": f"[ERROR] Bad params for '{name}': {e}"}
    except Exception as e:
        return {"ok": False, "output": f"[ERROR] Tool '{name}' crashed: {e}"}
