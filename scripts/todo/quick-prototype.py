#!/usr/bin/env python3
"""
Preloaded TodoList for /quick-prototype workflow.

Rapidly create interactive prototypes combining React and visualization libraries.
"""


def get_todos():
    """
    Return list of todo items for TodoWrite.

    Returns:
        list[dict]: Todo items with content, activeForm, status
    """
    return [
        {"content": "Step 1: Analyze requirements", "activeForm": "Step 1: Analyzing requirements", "status": "pending"},
        {"content": "Step 2: Select libraries", "activeForm": "Step 2: Selecting libraries", "status": "pending"},
        {"content": "Step 3: Create prototype structure", "activeForm": "Step 3: Creating prototype structure", "status": "pending"},
        {"content": "Step 4: Generate complete HTML file", "activeForm": "Step 4: Generating complete HTML file", "status": "pending"},
        {"content": "Step 5: Deliver result", "activeForm": "Step 5: Delivering result", "status": "pending"}
    ]



if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
