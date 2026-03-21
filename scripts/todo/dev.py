#!/usr/bin/env python3
"""
Preloaded TodoList for /dev workflow.

BA-delegated development workflow with quality gates.
"""


def get_todos():
    """
    Return list of todo items for TodoWrite.

    Returns:
        list[dict]: Todo items with content, activeForm, status
    """
    return [
        {"content": "Step 1: Parse development requirement", "activeForm": "Step 1: Parsing development requirement", "status": "pending"},
        {"content": "Step 2: Delegate to BA subagent", "activeForm": "Step 2: Delegating to BA subagent", "status": "pending"},
        {"content": "Step 3: BA clarification loop (if needed)", "activeForm": "Step 3: Running BA clarification loop", "status": "pending"},
        {"content": "Step 4: Validate BA output", "activeForm": "Step 4: Validating BA output", "status": "pending"},
        {"content": "Step 5: Delegate to dev subagent", "activeForm": "Step 5: Delegating to dev subagent", "status": "pending"},
        {"content": "Step 6: Validate dev implementation", "activeForm": "Step 6: Validating dev implementation", "status": "pending"},
        {"content": "Step 7: Delegate to QA subagent", "activeForm": "Step 7: Delegating to QA subagent", "status": "pending"},
        {"content": "Step 8: Process QA results", "activeForm": "Step 8: Processing QA results", "status": "pending"},
        {"content": "Step 9: Update settings.json permissions", "activeForm": "Step 9: Updating settings.json permissions", "status": "pending"},
        {"content": "Step 10: Iteration loop (if QA fails)", "activeForm": "Step 10: Iterating based on QA feedback", "status": "pending"},
        {"content": "Step 11: Generate completion report", "activeForm": "Step 11: Generating completion report", "status": "pending"}
    ]



if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
