#!/usr/bin/env python3
"""
Preloaded TodoList for /dev-overnight workflow.

Autonomous overnight development loop with continuous
exploration and fix cycles (13 steps). State file is created
by the UserPromptSubmit hook; Step 1 handles worktree setup.
"""

# (content, activeForm) tuples for each step
_STEPS = [
    ("Create worktree (first run only)", "Creating worktree"),
    ("Explore codebase for issues (4 specialist subagents)", "Exploring codebase for issues"),
    ("Select and prioritize next issue", "Selecting and prioritizing next issue"),
    ("Delegate to BA subagent", "Delegating to BA subagent"),
    ("Validate BA output", "Validating BA output"),
    ("Delegate to dev subagent", "Delegating to dev subagent"),
    ("Validate dev implementation", "Validating dev implementation"),
    ("Delegate to QA subagent", "Delegating to QA subagent"),
    ("Process QA results", "Processing QA results"),
    ("Update settings.json permissions", "Updating settings.json permissions"),
    ("Iteration loop (if QA fails)", "Running iteration loop"),
    ("Log cycle results and check time", "Logging cycle results and checking time"),
    ("Generate summary report or loop", "Generating summary report or looping"),
]


def get_todos():
    """Return todo items for the dev-overnight workflow (13 steps)."""
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
