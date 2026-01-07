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
        {"content": "Step 1: Analyze Requirements", "activeForm": "Step 1: Analyzing Requirements", "status": "pending"},
        {"content": "Step 2: Select Libraries", "activeForm": "Step 2: Selecting Libraries", "status": "pending"},
        {"content": "Step 3: Create Prototype Structure", "activeForm": "Step 3: Creating Prototype Structure", "status": "pending"},
        {"content": "Step 4: Generate Complete HTML File", "activeForm": "Step 4: Generating Complete HTML File", "status": "pending"},
        {"content": "Step 5: Deliver to User", "activeForm": "Step 5: Delivering to User", "status": "pending"}
    ]


if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
