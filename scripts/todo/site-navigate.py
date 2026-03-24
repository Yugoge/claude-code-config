#!/usr/bin/env python3
import json
steps = [
    {"content": "Phase 1: Homepage Analysis", "activeForm": "Phase 1: Analyzing Homepage Structure", "status": "pending"},
    {"content": "Phase 2: Path Selection", "activeForm": "Phase 2: Selecting Navigation Paths", "status": "pending"},
    {"content": "Phase 3: Parallel Exploration", "activeForm": "Phase 3: Exploring Pages in Parallel", "status": "pending"},
    {"content": "Phase 4: Depth Navigation (if needed)", "activeForm": "Phase 4: Navigating Deeper Pages", "status": "pending"},
    {"content": "Phase 5: Alternative Strategies (if stuck)", "activeForm": "Phase 5: Trying Alternative Strategies", "status": "pending"},
    {"content": "Phase 6: Navigation Report", "activeForm": "Phase 6: Generating Navigation Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
