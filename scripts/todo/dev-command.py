#!/usr/bin/env python3
"""Preloaded TodoList for /dev-command workflow.

This todo script generates workflow steps for the BA-delegated dev-command workflow
with command development best practices.
"""


# (content, activeForm, extra_meta) tuples for each step
_STEPS = [
    ("Parse development requirement", "Parsing development requirement", None),
    ("Delegate to BA subagent", "Delegating to BA subagent", {"subagent_call": {"agent": "ba", "subagent_type": "ba"}}),
    ("BA clarification loop (if needed)", "Running BA clarification loop", None),
    ("Validate BA output", "Validating BA output", None),
    ("Delegate to dev subagent", "Delegating to dev subagent", {"subagent_call": {"agent": "dev", "subagent_type": "dev"}}),
    ("Validate dev implementation", "Validating dev implementation", None),
    ("Delegate to QA subagent", "Delegating to QA subagent", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("Process QA results", "Processing QA results", None),
    ("Update settings.json permissions", "Updating settings.json permissions", None),
    ("Iteration loop (if QA fails)", "Executing iteration loop", None),
    ("Generate completion report", "Generating completion report", None),
]


def _build_step(index, desc, active, meta):
    """Build a single todo item dict from step tuple."""
    item = {
        "content": f"Step {index}: {desc}",
        "activeForm": f"Step {index}: {active}",
        "status": "pending",
    }
    if meta:
        item.update(meta)
    return item


def get_todos():
    """Return workflow steps as TodoWrite-compatible list."""
    return [
        _build_step(i + 1, desc, active, meta)
        for i, (desc, active, meta) in enumerate(_STEPS)
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
