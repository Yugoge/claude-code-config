#!/usr/bin/env python3
import json
steps = [
    {"content": "Step 1: WebSearch Discovery", "activeForm": "Step 1: Running WebSearch Discovery", "status": "pending"},
    {"content": "Step 2: Playwright Page Navigation", "activeForm": "Step 2: Navigating Pages with Playwright", "status": "pending"},
    {"content": "Step 3: Content Extraction", "activeForm": "Step 3: Extracting Page Content", "status": "pending"},
    {"content": "Step 4: Data Processing and Output", "activeForm": "Step 4: Processing and Outputting Data", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
