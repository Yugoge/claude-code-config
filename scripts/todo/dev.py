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
        {"content": "Step 2: Consult specialists (optional)", "activeForm": "Step 2: Consulting specialists", "status": "pending"},
        {"content": "Step 3: Delegate to BA subagent", "activeForm": "Step 3: Delegating to BA subagent", "status": "pending", "subagent_call": {"agent": "ba", "subagent_type": "ba"}},
        {"content": "Step 4: BA clarification loop (if needed)", "activeForm": "Step 4: Running BA clarification loop", "status": "pending"},
        {"content": "Step 5: Validate BA output", "activeForm": "Step 5: Validating BA output", "status": "pending"},
        {"content": "Step 6: QA validates BA conclusions", "activeForm": "Step 6: QA validating BA conclusions", "status": "pending", "subagent_call": {"agent": "qa", "subagent_type": "qa"}},
        {"content": "Step 7: BA-QA iteration loop (if QA rejects BA)", "activeForm": "Step 7: Iterating BA analysis based on QA objections", "status": "pending"},
        {"content": "Step 8: Delegate to dev subagent", "activeForm": "Step 8: Delegating to dev subagent", "status": "pending", "subagent_call": {"agent": "dev", "subagent_type": "dev"}},
        {"content": "Step 9: Write canonical aggregate dev-report (parallel-dev only)", "activeForm": "Step 9: Writing canonical aggregate dev-report", "status": "pending"},
        {"content": "Step 10: Validate dev implementation", "activeForm": "Step 10: Validating dev implementation", "status": "pending"},
        {"content": "Step 11: Delegate to QA subagent", "activeForm": "Step 11: Delegating to QA subagent", "status": "pending", "subagent_call": {"agent": "qa", "subagent_type": "qa"}},
        {"content": "Step 12: Process QA results", "activeForm": "Step 12: Processing QA results", "status": "pending"},
        {"content": "Step 13: Update settings.json permissions", "activeForm": "Step 13: Updating settings.json permissions", "status": "pending"},
        {"content": "Step 14: Iteration loop (if QA fails)", "activeForm": "Step 14: Iterating based on QA feedback", "status": "pending"},
        {"content": "Step 15: Generate completion report and spec/temp update", "activeForm": "Step 15: Generating completion report and spec/temp update", "status": "pending"}
    ]



if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
