#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: Analyze Code Quality", "activeForm": "Step 1: Analyzing Code Quality", "status": "pending"},
    {"content": "Step 2: Security Review", "activeForm": "Step 2: Reviewing Security", "status": "pending"},
    {"content": "Step 3: Performance Analysis", "activeForm": "Step 3: Analyzing Performance", "status": "pending"},
    {"content": "Step 4: Testing Coverage Check", "activeForm": "Step 4: Checking Testing Coverage", "status": "pending"},
    {"content": "Step 5: Documentation Review", "activeForm": "Step 5: Reviewing Documentation", "status": "pending"},
    {"content": "Step 6: Generate Review Report", "activeForm": "Step 6: Generating Review Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
