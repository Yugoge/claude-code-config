#!/usr/bin/env python3
"""
graphify-maintain.py — Global Graphify cache lifecycle manager.

Usage:
  python3 scripts/graphify-maintain.py init    # One-time full build (2-15 min, user-triggered only)
  python3 scripts/graphify-maintain.py update  # Incremental refresh (non-blocking advisory, ~30s)
  python3 scripts/graphify-maintain.py status  # Show cache state and manifest

Feature flags:
  CLAUDE_GRAPHIFY_ENABLED=0  — skip all operations and exit 0
  GRAPHIFY_BIN               — override CLI path
  CLAUDE_GRAPHIFY_CACHE_ROOT — override /var/tmp/claude-graphify

Exit codes:
  0 — success or no-op (binary absent, disabled)
  1 — error (init/update failed with non-zero exit)
  2 — usage error
"""

import json
import os
import sys
import time
from pathlib import Path

# Locate project root from env (set by Claude harness)
_PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
sys.path.insert(0, str(_PROJECT_DIR / "scripts"))

from graphify_lib import (
    STATUS_OK, STATUS_FAILED, STATUS_UNAVAILABLE, STATUS_SKIPPED,
    check_cache_available, get_cache_root, get_graphify_bin, get_repo_key,
    is_graphify_enabled, run_graphify_cmd, write_json_locked,
)

INCREMENTAL_TIMEOUT = 300   # 5 min for incremental updates
INIT_TIMEOUT = 900           # 15 min for first full build


def cmd_init() -> int:
    """Full initial build — must be run manually by the user, never auto-triggered."""
    if not is_graphify_enabled():
        print("graphify-maintain: CLAUDE_GRAPHIFY_ENABLED=0 — skipping init", flush=True)
        return 0

    bin_path = get_graphify_bin()
    if not bin_path:
        print("graphify-maintain: GRAPHIFY_BIN absent — cannot init", flush=True)
        return 0  # advisory: no-op

    cache_root = get_cache_root()
    repo_key = get_repo_key(_PROJECT_DIR)
    repo_cache = cache_root / repo_key

    print(f"graphify-maintain init: building graph for repo_key={repo_key}", flush=True)
    print(f"  cache_dir: {repo_cache}", flush=True)
    print(f"  timeout: {INIT_TIMEOUT}s", flush=True)

    start = time.time()
    exit_code, stdout, stderr = run_graphify_cmd(
        ["--init", "--output-dir", str(repo_cache), "--project-dir", str(_PROJECT_DIR)],
        timeout_seconds=INIT_TIMEOUT,
        cwd=str(_PROJECT_DIR),
    )
    elapsed = time.time() - start

    if exit_code == 0:
        print(f"graphify-maintain init: ok in {elapsed:.1f}s", flush=True)
        # Write manifest
        manifest_data = {
            "branch": _get_git_branch(),
            "head_sha": _get_git_head(),
            "graphify_version": _get_graphify_version(bin_path),
            "built_at": _now_iso(),
            "repo_key": repo_key,
        }
        write_json_locked(repo_cache / "manifest.json", manifest_data)
        return 0
    else:
        print(f"graphify-maintain init: failed (exit={exit_code}) in {elapsed:.1f}s", file=sys.stderr, flush=True)
        if stderr:
            print(f"  stderr: {stderr[:500]}", file=sys.stderr, flush=True)
        return 1


def cmd_update() -> int:
    """Incremental refresh — non-blocking advisory; called from /pull and /dev Step 7.5."""
    if not is_graphify_enabled():
        print("graphify-maintain: CLAUDE_GRAPHIFY_ENABLED=0 — skipping update", flush=True)
        return 0

    available, reason = check_cache_available()
    if not available:
        print(f"graphify-maintain update: {STATUS_UNAVAILABLE} ({reason}) — skipping", flush=True)
        return 0  # advisory: no-op

    bin_path = get_graphify_bin()
    repo_key = get_repo_key(_PROJECT_DIR)
    cache_root = get_cache_root()
    repo_cache = cache_root / repo_key

    print(f"graphify-maintain update: incremental refresh for repo_key={repo_key}", flush=True)
    start = time.time()
    exit_code, stdout, stderr = run_graphify_cmd(
        ["--update", "--output-dir", str(repo_cache), "--project-dir", str(_PROJECT_DIR)],
        timeout_seconds=INCREMENTAL_TIMEOUT,
        cwd=str(_PROJECT_DIR),
    )
    elapsed = time.time() - start

    if exit_code == 0:
        print(f"graphify-maintain update: ok in {elapsed:.1f}s", flush=True)
        # Refresh manifest HEAD + branch
        manifest_path = repo_cache / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        else:
            manifest = {}
        manifest.update({
            "branch": _get_git_branch(),
            "head_sha": _get_git_head(),
            "updated_at": _now_iso(),
        })
        write_json_locked(manifest_path, manifest)
        return 0
    else:
        print(f"graphify-maintain update: failed (exit={exit_code}) in {elapsed:.1f}s — advisory, continuing", file=sys.stderr, flush=True)
        return 0  # advisory: always exit 0 so callers are not blocked


def cmd_status() -> int:
    """Show cache state and manifest."""
    available, reason = check_cache_available()
    repo_key = get_repo_key(_PROJECT_DIR)
    cache_root = get_cache_root()
    repo_cache = cache_root / repo_key

    print(f"graphify-maintain status:")
    print(f"  enabled: {is_graphify_enabled()}")
    print(f"  binary: {get_graphify_bin() or 'absent'}")
    print(f"  cache_root: {cache_root}")
    print(f"  repo_key: {repo_key}")
    print(f"  cache_available: {available}")
    if not available:
        print(f"  unavailable_reason: {reason}")

    manifest_path = repo_cache / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            print(f"  manifest: {json.dumps(manifest, indent=4)}")
        except Exception as exc:
            print(f"  manifest: parse error — {exc}")
    else:
        print(f"  manifest: absent ({manifest_path})")

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_git_branch() -> str:
    try:
        import subprocess as _sp
        r = _sp.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, cwd=str(_PROJECT_DIR))
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_git_head() -> str:
    try:
        import subprocess as _sp
        r = _sp.run(["git", "rev-parse", "HEAD"],
                    capture_output=True, text=True, cwd=str(_PROJECT_DIR))
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_graphify_version(bin_path: str) -> str:
    try:
        import subprocess as _sp
        r = _sp.run([bin_path, "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    subcmd = sys.argv[1]
    if subcmd == "init":
        sys.exit(cmd_init())
    elif subcmd == "update":
        sys.exit(cmd_update())
    elif subcmd == "status":
        sys.exit(cmd_status())
    else:
        print(f"Unknown subcommand: {subcmd!r}. Use init, update, or status.", file=sys.stderr)
        sys.exit(2)
