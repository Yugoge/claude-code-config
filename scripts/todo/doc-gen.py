#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: Analyze Codebase Structure", "activeForm": "Step 1: Analyzing Codebase Structure", "status": "pending"},
    {"content": "Step 2: Generate API Documentation", "activeForm": "Step 2: Generating API Documentation", "status": "pending"},
    {"content": "Step 3: Generate Module/Class Documentation", "activeForm": "Step 3: Generating Module/Class Documentation", "status": "pending"},
    {"content": "Step 4: Generate README Documentation", "activeForm": "Step 4: Generating README Documentation", "status": "pending"},
    {"content": "Step 5: Generate Architecture Documentation", "activeForm": "Step 5: Generating Architecture Documentation", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
