#!/usr/bin/env python3
"""Preloaded TodoList for /close workflow.

Three user-visible TodoSteps (flat-integer per agents/style-inspector.md
Standard 4):
  1. Dispatch three inspectors in parallel
  2. Delegate close debate to QA subagent
  3. Generate close-report

Flag handling (--codex / --force) and task-id resolution still happen in
commands/close.md body but are no longer TodoSteps — they are script
plumbing, not user-visible work.
"""


_STEPS = [
    ("1", "Dispatch three inspectors in parallel", "Dispatching three inspectors in parallel", None),
    ("2", "Delegate close debate to QA subagent", "Delegating close debate to QA subagent", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("3", "Generate close-report", "Generating close-report", None),
]


def _build_step(label, desc, active, meta):
    item = {
        "content": f"Step {label}: {desc}",
        "activeForm": f"Step {label}: {active}",
        "status": "pending",
    }
    if meta:
        item.update(meta)
    return item


def get_todos():
    return [_build_step(label, desc, active, meta) for label, desc, active, meta in _STEPS]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
