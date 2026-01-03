#!/usr/bin/env python3
"""
Global PreToolUse Hook: Todo Injection for Slash Commands

This hook runs BEFORE SlashCommand tool execution and:
1. Detects the command being executed (e.g., /ask, /learn, /save)
2. Looks for project-specific todo script at scripts/todo/{command}.py
3. Executes the script and injects output into Claude's prompt
4. Returns with hookSpecificOutput.additionalContext for forced injection

This is a GLOBAL hook (~/.claude/hooks/) that works across ALL projects.
Each project can have its own todo scripts in scripts/todo/{command}.py

Usage:
- Place project-specific todo generators in: $PROJECT/scripts/todo/{command}.py
- Each script should output JSON array of todo objects
- Hook automatically injects todos BEFORE command execution
- Claude MUST process todos (not advisory - forced via additionalContext)
"""

import sys
import json
import subprocess
from pathlib import Path
import os


def extract_command_name(command_string: str) -> str:
    """
    Extract command name from slash command string.

    Examples:
        "/learn file.pdf" → "learn"
        "/save topic" → "save"
        "/review" → "review"

    Args:
        command_string: Full command string from tool input

    Returns:
        Command name without leading slash
    """
    if not command_string or not command_string.startswith("/"):
        return ""

    # Split and get first word, remove leading slash
    parts = command_string.split()
    if not parts:
        return ""

    cmd_name = parts[0][1:]  # Remove leading "/"

    # Handle nested commands (e.g., "/dev:implement" → "dev")
    # Only take first part before colon
    if ":" in cmd_name:
        cmd_name = cmd_name.split(":")[0]

    return cmd_name


def find_todo_script(cmd_name: str) -> Path | None:
    """
    Find project-specific todo script for command.

    Search order (tries all paths, returns first match):
    1. $CLAUDE_PROJECT_DIR/scripts/todo/{cmd_name}.py
    2. Current working directory/scripts/todo/{cmd_name}.py
    3. ~/.claude/scripts/todo/{cmd_name}.py (global fallback)
    4. $CLAUDE_PROJECT_DIR/.claude/scripts/todo/{cmd_name}.py
    5. Current working directory/.claude/scripts/todo/{cmd_name}.py

    Args:
        cmd_name: Command name (e.g., "ask", "learn")

    Returns:
        Path to todo script if found, None otherwise
    """
    search_paths = []

    # 1. Project directory from environment variable
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        search_paths.append(Path(project_dir) / "scripts" / "todo" / f"{cmd_name}.py")
        search_paths.append(Path(project_dir) / ".claude" / "scripts" / "todo" / f"{cmd_name}.py")

    # 2. Current working directory
    cwd = Path.cwd()
    search_paths.append(cwd / "scripts" / "todo" / f"{cmd_name}.py")
    search_paths.append(cwd / ".claude" / "scripts" / "todo" / f"{cmd_name}.py")

    # 3. Global fallback in home directory
    home = Path.home()
    search_paths.append(home / ".claude" / "scripts" / "todo" / f"{cmd_name}.py")

    # Try each path in order, return first match
    for path in search_paths:
        if path.exists():
            return path

    return None


def execute_todo_script(script_path: Path) -> str:
    """
    Execute todo script and capture output.

    Args:
        script_path: Path to Python script

    Returns:
        Script stdout output (JSON string expected)
    """
    try:
        # Activate venv if it exists in project
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
        venv_activate = Path(project_dir) / "venv" / "bin" / "activate"

        if venv_activate.exists():
            # Run with venv activation
            cmd = f"source {venv_activate} && python {script_path}"
            result = subprocess.run(
                cmd,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                text=True,
                timeout=5
            )
        else:
            # Run directly with python3
            result = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=5
            )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # Return error info for debugging
            return f"# ⚠️ Todo script failed:\n# {result.stderr}"

    except subprocess.TimeoutExpired:
        return "# ⚠️ Todo script timeout (>5s)"
    except Exception as e:
        return f"# ⚠️ Todo script error: {str(e)}"


def format_todo_injection(todos_json: str, cmd_name: str) -> str:
    """
    Format todo JSON into injection message.

    Args:
        todos_json: JSON output from todo script
        cmd_name: Command name for context

    Returns:
        Formatted message for additionalContext
    """
    header = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CRITICAL WORKFLOW REQUIREMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Command: /{cmd_name}

MANDATORY: Use TodoWrite tool NOW with this checklist:

{todos_json}

⚠️ You MUST create todos BEFORE executing workflow.
⚠️ Mark in_progress before each step, completed after.
⚠️ NEVER skip steps.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return header


def main():
    """Main hook execution function."""
    try:
        # Read tool input from stdin
        tool_input = json.load(sys.stdin)
        command = tool_input.get("command", "")

        # Extract command name
        cmd_name = extract_command_name(command)

        if not cmd_name:
            # Not a slash command, allow execution
            return {"status": "allow"}

        # Find todo script
        todo_script = find_todo_script(cmd_name)

        if not todo_script:
            # No todo script for this command, allow execution
            return {"status": "allow"}

        # Execute todo script
        todos_output = execute_todo_script(todo_script)

        if not todos_output or todos_output.startswith("# ⚠️"):
            # Script failed or empty output
            # Still allow execution, but warn
            if todos_output.startswith("# ⚠️"):
                return {
                    "status": "allow",
                    "message": todos_output
                }
            return {"status": "allow"}

        # Format injection message
        injection = format_todo_injection(todos_output, cmd_name)

        # Return with additionalContext for FORCED injection
        return {
            "status": "allow",
            "hookSpecificOutput": {
                "additionalContext": injection
            }
        }

    except Exception as e:
        # On error, allow execution (fail-safe)
        return {
            "status": "allow",
            "message": f"⚠️  Todo injection hook error: {str(e)}"
        }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result))
