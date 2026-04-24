#!/usr/bin/env python3
"""Preloaded TodoList for /close workflow.

/close is a true wrapper. It has exactly 3 orchestration steps:
  1. Load input (auto-detect newest ba-spec/qa-report or use argument)
  2. Invoke QA subagent once with a debate prompt - QA runs the
     multi-round debate with codex INTERNALLY via the Skill tool
  3. Print the one-line CLOSE: YES/NO verdict that QA returns

Follows the _STEPS tuple + _build_step() + get_todos() pattern from
dev-command.py.
"""


_STEPS = [
    ("1", "Load input (auto-detect newest ba-spec/qa-report at top-level docs/dev/ or use argument)", "Loading input", None),
    ("2", "Invoke QA subagent with debate prompt (QA runs multi-round internal debate with codex, returns CLOSE: YES/NO)", "Invoking QA subagent for internal debate", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("3", "Print CLOSE: YES/NO verdict returned by QA", "Printing QA verdict", None),
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
