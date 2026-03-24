#!/usr/bin/env python3
import json
steps = [
    {"content": "Phase 1: Initial Broad Search", "activeForm": "Phase 1: Running Initial Broad Search", "status": "pending"},
    {"content": "Phase 2: Extract Key Sub-Topics", "activeForm": "Phase 2: Extracting Key Sub-Topics", "status": "pending"},
    {"content": "Phase 3: Parallel Deep Dive (5-10 searches)", "activeForm": "Phase 3: Running Parallel Deep Dives", "status": "pending"},
    {"content": "Phase 4: Source Content Extraction", "activeForm": "Phase 4: Extracting Source Content", "status": "pending"},
    {"content": "Phase 5: Contradiction and Gap Analysis", "activeForm": "Phase 5: Analyzing Contradictions and Gaps", "status": "pending"},
    {"content": "Phase 6: Synthesis and Report", "activeForm": "Phase 6: Synthesizing Final Report", "status": "pending"},
]
print(json.dumps(steps, ensure_ascii=False))
