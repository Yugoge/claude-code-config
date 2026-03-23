#!/usr/bin/env python3
"""
Preloaded TodoList for /dev-overnight workflow.

Autonomous overnight development loop with continuous
exploration and fix cycles. State file is created by the
UserPromptSubmit hook; Step 1 handles worktree and cron setup.
"""


def get_todos():
    """Return todo items for the dev-overnight workflow."""
    return [
        {
            "content": "Step 1: Create worktree and set up cron job",
            "activeForm": "Step 1: Creating worktree and setting up cron job",
            "status": "pending",
        },
        {
            "content": "Step 2: Explore codebase for issues",
            "activeForm": "Step 2: Exploring codebase for issues",
            "status": "pending",
        },
        {
            "content": "Step 3: Select and prioritize next issue",
            "activeForm": "Step 3: Selecting and prioritizing next issue",
            "status": "pending",
        },
        {
            "content": "Step 4: Analyze and implement fix",
            "activeForm": "Step 4: Analyzing and implementing fix",
            "status": "pending",
        },
        {
            "content": "Step 5: Verify fix",
            "activeForm": "Step 5: Verifying fix",
            "status": "pending",
        },
        {
            "content": "Step 6: Log cycle results and check time",
            "activeForm": "Step 6: Logging cycle results and checking time",
            "status": "pending",
        },
        {
            "content": "Step 7: Cleanup and generate summary report",
            "activeForm": "Step 7: Cleaning up and generating summary report",
            "status": "pending",
        },
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
