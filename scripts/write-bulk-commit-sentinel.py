#!/usr/bin/env python3
"""Write a multi-use /commit --bulk privilege-guard sentinel.

Invoked from commands/commit.md Step 5 (BULK=true) to authorize the
changelog-analyst subagent to make multiple auto-bulk commits within a
single /commit --bulk session.

Unlike the single-use commit grant written for non-bulk commits, this
sentinel is NOT consumed on each validation — it persists until expiry
so that changelog-analyst can commit one subsystem group at a time.

File: /tmp/claude-bulk-commit-sentinel-<sid>-<nonce>.json
Contents: {kind, sid, nonce, created_at, expires_at}

The privilege guard checks for this file inside _evaluate_commit when
the commit message matches BLESSED_BRIDGE_RE. Without a valid sentinel,
auto-bulk commits are BLOCKED even if the message prefix is correct.

Exit codes:
  0  success (sentinel written; path printed to stdout)
  2  CLAUDE_SESSION_ID unresolved
"""

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SENTINEL_TTL_MINUTES = 30


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="write-bulk-commit-sentinel.py",
        description="Write a multi-use /commit --bulk privilege-guard sentinel.",
    )
    parser.add_argument(
        "--sid",
        default=None,
        help="Claude session id. Defaults to the CLAUDE_SESSION_ID env var.",
    )
    parser.add_argument(
        "--output-dir",
        default="/tmp",
        help="Directory to write the sentinel JSON into. Default: /tmp.",
    )
    return parser.parse_args(argv)


def _resolve_sid(cli_sid):
    if cli_sid:
        return cli_sid
    env_sid = os.environ.get("CLAUDE_SESSION_ID", "")
    if not env_sid:
        print(
            "Cannot write bulk-commit sentinel: CLAUDE_SESSION_ID is not set and "
            "--sid was not supplied. Invoke /commit --bulk from within a Claude "
            "Code session or pass --sid explicitly.",
            file=sys.stderr,
        )
        sys.exit(2)
    return env_sid


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    sid = _resolve_sid(args.sid)

    # M4.1 (task 20260524-205206 / AC-04): user-authorization gate.
    # The production auth-flag path is /tmp/claude-bulk-allowed-<sid>.flag.
    # Tests may override via CLAUDE_BULK_AUTH_FLAG_PATH_OVERRIDE (the production
    # path is hook-protected from ALL model tool writes regardless of agent_id,
    # so the test harness uses an unprotected sibling path).
    auth_flag_path = os.environ.get("CLAUDE_BULK_AUTH_FLAG_PATH_OVERRIDE", "").strip()
    if not auth_flag_path:
        auth_flag_path = f"/tmp/claude-bulk-allowed-{sid}.flag"

    if not os.path.exists(auth_flag_path):
        print(
            "BULK mode requires explicit user authorization. "
            "The user (not an agent) must run: "
            "touch /tmp/claude-bulk-allowed-$CLAUDE_SESSION_ID.flag",
            file=sys.stderr,
        )
        sys.exit(2)

    # Consume the flag IMMEDIATELY at observation — BEFORE any sentinel-write
    # attempt. Single-use semantics: the grant is spent regardless of what
    # happens next. (Codex finding #8 fix: NO try/finally wrapper around the
    # write — unlink-FIRST is the contract, not unlink-AFTER.)
    try:
        os.unlink(auth_flag_path)
    except OSError:
        pass  # already gone (race condition); proceed to write attempt

    nonce = secrets.token_hex(8)
    now = datetime.now(timezone.utc)
    sentinel = {
        "kind": "bulk-commit",
        "sid": sid,
        "nonce": nonce,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=SENTINEL_TTL_MINUTES)).isoformat(),
    }
    path = Path(args.output_dir) / f"claude-bulk-commit-sentinel-{sid}-{nonce}.json"
    with open(path, "w") as fp:
        json.dump(sentinel, fp)
    print(str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
