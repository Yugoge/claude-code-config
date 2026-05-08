#!/usr/bin/env python3
"""Audit realpath behavior in the guard for the codex finding."""
import os
import fnmatch

GLOBS = [
    "*/.claude/specs/*/cp-state-*.json",
    "*/docs/dev/specs/*/cp-state-*.json",
]

INPUT = "/dev/shm/dev-workspace/dot-claude/specs/spec-X/cp-state-ba.json"
abspath = os.path.abspath(INPUT)
realpath = os.path.realpath(INPUT)
print(f"input    = {INPUT}")
print(f"abspath  = {abspath}")
print(f"realpath = {realpath}")
print()
for c in [abspath, realpath]:
    for g in GLOBS:
        m = fnmatch.fnmatchcase(c, g)
        print(f"  candidate={c}\n    glob={g} match={m}")

# Now consider the symlink case
INPUT2 = "/root/.claude/specs/spec-X/cp-state-ba.json"
abspath2 = os.path.abspath(INPUT2)
realpath2 = os.path.realpath(INPUT2)
print(f"\ninput    = {INPUT2}")
print(f"abspath  = {abspath2}")
print(f"realpath = {realpath2}")
for c in [abspath2, realpath2]:
    for g in GLOBS:
        m = fnmatch.fnmatchcase(c, g)
        print(f"  candidate={c}\n    glob={g} match={m}")
