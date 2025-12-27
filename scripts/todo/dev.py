#!/usr/bin/env python3
"""
Preloaded TodoList for /dev workflow.

Multi-round inquiry and development workflow with quality gates.
"""


def get_todos():
    """
    Return list of todo items for TodoWrite.

    Returns:
        list[dict]: Todo items with content, activeForm, status
    """
    return [
        {"content": "Step 1: Parse Development Requirement", "activeForm": "Step 1: Parsing Development Requirement", "status": "pending"},
        {"content": "Step 2: Multi-Round Requirement Clarification (if needed)", "activeForm": "Step 2: Clarifying Requirements", "status": "pending"},
        {"content": "Step 3: Git Root Cause Analysis", "activeForm": "Step 3: Analyzing Git History for Root Cause", "status": "pending"},
        {"content": "Step 4: Build Comprehensive Context JSON", "activeForm": "Step 4: Building Context JSON", "status": "pending"},
        {"content": "Step 5: Delegate to Dev Subagent", "activeForm": "Step 5: Delegating to Dev Subagent", "status": "pending"},
        {"content": "Step 6: Validate Dev Implementation", "activeForm": "Step 6: Validating Dev Implementation", "status": "pending"},
        {"content": "Step 7: Delegate to QA Subagent", "activeForm": "Step 7: Delegating to QA Subagent", "status": "pending"},
        {"content": "Step 8: Process QA Results", "activeForm": "Step 8: Processing QA Results", "status": "pending"},
        {"content": "Step 9: Update Settings.json Permissions", "activeForm": "Step 9: Updating Settings.json Permissions", "status": "pending"},
        {"content": "Step 10: Iteration Loop (if QA fails)", "activeForm": "Step 10: Iterating Based on QA Feedback", "status": "pending"},
        {"content": "Step 11: Generate Completion Report", "activeForm": "Step 11: Generating Completion Report", "status": "pending"}
    ]


if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
