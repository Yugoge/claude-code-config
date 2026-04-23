#!/usr/bin/env python3
"""Preloaded TodoList for /spec workflow.

The /spec command supports 7 modes (see ~/.claude/commands/spec.md):
  Mode 1: Quick creation   -- /spec <inline text>
  Mode 2: Interview        -- bare /spec (no args)
  Mode 3: Validate         -- /spec --validate <path>
  Mode 4: List             -- /spec --list
  Mode 5: Unlock           -- /spec --unlock <spec-id>
  Mode 6: Batch            -- /spec --batch ...
  Mode 7: Split            -- /spec --split <path>

Mode 2 (Interview) gets interview-specific steps.
Modes 1, 6 (flush), 7 get the general split workflow steps.
Modes 3, 4, 5, 6 (non-flush) are simple operations -- return [].

Inspects CLAUDE_TODO_PROMPT env var (injected by prompt-workflow.py's
run_todo_script) to distinguish modes.
"""

import json
import os
import sys

# Flags that map to simple (no-todo) modes
_SIMPLE_FLAGS = ("--validate", "--list", "--unlock")

# Interview Mode steps (Mode 2)
_INTERVIEW_STEPS = (
    ("1", "Request description from user",
           "Requesting description from user"),
    ("2", "Detect vagueness and handle clarification",
           "Detecting vagueness and handling clarification"),
    ("3", "Dispatch background exploration (if needed)",
           "Dispatching background exploration"),
    ("4", "Write spec file",
           "Writing spec file"),
    ("5", "Invoke spec subagent (split + checkpoints)",
           "Invoking spec subagent"),
    ("6", "QA validation of split quality",
           "QA validating split quality"),
    ("7", "Mark complete and display",
           "Marking complete and displaying"),
)

# General workflow steps (Mode 1 quick, Mode 6 flush, Mode 7 split)
_GENERAL_STEPS = (
    ("1", "Parse arguments and determine mode",
           "Parsing arguments"),
    ("2", "Read/create spec file",
           "Reading/creating spec file"),
    ("3", "Count monolith lines",
           "Counting monolith lines"),
    ("4", "Invoke spec subagent (Phase 0 + 1 + 2)",
           "Running spec subagent"),
    ("5", "QA validation of split quality",
           "QA validating split quality"),
    ("6", "Create .split-complete marker",
           "Marking split as complete"),
    ("7", "Display results",
           "Displaying results"),
)


def _build_step(label: str, desc: str, active: str) -> dict:
    """Build a single todo item dict from a step tuple."""
    return {
        "content": f"Step {label}: {desc}",
        "activeForm": f"Step {label}: {active}",
        "status": "pending",
    }


def _extract_args() -> str:
    """Extract the arguments portion from CLAUDE_TODO_PROMPT."""
    prompt = os.environ.get("CLAUDE_TODO_PROMPT", "").strip()
    parts = prompt.split(None, 1)
    if len(parts) <= 1:
        return ""
    return parts[1].strip()


def _detect_mode() -> str:
    """Detect /spec mode. Returns: interview, quick, split, batch_flush, simple."""
    args = _extract_args()
    if not args:
        return "interview"
    if any(args.startswith(f) for f in _SIMPLE_FLAGS):
        return "simple"
    if args.startswith("--batch"):
        return "batch_flush" if "--flush" in args else "simple"
    if args.startswith("--split"):
        return "split"
    return "quick"


def get_todos() -> list:
    """Return appropriate todo steps based on detected mode."""
    mode = _detect_mode()
    if mode == "interview":
        return [_build_step(l, d, a) for l, d, a in _INTERVIEW_STEPS]
    if mode in ("quick", "split", "batch_flush"):
        return [_build_step(l, d, a) for l, d, a in _GENERAL_STEPS]
    return []


if __name__ == "__main__":
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
    sys.exit(0)
