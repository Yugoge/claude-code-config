#!/usr/bin/env python3
"""Preloaded TodoList for /close workflow.

Generates workflow steps for the /close multi-round QA-vs-Codex debate closure
command. Follows the _STEPS tuple + _build_step() helper pattern from
dev-command.py (NOT the inline list-of-dicts pattern in dev.py).

Step count: 10 (load-input, early-exit-check, 3 rounds x 2 parties = 6,
evaluate-verdict, write-report)
"""


# (label, content, activeForm, extra_meta) tuples for each step
_STEPS = [
    ("1", "Load input context (auto-detect newest ba-spec/qa-report at top-level docs/dev/ or use argument)", "Loading input context", None),
    ("2", "Early-exit check (validate input file exists and is non-empty)", "Running early-exit check", None),
    ("3", "Round 1 — QA initial assessment", "Running Round 1 QA assessment", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("4", "Round 1 — Codex adversarial challenge", "Running Round 1 Codex challenge", {"skill_call": {"skill": "codex"}}),
    ("5", "Round 2 — QA response to Codex challenge (skip if round-1 unanimous YES)", "Running Round 2 QA response", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("6", "Round 2 — Codex counter-challenge (skip if round-1 unanimous YES)", "Running Round 2 Codex counter-challenge", {"skill_call": {"skill": "codex"}}),
    ("7", "Round 3 — QA final position (skip if prior unanimous YES)", "Running Round 3 QA final position", {"subagent_call": {"agent": "qa", "subagent_type": "qa"}}),
    ("8", "Round 3 — Codex final challenge (skip if prior unanimous YES)", "Running Round 3 Codex final challenge", {"skill_call": {"skill": "codex"}}),
    ("9", "Evaluate verdict (unanimous-consent rule on final active round)", "Evaluating verdict", None),
    ("10", "Write close-report-<timestamp>.md and print one-line final verdict", "Writing report and printing verdict", None),
]


def _build_step(label, desc, active, meta):
    """Build a single todo item dict from step tuple."""
    item = {
        "content": f"Step {label}: {desc}",
        "activeForm": f"Step {label}: {active}",
        "status": "pending",
    }
    if meta:
        item.update(meta)
    return item


def get_todos():
    """Return workflow steps as TodoWrite-compatible list."""
    return [
        _build_step(label, desc, active, meta)
        for label, desc, active, meta in _STEPS
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
