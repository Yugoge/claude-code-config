#!/usr/bin/env python3
"""build-pipelines-from-triage.py — emit pipeline definitions JSON to stdout.
Consumes PM triage schema (issues[] keyed by triage_index + pipeline_order[] +
pipeline_recommendation). Honors addressed_issues + failed_attempts >= 3 filters.
Usage: build-pipelines-from-triage.py <triage.json> <addressed.json> <ts> [session_id]
"""
import json, sys

if len(sys.argv) < 4:
    sys.exit("Usage: build-pipelines-from-triage.py <triage> <addressed> <ts> [sid]")
triage = json.load(open(sys.argv[1]))
addressed = set(json.load(open(sys.argv[2])) or [])
ts, sid = sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "overnight"
fa = triage.get("failed_attempts", {}) if isinstance(triage.get("failed_attempts"), dict) else {}
by_idx = {i["triage_index"]: i for i in triage.get("issues", []) if "triage_index" in i}
order = triage.get("pipeline_order") or sorted(by_idx)
pipes, j = [], 0
for ti in order:
    x = by_idx.get(ti)
    if not x or x.get("pipeline_recommendation") != "fix": continue
    key = f"{x.get('location','')}|{x.get('description','')}"
    if key in addressed or fa.get(str(ti), 0) >= 3: continue
    pipes.append({"index": j, "triage_index": ti, "description": x.get("description"), "location": x.get("location"),
                  "severity": x.get("severity"), "category": x.get("category"),
                  "agents_flagged": x.get("agents_flagged", []), "phase": "pending", "iteration": 0,
                  "status": "active", "timestamp_suffix": f"{ts}-{j}", "tier": x.get("tier", 2),
                  "pm_recommended": True, "spec_path": f"docs/dev/overnight/{sid}/spec-pipeline-{j}.md"})
    j += 1
json.dump(pipes, sys.stdout, indent=2)
