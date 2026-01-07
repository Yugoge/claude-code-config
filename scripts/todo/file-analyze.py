#!/usr/bin/env python3
"""
Preloaded TodoList for /file-analyze workflow.

Analyze PDF, Excel, Word, images and other files with deep insights.
"""


def get_todos():
    """
    Return list of todo items for TodoWrite.

    Returns:
        list[dict]: Todo items with content, activeForm, status
    """
    return [
        {"content": "Step 1: Identify File Type", "activeForm": "Step 1: Identifying File Type", "status": "pending"},
        {"content": "Step 2: For Excel Files", "activeForm": "Step 2: Analyzing Excel File", "status": "pending"},
        {"content": "Step 3: For PDF Files", "activeForm": "Step 3: Analyzing PDF File", "status": "pending"},
        {"content": "Step 4: For Images", "activeForm": "Step 4: Analyzing Image File", "status": "pending"},
        {"content": "Step 5: For CSV Files", "activeForm": "Step 5: Analyzing CSV File", "status": "pending"},
        {"content": "Step 6: For Word Documents", "activeForm": "Step 6: Analyzing Word Document", "status": "pending"}
    ]


if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
