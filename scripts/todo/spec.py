#!/usr/bin/env python3
"""Preloaded TodoList for /spec workflow.

Mirrors /root/knowledge-system/scripts/todo/ask.py structure.

/spec has a single mode: Spec Creation Mode. It acts immediately on whatever
the user provides, accumulates multiple requirements into one spec file per
session, and finalizes only on a natural-conclusion strong signal.
"""

import json
import sys


_SPEC_STEPS = (
    ("1", "Parse $ARGUMENTS",
           "Parsing arguments"),
    ("2", "Clarify if truly unclear (max 3 rounds)",
           "Clarifying requirement"),
    ("3", "Write first spec + dispatch background Explore",
           "Writing spec and dispatching exploration"),
    ("4", "Multi-turn accumulation loop (append new requirements to spec)",
           "Accumulating requirements"),
    ("5", "Natural-conclusion detection",
           "Detecting natural conclusion"),
    ("6", "Finalize: split + checkpoints + QA",
           "Finalizing spec"),
    ("7", "Display result",
           "Displaying result"),
)


def _build_step(label: str, desc: str, active: str) -> dict:
    """Build a single todo item dict from a step tuple."""
    return {
        "content": f"Step {label}: {desc}",
        "activeForm": f"Step {label}: {active}",
        "status": "pending",
    }


def get_todos() -> list:
    """Return the 7-step Spec Creation Mode todo list."""
    return [_build_step(label, desc, active) for label, desc, active in _SPEC_STEPS]


def get_blocking_count() -> int:
    """Steps 1-3 must complete before Claude can stop.
    (Parse, Clarify, Write first spec + dispatch Explore)
    Steps 4-7 are session-duration: multi-turn loop, conclusion detection,
    finalize, and display -- these run until natural-conclusion signal fires.
    """
    return 3


if __name__ == "__main__":
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
    sys.exit(0)
