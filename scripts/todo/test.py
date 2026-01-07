#!/usr/bin/env python3
"""
Preloaded TodoList for /test workflow.

Test validation workflow with edge case detection and quality enforcement.
"""


def get_todos():
    """
    Return list of todo items for TodoWrite.

    Returns:
        list[dict]: Todo items with content, activeForm, status
    """
    return [
        {"content": "Step 1: Initialize Workflow", "activeForm": "Step 1: Initializing Workflow", "status": "pending"},
        {"content": "Step 2: Check Test Folder Exists", "activeForm": "Step 2: Checking Test Folder", "status": "pending"},
        {"content": "Step 3: Discover Validators", "activeForm": "Step 3: Discovering Validators", "status": "pending"},
        {"content": "Step 4: Build Validation Context", "activeForm": "Step 4: Building Validation Context", "status": "pending"},
        {"content": "Step 5: Invoke Test Validator", "activeForm": "Step 5: Validating Tests", "status": "pending"},
        {"content": "Step 6: Process Validation Results", "activeForm": "Step 6: Processing Validation Results", "status": "pending"},
        {"content": "Step 7: Build Execution Context", "activeForm": "Step 7: Building Execution Context", "status": "pending"},
        {"content": "Step 8: Create Safety Checkpoint (Git Commit)", "activeForm": "Step 8: Creating Safety Checkpoint", "status": "pending"},
        {"content": "Step 9: Invoke Test Executor", "activeForm": "Step 9: Executing Tests", "status": "pending"},
        {"content": "Step 10: Process Execution Results", "activeForm": "Step 10: Processing Execution Results", "status": "pending"},
        {"content": "Step 11: Present Test Failures to User", "activeForm": "Step 11: Presenting Test Failures", "status": "pending"},
        {"content": "Step 12: Collect User Decision", "activeForm": "Step 12: Collecting User Decision", "status": "pending"},
        {"content": "Step 13: Generate Completion Report", "activeForm": "Step 13: Generating Completion Report", "status": "pending"}
    ]


if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
