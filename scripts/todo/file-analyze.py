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
        {"content": "Step 1: Identify file type", "activeForm": "Step 1: Identifying file type", "status": "pending"},
        {"content": "Step 2: Process Excel file (if applicable)", "activeForm": "Step 2: Processing Excel file", "status": "pending"},
        {"content": "Step 3: Process PDF file (if applicable)", "activeForm": "Step 3: Processing PDF file", "status": "pending"},
        {"content": "Step 4: Process image file (if applicable)", "activeForm": "Step 4: Processing image file", "status": "pending"},
        {"content": "Step 5: Process CSV file (if applicable)", "activeForm": "Step 5: Processing CSV file", "status": "pending"},
        {"content": "Step 6: Process Word document (if applicable)", "activeForm": "Step 6: Processing Word document", "status": "pending"}
    ]



if __name__ == "__main__":
    # CLI: print todos as formatted list
    import json
    todos = get_todos()
    print(json.dumps(todos, indent=2, ensure_ascii=False))
