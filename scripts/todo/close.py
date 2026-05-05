#!/usr/bin/env python3
"""Preloaded TodoList for /close workflow.

/close orchestration steps (flat-integer sequence per
agents/style-inspector.md Standard 4):
  1. --codex flag parsing (applies to non-force paths; sets
     codex_required true|false)
  2. --force flag short-circuit (optional; skipped when --force
     absent — when present, bypasses Steps 5/6 entirely and writes
     a forced close-report)
  3. Load input (resolve task-id from $ARGUMENTS or conversation
     context; no filesystem scan)
  4. Dispatch the three inspectors in parallel — orchestrator-only
     authority (style-inspector / cleanliness-inspector /
     prompt-inspector via Agent tool with --changed-files diff scope;
     reports written to docs/dev/{role}-inspector-report-<TASK_ID>.json)
  5. Invoke QA subagent once with debate prompt — QA reads the 3
     inspector reports as input and runs internal debate; codex
     multi-round when codex_required: true, QA-only single-round
     when false; returns one-line CLOSE: YES/NO verdict
  6. Print the verdict

Follows the _STEPS tuple + _build_step() + get_todos() pattern from
dev-command.py.
"""


_STEPS = [
    ("1", "--codex flag parsing (strip --codex from $ARGUMENTS; set codex_required true|false)", "Parsing --codex flag from arguments", None),
    ("2", "--force flag short-circuit (--force flag short-circuit; skipped when --force absent — when present, bypasses Steps 5/6 entirely and writes forced close-report + audit log)", "Evaluating --force flag short-circuit", None),
    ("3", "Load input (resolve task-id from $ARGUMENTS or from conversation context; no filesystem scan)", "Resolving task-id from argument or context", None),
    ("4", "Dispatch three inspectors in parallel (orchestrator-only — style-inspector, cleanliness-inspector, prompt-inspector via Agent tool with --changed-files diff scope)", "Dispatching three inspectors in parallel", None),
    ("5", "Invoke QA subagent with debate prompt (QA reads 3 inspector reports + runs internal debate; codex when codex_required: true, QA-only when false; returns CLOSE: YES/NO)", "Invoking QA subagent for internal debate", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("6", "Print CLOSE: YES/NO verdict returned by QA", "Printing QA verdict", None),
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
