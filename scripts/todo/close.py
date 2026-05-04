#!/usr/bin/env python3
"""Preloaded TodoList for /close workflow.

/close orchestration steps (after the parse-layer Step 0a --codex /
Step 0 --force short-circuit branches handled inline in close.md):
  1. Load input (resolve task-id from $ARGUMENTS or conversation context;
     no filesystem scan)
  2a. Dispatch the three inspectors in parallel — orchestrator-only
      authority (style-inspector / cleanliness-inspector / prompt-inspector
      via Agent tool with --changed-files diff scope; reports written to
      docs/dev/{role}-inspector-report-<TASK_ID>.json)
  2b. Invoke QA subagent once with debate prompt — QA reads the 3
      inspector reports as input and runs internal debate; codex
      multi-round when codex_required: true, QA-only single-round
      when false; returns one-line CLOSE: YES/NO verdict
  3. Print the verdict

Letter-suffix sub-steps (2a / 2b) are valid per agents/style-inspector.md
Standard 4 (anchored to integer parent Step 2).

Follows the _STEPS tuple + _build_step() + get_todos() pattern from
dev-command.py.
"""


_STEPS = [
    ("1", "Load input (spec path from $ARGUMENTS or from conversation context; no filesystem scan)", "Resolving spec path from argument or context", None),
    ("2a", "Dispatch three inspectors in parallel (orchestrator-only — style-inspector, cleanliness-inspector, prompt-inspector via Agent tool with --changed-files diff scope)", "Dispatching three inspectors in parallel", None),
    ("2b", "Invoke QA subagent with debate prompt (QA reads 3 inspector reports + runs internal debate; codex when codex_required: true, QA-only when false; returns CLOSE: YES/NO)", "Invoking QA subagent for internal debate", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
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
