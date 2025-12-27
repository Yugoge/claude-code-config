#!/usr/bin/env python3
"""
Preloaded TodoList for /clean workflow.

Aggressive project cleanup with orchestrated multi-agent workflow.
"""


def get_todos():
    """
    Return list of todo items for TodoWrite.

    Returns:
        list[dict]: Todo items with content, activeForm, status
    """
    return [
        {"content": "Step 1: Scan Project Structure", "activeForm": "Step 1: Scanning Project Structure", "status": "pending"},
        {"content": "Step 2: Invoke Cleanliness Inspector", "activeForm": "Step 2: Invoking Cleanliness Inspector", "status": "pending"},
        {"content": "Step 3: Invoke Style Inspector", "activeForm": "Step 3: Invoking Style Inspector", "status": "pending"},
        {"content": "Step 4: Merge Inspection Reports", "activeForm": "Step 4: Merging Inspection Reports", "status": "pending"},
        {"content": "Step 5: Present Combined Report to User", "activeForm": "Step 5: Presenting Combined Report to User", "status": "pending"},
        {"content": "Step 6: Collect User Approval", "activeForm": "Step 6: Collecting User Approval", "status": "pending"},
        {"content": "Step 7: Create Safety Checkpoint (Git Commit)", "activeForm": "Step 7: Creating Safety Checkpoint", "status": "pending"},
        {"content": "Step 8: Invoke Cleaner with Approvals", "activeForm": "Step 8: Invoking Cleaner with Approvals", "status": "pending"},
        {"content": "Step 9: Verify Cleanup Results", "activeForm": "Step 9: Verifying Cleanup Results", "status": "pending"},
        {"content": "Step 10: Generate Completion Report", "activeForm": "Step 10: Generating Completion Report", "status": "pending"}
    ]


if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
