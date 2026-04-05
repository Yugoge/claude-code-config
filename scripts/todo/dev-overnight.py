#!/usr/bin/env python3
"""
Preloaded TodoList for /dev-overnight workflow.

Autonomous overnight development loop with continuous
exploration and fix cycles (15 steps). State file is created
by the UserPromptSubmit hook; Step 1 handles worktree setup.

PM is invoked 3 times per cycle: Plan (2a), Triage (2c), Retro (13).
"""

# (content, activeForm, extra_meta) tuples for each step
_STEPS = [
    ("Create worktree (first run only)", "Creating worktree", None),
    (
        "Explore codebase for issues (PM plan + 4 specialists + PM triage)",
        "Exploring codebase for issues",
        {"subagent_call": [
            {"agent": "pm", "subagent_type": "pm"},
            {"agent": "specialist", "subagent_type": "ui-specialist"},
            {"agent": "specialist", "subagent_type": "architect"},
            {"agent": "specialist", "subagent_type": "product-owner"},
            {"agent": "specialist", "subagent_type": "user"},
        ]},
    ),
    ("Create parallel pipelines from PM triage", "Creating parallel pipelines from PM triage", None),
    (
        "Run all BA subagents (parallel)",
        "Running all BA subagents in parallel",
        {"subagent_call": {"agent": "ba", "subagent_type": "ba"}},
    ),
    ("Validate all BA outputs", "Validating all BA outputs", None),
    (
        "Run all Dev subagents (parallel)",
        "Running all Dev subagents in parallel",
        {"subagent_call": {"agent": "dev", "subagent_type": "dev"}},
    ),
    ("Validate all Dev implementations", "Validating all Dev implementations", None),
    (
        "PM QA Prep (rebuild Docker + write QA verification plans)",
        "PM preparing QA environment and verification plans",
        {"subagent_call": {"agent": "pm", "subagent_type": "pm"}},
    ),
    (
        "Run all QA subagents (parallel)",
        "Running all QA subagents in parallel",
        {"subagent_call": {"agent": "qa", "subagent_type": "qa"}},
    ),
    ("Process all QA results", "Processing all QA results", None),
    ("Run iteration loops for failed pipelines", "Running iteration loops for failed pipelines", None),
    ("Update settings.json permissions (aggregated)", "Updating settings.json permissions", None),
    ("Log all cycle results and check time", "Logging all cycle results and checking time", None),
    (
        "PM Retrospective (cycle summary + next-cycle handoff)",
        "Running PM Retrospective",
        {"subagent_call": {"agent": "pm", "subagent_type": "pm"}},
    ),
    ("Generate summary report or loop", "Generating summary report or looping", None),
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
    """Return todo items for the dev-overnight workflow (15 steps)."""
    return [
        _build_step(i + 1, desc, active, meta)
        for i, (desc, active, meta) in enumerate(_STEPS)
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
