#!/usr/bin/env python3
"""
Stop Hook: Block spec agent from exiting with < 100% monolith coverage.

Logic:
  1. If stop_hook_active -> exit 0
  2. Read workflow bookmark to check if current workflow is /spec
  3. If NOT /spec -> exit 0 (allow)
  4. If /spec -> find latest spec views dir and monolith
  5. Run spec-verify.py --monolith <path> --views-dir <path>
  6. If exit 0 (100% coverage) -> exit 0 (allow stop)
  7. If exit != 0 -> exit 2 (block stop)

Exit codes:
  0: Allow stop
  2: Block stop
"""

import json
import os
import subprocess
import sys
from pathlib import Path


SPEC_VERIFY = "/root/bin/spec-verify.py"


def read_stdin():
    """Parse stop hook JSON from stdin."""
    try:
        if not sys.stdin.isatty():
            return json.load(sys.stdin)
    except Exception:
        pass
    return {}


def get_workflow_command(project_dir: Path, session_id: str) -> str:
    """Return the workflow command name from bookmark, or empty string."""
    bookmark = project_dir / ".claude" / f"workflow-{session_id}.json"
    if not bookmark.exists():
        return ""
    try:
        state = json.loads(bookmark.read_text())
        return state.get("command", "")
    except Exception:
        return ""


def find_latest_spec(specs_base: Path):
    """Find the most recent spec dir that has a views/ subdirectory."""
    if not specs_base.is_dir():
        return None
    spec_dirs = sorted(
        [d for d in specs_base.iterdir() if d.is_dir() and (d / "views").is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    return spec_dirs[0] if spec_dirs else None


def find_monolith(specs_base: Path, spec_dir: Path) -> Path | None:
    """Locate the monolith .md file for a given spec directory."""
    spec_id = spec_dir.name
    candidates = [
        specs_base / f"{spec_id}.md",
        specs_base / f"{spec_id}.monolith.md",
        spec_dir / f"{spec_id}.md",
        spec_dir / f"{spec_id}.monolith.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    matches = list(specs_base.glob(f"{spec_id}*.md"))
    return matches[0] if matches else None


def run_coverage_check(monolith: Path, views_dir: Path) -> subprocess.CompletedProcess:
    """Run spec-verify.py and return the result."""
    return subprocess.run(
        ["python3", SPEC_VERIFY, "--monolith", str(monolith), "--views-dir", str(views_dir)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def block_with_message(result: subprocess.CompletedProcess):
    """Write blocking message to stderr and exit 2."""
    sys.stderr.write(
        "\n⛔ SPEC COVERAGE ENFORCEMENT: spec-verify.py reports < 100% coverage.\n"
        "The spec agent MUST achieve 100% coverage before exiting.\n"
        "Run spec-verify.py --show-uncovered to see missing lines.\n"
        "Apply the deterministic coverage fallback from agents/spec.md Step 7.\n"
    )
    if result.stdout:
        sys.stderr.write(f"\nspec-verify.py output:\n{result.stdout}\n")
    if result.stderr:
        sys.stderr.write(f"\nspec-verify.py stderr:\n{result.stderr}\n")
    sys.exit(2)


def main():
    data = read_stdin()
    if data.get("stop_hook_active", False):
        sys.exit(0)

    session_id = data.get("session_id", "default")
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

    if get_workflow_command(project_dir, session_id) != "spec":
        sys.exit(0)

    specs_base = project_dir / "docs" / "dev" / "specs"
    spec_dir = find_latest_spec(specs_base)
    if spec_dir is None:
        sys.exit(0)

    monolith = find_monolith(specs_base, spec_dir)
    if monolith is None or not Path(SPEC_VERIFY).is_file():
        sys.exit(0)

    result = run_coverage_check(monolith, spec_dir / "views")
    if result.returncode == 0:
        sys.exit(0)

    block_with_message(result)


if __name__ == "__main__":
    main()
