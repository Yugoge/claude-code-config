#!/usr/bin/env python3
"""
PostToolUse Hook: /allow grant consumption.

Atomically deletes the /allow grant file after a tool executes successfully.
PreToolUse hooks are now read-only grant checkers; this hook is the sole
consume point. Main-agent only (subagents are exempt).

PostToolUse fires only when all PreToolUse hooks exit 0 (tool was allowed).
If any PreToolUse hook exits 2, PostToolUse never fires — grant persists
for retry. This is correct UX: user can retry with the same grant.

Exit 0 always (fail-open). Silently exits if no grant or no match.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.subagent import is_subagent_context  # noqa: E402
from lib.allowlist import consume_grant_for_posttool  # noqa: E402


def _split_bash_command(cmd: str) -> list:
    """Split a compound Bash command on &&, ||, ;, | separators.

    Mirrors pretool-bash-safety.sh split_subcommands (lines 227-230):
    process || before | so '||' becomes a double-newline, not two pipes.
    """
    # Order matters: || must be replaced before |
    s = cmd.replace("||", "\n\n").replace("&&", "\n").replace(";", "\n").replace("|", "\n")
    return [t.strip() for t in s.split("\n") if t.strip()]


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)

    # Main-agent only — subagents are exempt
    if is_subagent_context(data):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "default")
    grant_path = Path(f"/tmp/claude-bash-allowlist-{session_id}.json")

    try:
        with open(grant_path, "r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                grant = json.load(fh)
            except Exception:
                sys.exit(0)

            pattern = grant.get("pattern", "")
            if not isinstance(pattern, str) or not pattern:
                sys.exit(0)

            is_regex = grant.get("is_regex", False)

            matched = False
            if tool_name == "Bash":
                command = (data.get("tool_input") or {}).get("command", "")
                subcommands = _split_bash_command(command)
                # Include full command as a candidate too
                candidates = subcommands + [command]
                for part in candidates:
                    if is_regex:
                        if re.search(pattern, part):
                            matched = True
                            break
                    else:
                        if pattern == part or pattern in part:
                            matched = True
                            break
                # Fallback: exact tool-name match for grants like `/allow Bash`
                if not matched and not is_regex and pattern == tool_name:
                    matched = True
            else:
                if is_regex:
                    matched = bool(re.search(pattern, tool_name))
                else:
                    # Exact match only for literal grants (prevents /allow Write from
                    # consuming a TodoWrite call)
                    matched = (pattern == tool_name)

            if matched:
                try:
                    os.unlink(grant_path)
                except FileNotFoundError:
                    pass
                sys.stderr.write(f"[ALLOW] grant CONSUMED for {tool_name}\n")
            # If not matched: exit 0 silently — grant stays for the intended tool call

    except FileNotFoundError:
        pass
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
