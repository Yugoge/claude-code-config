#!/usr/bin/env python3
import json
steps = [
    {"content": "Phase 1: Parallel Discovery Search", "activeForm": "Phase 1: Running Parallel Discovery Search", "status": "pending"},
    {"content": "Phase 2: Entry Point Analysis", "activeForm": "Phase 2: Analyzing Entry Points", "status": "pending"},
    {"content": "Phase 3: Breadth Exploration", "activeForm": "Phase 3: Exploring Breadth of Sources", "status": "pending"},
    {"content": "Phase 4: Depth Targeting", "activeForm": "Phase 4: Targeting Depth Content", "status": "pending"},
    {"content": "Phase 5: Fallback Recovery (if needed)", "activeForm": "Phase 5: Running Fallback Recovery", "status": "pending"},
    {"content": "Phase 6: Synthesis and Report", "activeForm": "Phase 6: Synthesizing Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
