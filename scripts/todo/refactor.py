#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: Detect Code Smells", "activeForm": "Step 1: Detecting Code Smells", "status": "pending"},
    {"content": "Step 2: Select Refactoring Techniques", "activeForm": "Step 2: Selecting Refactoring Techniques", "status": "pending"},
    {"content": "Step 3: Implement Refactoring", "activeForm": "Step 3: Implementing Refactoring", "status": "pending"},
    {"content": "Step 4: Verify Tests Pass", "activeForm": "Step 4: Verifying Tests Pass", "status": "pending"},
    {"content": "Step 5: Generate Refactoring Report", "activeForm": "Step 5: Generating Refactoring Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
