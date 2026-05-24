#!/usr/bin/env python3
# pretool-gitignore-preflight.py — PreToolUse hook (matcher: Agent)
#
# Purpose: Block Agent dispatches when any declared deliverable in the dev-report
# is matched by .gitignore, preventing a cycle from passing QA but silently
# failing to ship via git (spec-20260520-221059.md Layer A R1, arch-6).
#
# No-op conditions (exits 0):
#   1. The Agent prompt does not contain a docs/dev/dev-report-*.json path reference.
#   2. The referenced dev-report path does not exist on disk (pre-dev dispatch).
#   3. dev.files_modified and dev.files_created are both absent, null, or empty.
#   4. A top-level gitignore_waiver field is present, non-null, and non-empty.
#
# Blocking condition (exits 2):
#   Any path in dev.files_modified or dev.files_created is matched by .gitignore
#   (git check-ignore --no-index --quiet exits 0 for that path) AND no valid
#   gitignore_waiver is present at the top level of the dev-report JSON.
#
# gitignore_waiver bypass:
#   Add "gitignore_waiver": "<reason>" at the top level of the dev-report JSON.
#   The value must be non-null and non-empty string. Null or empty string is NOT
#   accepted as a waiver.
#
# Input JSON shape (stdin):
#   {"tool_name": "Agent", "tool_input": {"prompt": "... Dev report file: docs/dev/dev-report-<task-id>.json ..."}}
#   Prompt is extracted via data.get("tool_input") or data.get("toolInput") then .get("prompt", "").
#   data.get("prompt") at top level is NEVER used — that key is absent in production payloads.

import json
import os
import re
import subprocess
import sys

DEV_REPORT_PATTERN = re.compile(r'docs/dev/dev-report-[A-Za-z0-9._-]+\.json')


def get_repo_root():
    """Derive repo root from this file's location (hooks/ is one level below root)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_gitignored(path, repo_root):
    """Return True if git considers the path gitignored (exit 0 = ignored)."""
    result = subprocess.run(
        ['git', 'check-ignore', '--no-index', '--quiet', '--', path],
        cwd=repo_root,
        capture_output=True,
    )
    # exit 0 = ignored, exit 1 = not ignored, exit 128 = error (treat as not ignored)
    return result.returncode == 0


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = data.get('tool_input') or data.get('toolInput') or {}
    prompt = tool_input.get('prompt', '')

    # Use findall to capture ALL dev-report paths in prompt (not just the first).
    # If the prompt contains prior context mentioning an older clean report
    # before the current dirty one, .search() would miss the dirty report.
    matches = list(DEV_REPORT_PATTERN.finditer(prompt))
    if not matches:
        sys.exit(0)

    repo_root = get_repo_root()
    blocked = []

    for match in matches:
        report_rel = match.group(0)
        report_path = os.path.join(repo_root, report_rel)

        if not os.path.isfile(report_path):
            continue

        try:
            with open(report_path) as f:
                report = json.load(f)
        except Exception:
            continue

        waiver = report.get('gitignore_waiver')
        if waiver is not None and isinstance(waiver, str) and waiver.strip():
            continue

        dev = report.get('dev') or {}
        files_modified = dev.get('files_modified') or []
        files_created = dev.get('files_created') or []
        # Guard: only process list entries that are non-empty strings.
        # A string-typed files_modified would iterate chars without this check.
        if not isinstance(files_modified, list):
            files_modified = []
        if not isinstance(files_created, list):
            files_created = []
        all_paths = files_modified + files_created

        for path in all_paths:
            if isinstance(path, str) and path and is_gitignored(path, repo_root):
                blocked.append(path)

    if blocked:
        msg = 'BLOCKED: gitignored deliverables detected: ' + ', '.join(blocked)
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
