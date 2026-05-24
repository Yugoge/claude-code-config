#!/usr/bin/env python3
"""Single-invocation /push Steps 4+5 wrapper for the orchestrator.

Encapsulates the entire Chain-B grant validation → consume → sentinel write →
os.execv(push.sh) sequence in one Bash call, eliminating the need to delegate
Steps 4+5 to a subagent.

WHY THIS MUST BE A SINGLE ORCHESTRATOR-LAYER BASH INVOCATION:
  1. The orchestrator's 3-consecutive-Bash budget is exhausted by Steps 0-2;
     delegating Steps 4+5 to a subagent causes three compounding failures:
     (a) HOW-prescriptive prompts cause the subagent to delete the wrong file
         (Chain-A push-gate token instead of the Chain-B push-analyst grant);
     (b) subagents legitimately reject writing the Chain-B sentinel as a
         privilege escalation;
     (c) the Chain-B sentinel's 60-second mtime gate in push.sh cannot survive
         two sequential agent dispatch delays (30-90s each).
  2. os.execv keeps this and push.sh in the SAME PID — the sentinel written
     here is unconditionally fresh when push.sh reads it (< 1s mtime age).

Parameters:
  --request-id  REQUEST_ID from the orchestrator's Step 2 snapshot (required)
  --repo-hash   16-char hex sha256(realpath(git_root))[:16] (required)
  --remote      push remote name, e.g. "origin" (required)
  --auto        forward --auto flag to push.sh for non-interactive lock handling

Exit codes:
  0   os.execv succeeded; process becomes push.sh (returns push.sh's exit code)
  1   Chain-B validation failure: grant missing/expired/mismatched/blocked verdict
  2   Setup/argument error: bad args, missing CLAUDE_SESSION_ID, bad repo-hash,
      push.sh not found/executable, os.execv failed after sentinel write
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="execute-push.py",
        description=(
            "Validate Chain-B push-analyst grant, write sentinel, and exec push.sh "
            "in a single process — avoids delegating Steps 4+5 to a subagent."
        ),
    )
    parser.add_argument(
        "--request-id",
        required=True,
        help="REQUEST_ID from orchestrator Step 2 snapshot.",
    )
    parser.add_argument(
        "--repo-hash",
        required=True,
        help="16-char hex sha256(realpath(git_root))[:16] from orchestrator Step 2.",
    )
    parser.add_argument(
        "--remote",
        required=True,
        help="Push remote name (e.g. 'origin').",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        default=False,
        help="Forward --auto flag to push.sh for non-interactive lock handling.",
    )
    return parser.parse_args(argv)


def _get_git_head() -> str:
    """Return the current HEAD sha (40 hex chars). Exits 2 on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f"execute-push: cannot read git HEAD: {exc}", file=sys.stderr)
        sys.exit(2)


def _get_git_branch() -> str:
    """Return the current branch name. Exits 2 on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f"execute-push: cannot read git branch: {exc}", file=sys.stderr)
        sys.exit(2)


def _get_git_root() -> str:
    """Return the repo root path. Exits 2 on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f"execute-push: cannot read git root: {exc}", file=sys.stderr)
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # Step 1: Validate CLAUDE_SESSION_ID FIRST (before repo-hash check per AC3
    # ordering requirement: env var check must precede repo-hash validation).
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if not session_id:
        print(
            "execute-push: CLAUDE_SESSION_ID is not set. "
            "Invoke /push from within a Claude Code session.",
            file=sys.stderr,
        )
        return 2

    # Step 2: Validate repo-hash format and match against computed hash.
    if not re.fullmatch(r"[0-9a-f]{16}", args.repo_hash):
        print(
            f"execute-push: --repo-hash must be 16 lowercase hex chars, got: {args.repo_hash!r}",
            file=sys.stderr,
        )
        return 2

    git_root = _get_git_root()
    computed_hash = hashlib.sha256(os.path.realpath(git_root).encode()).hexdigest()[:16]
    if computed_hash != args.repo_hash:
        print(
            f"execute-push: repo-hash mismatch — computed {computed_hash!r}, "
            f"got {args.repo_hash!r}. Ensure --repo-hash was captured in Step 2 "
            f"from the same repository.",
            file=sys.stderr,
        )
        return 2

    # Step 3: Read and validate the push-analyst grant.
    grant_path = (
        f"/tmp/agentic-commit/push-analyst/{args.repo_hash}"
        f"/{session_id}/{args.request_id}.json"
    )
    if not os.path.isfile(grant_path):
        print(
            f"execute-push: push-analyst did not write a grant at {grant_path} — "
            "aborting push. Ensure push-analyst subagent completed successfully.",
            file=sys.stderr,
        )
        return 1

    try:
        with open(grant_path) as fp:
            grant = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"execute-push: push-analyst grant is not valid JSON — aborting push: {exc}",
            file=sys.stderr,
        )
        return 1

    if not isinstance(grant, dict):
        print(
            "execute-push: push-analyst grant is not a JSON object — aborting push.",
            file=sys.stderr,
        )
        return 1

    # Read HEAD and branch for grant field validation.
    head_sha = _get_git_head()
    branch_raw = _get_git_branch()

    # Validate required grant fields (nonce=request_id per push-analyst schema).
    def _field_err(msg: str) -> int:
        print(f"execute-push: grant validation failed — {msg}", file=sys.stderr)
        return 1

    nonce = grant.get("nonce")
    if nonce != args.request_id:
        return _field_err(f"nonce {nonce!r} does not match request_id {args.request_id!r}")

    grant_branch = grant.get("branch")
    if grant_branch != branch_raw:
        return _field_err(f"branch {grant_branch!r} does not match current branch {branch_raw!r}")

    grant_head = grant.get("head_sha")
    if grant_head != head_sha:
        return _field_err(f"head_sha {grant_head!r} does not match current HEAD {head_sha!r}")

    grant_remote = grant.get("remote_name")
    if grant_remote != args.remote:
        return _field_err(f"remote_name {grant_remote!r} does not match --remote {args.remote!r}")

    grant_session = grant.get("session_id")
    if grant_session != session_id:
        return _field_err(
            f"session_id {grant_session!r} does not match CLAUDE_SESSION_ID {session_id!r}"
        )

    verdict = grant.get("verdict")
    if verdict not in ("approved", "warn", "blocked"):
        return _field_err(f"verdict {verdict!r} is not one of approved/warn/blocked")

    risks = grant.get("risks")
    if not isinstance(risks, list):
        return _field_err(f"risks field is not a JSON array: {risks!r}")

    expires_at_raw = grant.get("expires_at", "")
    try:
        # Normalize Z-suffix (push-analyst writes YYYY-MM-DDTHH:MM:SSZ which
        # Python's fromisoformat does not accept until 3.11; replace Z → +00:00).
        expires_at_str = expires_at_raw.replace("Z", "+00:00")
        expires_at = datetime.fromisoformat(expires_at_str)
    except (ValueError, AttributeError) as exc:
        return _field_err(f"expires_at {expires_at_raw!r} is not valid ISO-8601: {exc}")

    if datetime.now(timezone.utc) >= expires_at:
        return _field_err(f"grant is expired (expires_at={expires_at_raw!r})")

    # Step 4: Apply verdict logic.
    # blocked → print risks, exit 1 WITHOUT writing sentinel or exec'ing push.sh.
    if verdict == "blocked":
        print(
            "execute-push: push-analyst verdict is BLOCKED — aborting push.",
            file=sys.stderr,
        )
        for risk in risks:
            print(f"  blocked risk: {risk}", file=sys.stderr)
        return 1

    # warn → print risks as warnings, then proceed.
    if verdict == "warn":
        print("execute-push: push-analyst verdict is WARN — proceeding with warnings:", file=sys.stderr)
        for risk in risks:
            print(f"  warning: {risk}", file=sys.stderr)

    # Step 5: Verify push.sh exists and is executable BEFORE consuming the grant.
    push_sh = os.path.expanduser("~/.claude/hooks/push.sh")
    if not os.path.isfile(push_sh) or not os.access(push_sh, os.X_OK):
        print(
            f"execute-push: push.sh not found or not executable at {push_sh}",
            file=sys.stderr,
        )
        return 2

    # Step 6: Re-read HEAD for drift check at sentinel-write time.
    current_head = _get_git_head()
    if current_head != head_sha:
        print(
            f"execute-push: HEAD drifted since grant was written "
            f"(grant head_sha={head_sha!r}, current HEAD={current_head!r}) — "
            "aborting push.",
            file=sys.stderr,
        )
        return 1

    # Step 7: Consume (unlink) the grant — only AFTER verdict check passes
    # (not on blocked) and BEFORE writing the sentinel.
    try:
        os.unlink(grant_path)
    except OSError as exc:
        print(f"execute-push: failed to unlink grant at {grant_path}: {exc}", file=sys.stderr)
        return 1

    # Step 8: Atomically write the Chain-B success sentinel.
    branch_encoded = branch_raw.replace("/", "__")
    sentinel_dir = f"/tmp/agentic-commit/push-analyst/{args.repo_hash}"
    sentinel_path = f"{sentinel_dir}/{branch_encoded}-chainB.validated.sentinel.json"

    sentinel_content = json.dumps({
        "result": "PASS",
        "request_id": args.request_id,
        "head": current_head,
        "branch": branch_raw,
        "remote": args.remote,
    })

    tmp_path = None
    try:
        os.makedirs(sentinel_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=sentinel_dir, prefix=".sentinel-", suffix=".tmp")
        try:
            os.write(fd, sentinel_content.encode())
        finally:
            os.close(fd)
        os.replace(tmp_path, sentinel_path)
        tmp_path = None  # os.replace succeeded; no cleanup needed
    except OSError as exc:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        print(f"execute-push: failed to write Chain-B sentinel: {exc}", file=sys.stderr)
        return 2

    # Step 9: Set CLAUDE_PUSH_REQUEST_ID BEFORE os.execv, then exec push.sh.
    os.environ["CLAUDE_PUSH_REQUEST_ID"] = args.request_id
    push_argv = [push_sh, args.remote]
    if args.auto:
        push_argv.append("--auto")

    try:
        os.execv(push_sh, push_argv)
    except OSError as exc:
        # execv failed after sentinel was written — unlink sentinel to avoid
        # a stale sentinel being picked up by a subsequent push attempt.
        try:
            os.unlink(sentinel_path)
        except OSError:
            pass
        print(f"execute-push: os.execv failed: {exc}", file=sys.stderr)
        return 2

    # Unreachable: os.execv replaces this process on success.
    return 0


if __name__ == "__main__":
    sys.exit(main())
