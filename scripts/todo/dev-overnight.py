#!/usr/bin/env python3
"""
Preloaded TodoList for /dev-overnight workflow.

Autonomous overnight development loop with continuous
exploration and fix cycles (14 steps). State file is created
by the UserPromptSubmit hook; Step 1 handles worktree setup.

PM is invoked 3 times per cycle: Plan (2a), Triage (2c), Retro (13).
"""

# (content, activeForm) tuples for each step
_STEPS = [
    ("Create worktree (first run only)", "Creating worktree"),
    ("Explore codebase for issues (PM plan + 4 specialists + PM triage)", "Exploring codebase for issues"),
    ("Create parallel pipelines from PM triage", "Creating parallel pipelines from PM triage"),
    ("Run all BA subagents (parallel)", "Running all BA subagents in parallel"),
    ("Validate all BA outputs", "Validating all BA outputs"),
    ("Run all Dev subagents (parallel)", "Running all Dev subagents in parallel"),
    ("Validate all Dev implementations", "Validating all Dev implementations"),
    ("Run all QA subagents (parallel)", "Running all QA subagents in parallel"),
    ("Process all QA results", "Processing all QA results"),
    ("Run iteration loops for failed pipelines", "Running iteration loops for failed pipelines"),
    ("Update settings.json permissions (aggregated)", "Updating settings.json permissions"),
    ("Log all cycle results and check time", "Logging all cycle results and checking time"),
    ("PM Retrospective (cycle summary + next-cycle handoff)", "Running PM Retrospective"),
    ("Generate summary report or loop", "Generating summary report or looping"),
]


def get_todos():
    """Return todo items for the dev-overnight workflow (14 steps)."""
    return [
        {
            "content": f"Step {i + 1}: {desc}",
            "activeForm": f"Step {i + 1}: {active}",
            "status": "pending",
        }
        for i, (desc, active) in enumerate(_STEPS)
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
