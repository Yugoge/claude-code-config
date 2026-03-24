#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: Profile Algorithm Complexity", "activeForm": "Step 1: Profiling Algorithm Complexity", "status": "pending"},
    {"content": "Step 2: Analyze Resource Usage", "activeForm": "Step 2: Analyzing Resource Usage", "status": "pending"},
    {"content": "Step 3: Review Database and I/O", "activeForm": "Step 3: Reviewing Database and I/O", "status": "pending"},
    {"content": "Step 4: Identify Caching Opportunities", "activeForm": "Step 4: Identifying Caching Opportunities", "status": "pending"},
    {"content": "Step 5: Assess Concurrency Options", "activeForm": "Step 5: Assessing Concurrency Options", "status": "pending"},
    {"content": "Step 6: Generate Optimization Report", "activeForm": "Step 6: Generating Optimization Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
