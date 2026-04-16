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
        {"content": "Step 1: Initialize Workflow and Load TodoList", "activeForm": "Step 1: Initializing Workflow and Loading TodoList", "status": "pending"},
        {"content": "Step 2: Analyze Git History for Edge Cases", "activeForm": "Step 2: Analyzing Git History for Edge Cases", "status": "pending"},
        {"content": "Step 3: Migrate test/ to tests/ if Needed", "activeForm": "Step 3: Migrating test/ to tests/", "status": "pending"},
        {"content": "Step 4: Cleanup tests/ Based on Git History", "activeForm": "Step 4: Cleaning Up tests/ Based on Git History", "status": "pending"},
        {"content": "Step 5: Check Test Folder Exists", "activeForm": "Step 5: Checking Test Folder", "status": "pending"},
        {"content": "Step 6: Discover Validators", "activeForm": "Step 6: Discovering Validators", "status": "pending"},
        {"content": "Step 7: Build Validation Context", "activeForm": "Step 7: Building Validation Context", "status": "pending"},
        {"content": "Step 8: Invoke Test Validator", "activeForm": "Step 8: Validating Tests", "status": "pending"},
        {"content": "Step 9: Process Validation Results", "activeForm": "Step 9: Processing Validation Results", "status": "pending"},
        {"content": "Step 10: Build Execution Context", "activeForm": "Step 10: Building Execution Context", "status": "pending"},
        {"content": "Step 11: Create Safety Checkpoint", "activeForm": "Step 11: Creating Safety Checkpoint", "status": "pending"},
        {"content": "Step 12: Invoke Test Executor", "activeForm": "Step 12: Executing Tests", "status": "pending"},
        {"content": "Step 13: Process Execution Results", "activeForm": "Step 13: Processing Execution Results", "status": "pending"},
        {"content": "Step 14: Present Test Failures to User", "activeForm": "Step 14: Presenting Test Failures", "status": "pending"},
        {"content": "Step 15: Collect User Decision", "activeForm": "Step 15: Collecting User Decision", "status": "pending"},
        {"content": "Step 16: Generate Completion Report", "activeForm": "Step 16: Generating Completion Report", "status": "pending"}
    ]



if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
