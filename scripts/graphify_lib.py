"""
graphify_lib.py — shared library for Graphify knowledge-graph integration.

Drives the REAL `graphifyy` v0.8.25 CLI (command `graphify`). Provides: status
state machine, EXCLUDE_FRAGMENTS sensitive-path scrubbing (applied ON READ),
file locking, out-of-repo cache resolution, cache-root-inside-repo refusal,
node-link graph.json parsing, and the subprocess runner that EVERY graphify
call must route through (so cwd=cacheDir + GRAPHIFY_OUT=cacheDir + numeric
timeout are enforced unconditionally — see M1a/AC4/AC13).

Real CLI surface (empirically verified against graphify 0.8.25):
  graphify update <repo>                          AST-only re-extract; writes
                                                  graph.json/report/html/cache to
                                                  $GRAPHIFY_OUT (absolute), manifest
                                                  to <cwd>/graphify-out/manifest.json.
  graphify extract <repo> --out DIR --backend B   AST + semantic (docs/papers/images
                                                  via LLM backend); writes to
                                                  DIR/graphify-out/graph.json.
  graphify query "<q>" --graph G --budget N       BFS traversal, human-readable TEXT.
  graphify affected "<node.id>" --graph G --depth N  reverse traversal, TEXT.

Graph schema (verified): NetworkX node-link. Top keys
  {directed, multigraph, graph, nodes, links, hyperedges}.
  Edges are under `links` (NOT `edges`) with keys source/target/relation/
  confidence/source_file. Nodes carry id/label/source_file/community/file_type.

Status state machine (all 5 states):
  ok          — binary present, cache hit (cacheDir/graph.json exists), data extracted
  degraded    — binary ran but output parse error / partial data
  failed      — binary present but runtime error: non-zero exit, timeout, exception
  unavailable — binary absent OR cache-root missing/empty OR no cacheDir/graph.json
                OR cache_root_inside_repo refusal
  skipped     — CLAUDE_GRAPHIFY_ENABLED=0 OR --no-graphify OR nil blast-radius-map

Advisory vs blocking:
  Graphify tool failure (degraded/failed/unavailable/skipped) is ADVISORY — DEV/BA
  always receive a valid (possibly empty) artifact; tool failure NEVER blocks /dev.
  Requirement ambiguity (ambiguity_hypotheses in pre_query.json) is the only
  CLARIFICATION-BLOCKING signal (BA returns needs_clarification).
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Exclusion fragments — two authority sources (kept separate for auditability)
# ---------------------------------------------------------------------------

# Sensitive-data patterns — authority: spec §5 Risk item 7 + arch-8.
# These prevent credentials and secrets from entering the graph cache.
_SENSITIVE_DATA_FRAGMENTS = (
    ".env",
    "credentials",
    "keys",
    "/logs/",
    ".pem",
    ".key",
    ".secret",
)

# Filesystem-noise patterns — authority: scripts/blast-radius-tool.py:35-38.
# These prevent VCS metadata, build artifacts, and installed packages from
# inflating the graph with non-source content.
_FILESYSTEM_NOISE_FRAGMENTS = (
    "/venv/",
    "/worktrees/",
    "/.archive/",
    "/plugins/",
    "/.git/",
    "/__pycache__/",
    "/node_modules/",
)

# Combined tuple exposed as the public API.  graphify-query.py and
# graphify-enrich.py filter candidate paths through this tuple.
EXCLUDE_FRAGMENTS = _SENSITIVE_DATA_FRAGMENTS + _FILESYSTEM_NOISE_FRAGMENTS

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_FAILED = "failed"
STATUS_UNAVAILABLE = "unavailable"
STATUS_SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Feature flag helpers
# ---------------------------------------------------------------------------

def is_graphify_enabled() -> bool:
    """Return False when CLAUDE_GRAPHIFY_ENABLED=0 (explicit disable)."""
    val = os.environ.get("CLAUDE_GRAPHIFY_ENABLED", "auto").strip().lower()
    return val != "0"


def get_graphify_bin() -> str | None:
    """Return graphify CLI path from GRAPHIFY_BIN env or PATH search, or None when absent."""
    override = os.environ.get("GRAPHIFY_BIN", "").strip()
    if override:
        return override if Path(override).exists() else None
    # Fall back to PATH search
    import shutil
    return shutil.which("graphify")


def get_cache_root() -> Path:
    """Return the global Graphify cache root directory."""
    override = os.environ.get("CLAUDE_GRAPHIFY_CACHE_ROOT", "").strip()
    return Path(override) if override else Path("/var/tmp/claude-graphify")


def get_repo_key(project_dir: Path | None = None) -> str:
    """Derive a stable repo key from the project directory path."""
    root = project_dir or Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    # Use last two path components to keep keys short but unique enough
    parts = [p for p in root.parts if p not in ("/", "")]
    return "_".join(parts[-2:]) if len(parts) >= 2 else parts[-1] if parts else "unknown"


# ---------------------------------------------------------------------------
# File locking (mirrors scripts/spec-check.py:171)
# ---------------------------------------------------------------------------

def write_json_locked(path: Path, data: Any, indent: int = 2) -> None:
    """Write JSON to path under fcntl.LOCK_EX to prevent concurrent corruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def read_json_safe(path: Path) -> tuple[Any, str]:
    """Read JSON from path. Returns (data, status) where status is STATUS_OK or STATUS_DEGRADED."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text), STATUS_OK
    except (FileNotFoundError, PermissionError):
        return None, STATUS_UNAVAILABLE
    except json.JSONDecodeError as exc:
        return None, STATUS_DEGRADED


# ---------------------------------------------------------------------------
# Cache availability check
# ---------------------------------------------------------------------------

def check_cache_available(repo_key: str | None = None) -> tuple[bool, str]:
    """
    Return (available, reason).
    Triggers unavailable: GRAPHIFY_BIN absent, CLAUDE_GRAPHIFY_CACHE_ROOT absent,
    or no manifest.json in the repo's cache directory.
    """
    if not is_graphify_enabled():
        return False, "CLAUDE_GRAPHIFY_ENABLED=0"
    bin_path = get_graphify_bin()
    if not bin_path:
        return False, "GRAPHIFY_BIN absent (binary not found in PATH or GRAPHIFY_BIN override)"
    cache_root = get_cache_root()
    key = repo_key or get_repo_key()
    manifest = cache_root / key / "manifest.json"
    if not manifest.exists():
        return False, f"no manifest.json at {manifest}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Subprocess runner with timeout
# ---------------------------------------------------------------------------

def run_graphify_cmd(
    args: list[str],
    timeout_seconds: int = 300,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """
    Run the graphify CLI with given args.
    timeout_seconds: 300 (5 min) for incremental updates, 900 (15 min) for first build.
    Returns (exit_code, stdout, stderr).
    Triggers status=failed on non-zero exit, timeout, or subprocess exception.
    """
    bin_path = get_graphify_bin()
    if not bin_path:
        return -1, "", "GRAPHIFY_BIN absent"
    cmd = [bin_path] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout_seconds}s — status=failed"
    except Exception as exc:
        return -1, "", f"subprocess error: {exc}"


# ---------------------------------------------------------------------------
# Path exclusion helper
# ---------------------------------------------------------------------------

def should_exclude_path(path: str) -> bool:
    """Return True if path matches any EXCLUDE_FRAGMENTS entry."""
    for fragment in EXCLUDE_FRAGMENTS:
        if fragment in path:
            return True
    return False


# ---------------------------------------------------------------------------
# Build empty graph_context (advisory pass-through for unavailable/failed/skipped)
# ---------------------------------------------------------------------------

def empty_graph_context(status: str, reason: str = "") -> dict:
    """Return a minimal valid graph_context object for non-ok statuses.
    DEV always receives this object; tool failure is advisory (never blocks DEV).
    """
    return {
        "status": status,
        "structural_context": {},
        "ambiguity_hypotheses": [],
        "error_detail": reason,
    }
