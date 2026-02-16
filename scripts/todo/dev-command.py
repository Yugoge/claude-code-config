#!/usr/bin/env python3
"""Preloaded TodoList for /dev-command workflow.

This todo script generates workflow steps for the enhanced dev-command workflow
with command development best practices.
"""

def get_todos():
    """Return workflow steps as TodoWrite-compatible list."""
    return [
        {
            "content": "Step 0: Initialize workflow checklist",
            "activeForm": "Step 0: Initializing workflow checklist",
            "status": "pending"
        },
        {
            "content": "Step 1: Parse development requirement",
            "activeForm": "Step 1: Parsing development requirement",
            "status": "pending"
        },
        {
            "content": "Step 2: Multi-round requirement clarification",
            "activeForm": "Step 2: Conducting multi-round requirement clarification",
            "status": "pending"
        },
        {
            "content": "Step 3: Git root cause analysis",
            "activeForm": "Step 3: Performing git root cause analysis",
            "status": "pending"
        },
        {
            "content": "Step 4: Build comprehensive context JSON",
            "activeForm": "Step 4: Building comprehensive context JSON",
            "status": "pending"
        },
        {
            "content": "Step 5: Delegate to dev subagent",
            "activeForm": "Step 5: Delegating to dev subagent",
            "status": "pending"
        },
        {
            "content": "Step 6: Validate dev implementation",
            "activeForm": "Step 6: Validating dev implementation",
            "status": "pending"
        },
        {
            "content": "Step 7: Delegate to QA subagent",
            "activeForm": "Step 7: Delegating to QA subagent",
            "status": "pending"
        },
        {
            "content": "Step 8: Process QA results",
            "activeForm": "Step 8: Processing QA results",
            "status": "pending"
        },
        {
            "content": "Step 9: Update settings.json permissions",
            "activeForm": "Step 9: Updating settings.json permissions",
            "status": "pending"
        },
        {
            "content": "Step 10: Iteration loop (if QA fails)",
            "activeForm": "Step 10: Executing iteration loop",
            "status": "pending"
        },
        {
            "content": "Step 11: Generate completion report",
            "activeForm": "Step 11: Generating completion report",
            "status": "pending"
        }
    ]

if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
