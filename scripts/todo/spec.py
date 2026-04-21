#!/usr/bin/env python3
"""Preloaded TodoList for /spec workflow (Interview Mode only).

The /spec command supports 4 modes (see ~/.claude/commands/spec.md):
  Mode 1: Quick creation -- /spec <inline text>
  Mode 2: Interview      -- bare /spec (no args)  [todos written here]
  Mode 3: Validate       -- /spec --validate <path>
  Mode 4: List           -- /spec --list

Only Mode 2 (bare /spec) should write todos. prompt-workflow.py's
extract_command_name returns "spec" for ALL four modes, so this script
inspects the CLAUDE_TODO_PROMPT env var (injected by prompt-workflow.py's
run_todo_script) to distinguish Mode 2 from the others. Non-Interview
modes return [] so no bookmark/todos file is written and the spec-block
hook never activates for them.

The 7 steps below map 1:1 to the 7 Interview Flow steps in spec.md.
"""

import json
import os
import sys


# (label, content, activeForm) tuples for each Interview Mode step.
_STEPS = (
    ("1", "Open interview -- ask what the issue or feature is",
           "Opening interview"),
    ("2", "Deep-dive on problem -- ask about current behavior",
           "Deep-diving on problem"),
    ("3", "Acceptance criteria -- ask what done looks like",
           "Gathering acceptance criteria"),
    ("4", "Context and constraints -- ask for additional context",
           "Gathering context and constraints"),
    ("5", "Incorporate exploration results",
           "Incorporating exploration results"),
    ("6", "Preview and confirm spec with user",
           "Previewing and confirming spec"),
    ("7", "Write the spec file",
           "Writing spec file"),
)


def _build_step(label: str, desc: str, active: str) -> dict:
    """Build a single todo item dict from a step tuple."""
    return {
        "content": f"Step {label}: {desc}",
        "activeForm": f"Step {label}: {active}",
        "status": "pending",
    }


def is_interview_mode() -> bool:
    """Return True when the prompt is bare /spec (no arguments).

    Inspects CLAUDE_TODO_PROMPT (set by prompt-workflow.py run_todo_script).
    When the env var is missing or empty, default to Interview Mode so
    that direct CLI invocation (no env var) still prints the 7 steps.
    """
    prompt = os.environ.get("CLAUDE_TODO_PROMPT", "")
    parts = prompt.strip().split(None, 1)
    # Empty prompt or just "/spec" (no second token) -> Interview Mode
    if len(parts) <= 1:
        return True
    return parts[1].strip() == ""


def get_todos() -> list:
    """Return 7 pending Interview Mode steps, or [] for other modes."""
    if not is_interview_mode():
        return []
    return [_build_step(label, desc, active) for label, desc, active in _STEPS]


if __name__ == "__main__":
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
    sys.exit(0)
