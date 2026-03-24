#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: Input Validation and Injection Analysis", "activeForm": "Step 1: Analyzing Input Validation and Injection", "status": "pending"},
    {"content": "Step 2: Authentication and Authorization Review", "activeForm": "Step 2: Reviewing Authentication and Authorization", "status": "pending"},
    {"content": "Step 3: Data Exposure and Sensitive Info Check", "activeForm": "Step 3: Checking Data Exposure", "status": "pending"},
    {"content": "Step 4: Dependency Vulnerability Scan", "activeForm": "Step 4: Scanning Dependency Vulnerabilities", "status": "pending"},
    {"content": "Step 5: Configuration and Infrastructure Review", "activeForm": "Step 5: Reviewing Configuration Security", "status": "pending"},
    {"content": "Step 6: Generate Security Report", "activeForm": "Step 6: Generating Security Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
