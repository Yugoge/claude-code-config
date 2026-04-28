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
        {"content": "Step 1: Initialize Workflow", "activeForm": "Step 1: Initializing Workflow", "status": "pending"},
        {"content": "Step 2: Scan Project Structure", "activeForm": "Step 2: Scanning Project Structure", "status": "pending"},
        {"content": "Step 3: Build Inspection Context", "activeForm": "Step 3: Building Inspection Context", "status": "pending"},
        {"content": "Step 4: Rule Initialization (MANDATORY PRE-INSPECTION)", "activeForm": "Step 4: Initializing Folder Rules", "status": "pending"},
        {"content": "Step 5: Invoke Cleanliness Inspector", "activeForm": "Step 5: Invoking Cleanliness Inspector", "status": "pending", "subagent_call": {"agent": "cleanliness-inspector", "subagent_type": "cleanliness-inspector"}},
        {"content": "Step 6: Invoke Style Inspector", "activeForm": "Step 6: Invoking Style Inspector", "status": "pending", "subagent_call": {"agent": "style-inspector", "subagent_type": "style-inspector"}},
        {"content": "Step 7: Plan Style Inspection", "activeForm": "Step 7: Planning Style Inspection", "status": "pending"},
        {"content": "Step 8: Launch Parallel Style Inspectors", "activeForm": "Step 8: Launching Parallel Style Inspectors", "status": "pending"},
        {"content": "Step 9: Collect and Merge Results", "activeForm": "Step 9: Collecting and Merging Results", "status": "pending"},
        {"content": "Step 10: Coverage Verification (MANDATORY GATE)", "activeForm": "Step 10: Verifying Coverage", "status": "pending"},
        {"content": "Step 11: Merge Inspection Reports", "activeForm": "Step 11: Merging Inspection Reports", "status": "pending"},
        {"content": "Step 12: Present Combined Report to User", "activeForm": "Step 12: Presenting Combined Report to User", "status": "pending"},
        {"content": "Step 13: Collect User Approval", "activeForm": "Step 13: Collecting User Approval", "status": "pending"},
        {"content": "Step 13b: Completeness verification gate (Option 1 only)", "activeForm": "Step 13b: Verifying cleanup completeness", "status": "pending"},
        {"content": "Step 14: Create Safety Checkpoint (Git Commit)", "activeForm": "Step 14: Creating Safety Checkpoint", "status": "pending"},
        {"content": "Step 15: Invoke Cleaner with Approvals", "activeForm": "Step 15: Invoking Cleaner with Approvals", "status": "pending", "subagent_call": {"agent": "cleaner", "subagent_type": "cleaner"}},
        {"content": "Step 16: Verify Cleanup Results", "activeForm": "Step 16: Verifying Cleanup Results", "status": "pending"},
        {"content": "Step 17: Generate Completion Report", "activeForm": "Step 17: Generating Completion Report", "status": "pending"}
    ]



if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
