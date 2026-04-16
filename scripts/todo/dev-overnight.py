#!/usr/bin/env python3
"""
Preloaded TodoList for /dev-overnight workflow.

Autonomous overnight development loop with continuous
exploration and fix cycles (16 steps). State file is created
by the UserPromptSubmit hook; Step 1 handles worktree setup.

PM is invoked 3 times per cycle: Plan (2a), Triage (2c), Retro (13).
"""

# (label, content, activeForm, extra_meta) tuples for each step
_STEPS = [
    ("1", "Create worktree (first run only)", "Creating worktree", None),
    (
        "2",
        "Explore codebase for issues (PM plan + PM-recommended specialists + PM triage)",
        "Exploring codebase for issues",
        {"subagent_call": [
            {"agent": "pm", "subagent_type": "pm"},
        ]},
    ),
    ("2d", "Create overnight spec files", "Creating overnight spec files", None),
    ("3", "Create parallel pipelines from PM triage", "Creating parallel pipelines from PM triage", None),
    ("3a", "Convert focus to QA verification criteria", "Converting focus to QA verification criteria", None),
    (
        "4",
        "Run all BA subagents (parallel)",
        "Running all BA subagents in parallel",
        {"subagent_call": {"agent": "ba", "subagent_type": "ba"}},
    ),
    ("5", "Validate all BA outputs", "Validating all BA outputs", None),
    (
        "5a",
        "QA validates BA conclusions (all pipelines, parallel)",
        "QA validating BA conclusions for all pipelines",
        {"subagent_call": {"agent": "qa", "subagent_type": "qa"}},
    ),
    ("5b", "BA-QA iteration loop (if QA rejects BA)", "Iterating BA analysis based on QA objections", None),
    (
        "6",
        "Run all Dev subagents (parallel)",
        "Running all Dev subagents in parallel",
        {"subagent_call": {"agent": "dev", "subagent_type": "dev"}},
    ),
    ("7", "Validate all Dev implementations", "Validating all Dev implementations", None),
    (
        "8",
        "PM QA Prep (rebuild Docker + write QA verification plans)",
        "PM preparing QA environment and verification plans",
        {"subagent_call": {"agent": "pm", "subagent_type": "pm"}},
    ),
    (
        "9",
        "Run all QA subagents (parallel)",
        "Running all QA subagents in parallel",
        {"subagent_call": {"agent": "qa", "subagent_type": "qa"}},
    ),
    ("10", "Process all QA results", "Processing all QA results", None),
    ("11", "Run iteration loops for failed pipelines", "Running iteration loops for failed pipelines", None),
    ("12", "Update settings.json permissions (aggregated)", "Updating settings.json permissions", None),
    ("13", "Log all cycle results and check time", "Logging all cycle results and checking time", None),
    (
        "14",
        "PM Retrospective (cycle summary + next-cycle handoff)",
        "Running PM Retrospective",
        {"subagent_call": {"agent": "pm", "subagent_type": "pm"}},
    ),
    ("15", "Generate summary report or loop", "Generating summary report or looping", None),
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
    """Return todo items for the dev-overnight workflow (16 steps)."""
    return [
        _build_step(label, desc, active, meta)
        for label, desc, active, meta in _STEPS
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
