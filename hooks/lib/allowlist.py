"""PreToolUse allowlist grant reader for Claude Code hooks.

Single source of truth for read_grant() — the check-only (no delete)
variant of the /allow grant check used by PreToolUse hooks.

Contract: PreToolUse hooks ONLY read the grant; they never delete it.
Deletion is deferred to posttool-allowlist-consume.py (PostToolUse).
This preserves the grant for retry if any PreToolUse hook later exits 2.

Extracted from pretool-orchestrator-gate.py lines 155-183.

Stdlib-only; Python 3.12+ required.
"""

import fcntl
import json
import re
import sys
from pathlib import Path


def read_grant(tool_name: str, sid: str) -> bool:
    """Check /allow grant for tool_name. Read-only — does NOT delete the grant.

    Deletion is deferred to posttool-allowlist-consume.py (PostToolUse).
    Returns True if grant matches, False otherwise (missing file = False).
    """
    flag_path = Path(f"/tmp/claude-bash-allowlist-{sid}.json")
    try:
        with open(flag_path, "r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                grant = json.load(fh)
            except Exception:
                return False
            pattern = grant.get("pattern", "")
            if not isinstance(pattern, str) or not pattern:
                return False
            is_regex = grant.get("is_regex", False)
            if is_regex:
                matched = bool(re.search(pattern, tool_name))
            else:
                matched = pattern == tool_name or pattern in tool_name
            if matched:
                sys.stderr.write(f"[ALLOW] grant matched for {tool_name}, consume deferred to PostToolUse\n")
                return True
            return False
    except (FileNotFoundError, OSError):
        return False
    except Exception:
        return False
