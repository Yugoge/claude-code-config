#!/usr/bin/env python3
"""aggregate-permissions.py — collect validated_permissions from qa-report-*.json.
Usage: aggregate-permissions.py <qa-glob-or-dir> [pipelines.json]
Outputs deduplicated permissions JSON list to stdout.
"""
import glob, json, os, sys


def extract(path):
    return json.load(open(path)).get("qa", {}).get("permissions_verification", {}).get("validated_permissions", [])


if len(sys.argv) < 2:
    sys.exit("Usage: aggregate-permissions.py <qa-glob-or-dir> [pipelines.json]")
src = sys.argv[1]
paths = sorted(glob.glob(os.path.join(src, "qa-report-*.json"))) if os.path.isdir(src) else sorted(glob.glob(src))
fixed = None
if len(sys.argv) > 2:
    fixed = {p["timestamp_suffix"] for p in json.load(open(sys.argv[2])) if p.get("status") == "fixed"}
paths = [p for p in paths if fixed is None or any(s in p for s in fixed)]
seen, out = set(), []
for perm in (perm for p in paths for perm in extract(p)):
    key = perm.get("pattern")
    if key and key not in seen:
        seen.add(key); out.append(perm)
json.dump(out, sys.stdout, indent=2)
