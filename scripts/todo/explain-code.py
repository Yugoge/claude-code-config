#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: Overview and Purpose", "activeForm": "Step 1: Analyzing Overview and Purpose", "status": "pending"},
    {"content": "Step 2: High-Level Architecture", "activeForm": "Step 2: Mapping High-Level Architecture", "status": "pending"},
    {"content": "Step 3: Detailed Walkthrough", "activeForm": "Step 3: Walking Through Code in Detail", "status": "pending"},
    {"content": "Step 4: Key Concepts and Patterns", "activeForm": "Step 4: Identifying Key Concepts", "status": "pending"},
    {"content": "Step 5: Control Flow and External Interactions", "activeForm": "Step 5: Tracing Control Flow", "status": "pending"},
    {"content": "Step 6: Issues and Suggestions", "activeForm": "Step 6: Documenting Issues and Suggestions", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
