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
    # Tests may override via CLAUDE_BULK_AUTH_FLAG_PATH_OVERRIDE, but the
    # override MUST point at a regular file inside /tmp/ whose basename
    # matches the test-flag pattern (a non-protected sibling glob — the
    # production path is hook-protected from ALL model tool writes
    # regardless of agent_id).
    auth_flag_path = os.environ.get("CLAUDE_BULK_AUTH_FLAG_PATH_OVERRIDE", "").strip()
    if auth_flag_path:
        # Reject obviously-unsafe overrides (codex Cycle-5 finding #1 fix):
        # the override must (a) not be a directory; (b) live under /tmp;
        # (c) match the test-flag basename pattern. Otherwise an attacker
        # could point at /tmp itself (unlink fails, write proceeds).
        bn = os.path.basename(auth_flag_path)
        if (
            not auth_flag_path.startswith("/tmp/")
            or os.path.isdir(auth_flag_path)
            or not bn.endswith(".flag")
            or "claude-bulk-allowed-" in bn
            or not bn.startswith(("claude-bulk-test-flag-", "phase-a-auth-",
                                  "test-auth", "no-such-flag"))
        ):
            print(
                "Invalid CLAUDE_BULK_AUTH_FLAG_PATH_OVERRIDE — must be a regular "
                "file under /tmp/ with basename matching the test-flag pattern.",
                file=sys.stderr,
            )
            sys.exit(2)
    else:
        auth_flag_path = f"/tmp/claude-bulk-allowed-{sid}.flag"

    if not os.path.exists(auth_flag_path) or os.path.isdir(auth_flag_path):
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
    # Codex Cycle-5 finding #1 fix: fail-closed if unlink fails for any
    # reason other than the file already being gone (race condition). A
    # silent unlink failure on a directory-path could let the sentinel write
    # without consuming the grant.
    try:
        os.unlink(auth_flag_path)
    except FileNotFoundError:
        pass  # already gone (race condition); proceed to write attempt
    except OSError as exc:
        print(
            f"Failed to consume auth flag at {auth_flag_path}: {exc}. "
            "Refusing to write sentinel.",
            file=sys.stderr,
        )
        sys.exit(2)

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
