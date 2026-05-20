"""PreToolUse allowlist grant reader for Claude Code hooks.

Single source of truth for grant-read, grant-match, and grant-consume
logic used by PreToolUse and PostToolUse hooks.

Contract:
  - PreToolUse hooks ONLY read the grant; they never delete it.
  - Deletion is deferred to posttool-allowlist-consume.py (PostToolUse).
  - Subagent firewall check stays in each caller; this library has no
    subagent awareness.

Extracted from pretool-orchestrator-gate.py lines 155-183 (initial
extraction, task aaf3c44). Extended with consolidation functions for
allow-6 (task 20260518-155948) to eliminate 4 independent open/flock/
JSON-load/match implementations across hook files.

Stdlib-only; Python 3.12+ required.
"""

import fcntl
import json
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import NamedTuple


class MatchResult(NamedTuple):
    """Result of a grant-pattern match."""
    pattern: str
    is_regex: bool
    matched_sub: str


def _match_loaded_grant(
    grant: dict,
    candidates: list[str],
    literal_policy: str,
    regex_timeout: int | None,
) -> MatchResult | None:
    """Pure match step: takes an already-loaded grant dict, no file I/O.

    Args:
        grant: decoded JSON grant dict (keys: pattern, is_regex)
        candidates: list of strings to match against (e.g. subcommands,
                    tool_name, full command)
        literal_policy: "exact_or_substr" (pattern==cand or pattern in cand),
                        "substr_only" (pattern in cand only), or
                        "exact_only" (pattern==cand only — used by PreTool
                        read_grant to mirror PostTool consume_grant_for_posttool
                        Branch 3 exact-only semantics)
        regex_timeout: SIGALRM timeout in seconds for regex match; None = no
                       timeout

    Returns:
        MatchResult on first match, None if no candidate matches or grant
        is invalid.
    """
    pattern = grant.get("pattern", "")
    if not isinstance(pattern, str) or not pattern:
        return None
    is_regex = bool(grant.get("is_regex", False))

    def _alarm_handler(signum, frame):
        raise TimeoutError("regex timeout")

    for cand in candidates:
        matched = False
        if is_regex:
            if regex_timeout is not None:
                old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
                signal.alarm(regex_timeout)
                try:
                    matched = bool(re.search(pattern, cand))
                except (re.error, TimeoutError):
                    matched = False
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                try:
                    matched = bool(re.search(pattern, cand))
                except re.error:
                    matched = False
        else:
            if literal_policy == "exact_or_substr":
                matched = pattern == cand or pattern in cand
            elif literal_policy == "exact_only":
                matched = pattern == cand
            else:  # substr_only
                matched = pattern in cand

        if matched:
            return MatchResult(pattern=pattern, is_regex=is_regex, matched_sub=cand)

    return None


def _load_and_match(
    sid: str,
    candidates: list[str],
    literal_policy: str,
    regex_timeout: int | None,
) -> MatchResult | None:
    """Blocking-lock wrapper: acquire LOCK_EX on grant file, json.load,
    then delegate to _match_loaded_grant.

    Args:
        sid: session id (used to locate /tmp/claude-bash-allowlist-<sid>.json)
        candidates: list of strings to match against
        literal_policy: passed through to _match_loaded_grant
        regex_timeout: passed through to _match_loaded_grant

    Returns:
        MatchResult on match, None otherwise. Never unlinks the grant file.
    """
    flag_path = Path(f"/tmp/claude-bash-allowlist-{sid}.json")
    try:
        with open(flag_path, "r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                grant = json.load(fh)
            except Exception:
                return None
            return _match_loaded_grant(grant, candidates, literal_policy, regex_timeout)
    except (FileNotFoundError, OSError):
        return None
    except Exception:
        return None


def read_grant(tool_name: str, sid: str) -> bool:
    """Check /allow grant for tool_name. Read-only — does NOT delete the grant.

    Literal match: pattern == tool_name ONLY (exact_only). Mirrors PostToolUse
    consume_grant_for_posttool Branch 3 to close the PreTool/PostTool
    asymmetry that allowed substring grants (e.g. '/allow Re') to bypass
    PreTool gates while never being consumed at PostTool — causing grant
    leakage past single-use. See cycle 20260519-211515 Item D.
    Regex match: re.search(pattern, tool_name) (unchanged, see is_regex
    branch of _match_loaded_grant).

    Deletion is deferred to posttool-allowlist-consume.py (PostToolUse).
    Returns True if grant matches, False otherwise (missing file = False).
    """
    result = _load_and_match(sid, [tool_name], "exact_only", None)
    if result is not None:
        sys.stderr.write(f"[ALLOW] grant matched for {tool_name}, consume deferred to PostToolUse\n")
        return True
    return False


def read_grant_for_git_command(command: str, sid: str) -> bool:
    """Check /allow grant for a git command. Read-only — does NOT delete the grant.

    Literal match: pattern in command (substr_only — no exact match branch).
    Regex match: re.search(pattern, command).

    Subagent firewall check stays in the caller (_check_git_allowlist).
    Returns True if grant matches, False otherwise.
    """
    result = _load_and_match(sid, [command], "substr_only", None)
    if result is not None:
        sys.stderr.write("[ALLOW] grant matched, consume deferred to PostToolUse\n")
        return True
    return False


def match_grant_for_bash_command(
    command: str,
    sid: str,
    regex_timeout: int = 1,
) -> MatchResult | None:
    """Match /allow grant for a compound bash command. Read-only — does NOT delete.

    Acquires LOCK_EX | LOCK_NB on sidecar .lock file with 3x100ms retry
    (matches existing bash heredoc NB-flock behavior — distinct from the
    blocking LOCK_EX used by _load_and_match).

    Splits command on &&, ||, ;, | (order: || before | so || becomes single
    newline, not |\\n).

    Returns MatchResult on first subcommand match, None if no match / no grant.
    Subagent firewall check stays in the bash wrapper caller.
    """
    flag_file = f"/tmp/claude-bash-allowlist-{sid}.json"
    lock_file = f"{flag_file}.lock"

    # NB flock with 3x100ms retry (preserves existing bash heredoc behavior)
    lock_fd = None
    try:
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        attempts = 0
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                attempts += 1
                if attempts >= 3:
                    return None
                time.sleep(0.1)

        # Lock held — read grant file
        if not os.path.exists(flag_file):
            return None
        try:
            with open(flag_file) as f:
                grant = json.load(f)
        except Exception:
            return None

        # Build subcommand candidates (split on && || ; |)
        # Order matters: || before | so '||' becomes a single newline
        s = command.replace("||", "\n").replace("&&", "\n").replace(";", "\n").replace("|", "\n")
        subcmds = [t.strip() for t in s.split("\n") if t.strip()]
        if not subcmds:
            subcmds = [command]

        return _match_loaded_grant(grant, subcmds, "substr_only", regex_timeout)

    except Exception:
        return None
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(lock_fd)
            except Exception:
                pass


def consume_grant_for_posttool(sid: str, tool_name: str, command: str) -> bool:
    """Atomically match and unlink the /allow grant for a PostToolUse event.

    This is the SOLE tool-execution consumption unlink site for /allow grant files.
    PreToolUse hooks must NEVER unlink; only this function does.

    Replicates posttool-allowlist-consume.py lines 68-91 branch logic:
      Branch 1 (Bash tool): compound-split + exact-or-substr match against
                            subcommands and full command
      Branch 2 (Bash fallback): exact pattern == tool_name if no subcommand matched
      Branch 3 (non-Bash, literal): exact-only (pattern == tool_name) —
                                    prevents /allow Write consuming TodoWrite
      Branch 4 (non-Bash, regex): re.search(pattern, tool_name)

    Performs match + os.unlink under a single fcntl.flock(LOCK_EX) (atomicity).

    Args:
        sid: session id
        tool_name: the tool that was called (e.g. "Bash", "Write", "TodoWrite")
        command: the Bash command string (empty string for non-Bash tools)

    Returns:
        True if grant matched and was consumed (unlinked), False otherwise.
    """
    grant_path = Path(f"/tmp/claude-bash-allowlist-{sid}.json")
    try:
        with open(grant_path, "r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                grant = json.load(fh)
            except Exception:
                return False

            pattern = grant.get("pattern", "")
            if not isinstance(pattern, str) or not pattern:
                return False
            is_regex = bool(grant.get("is_regex", False))

            matched = False
            if tool_name == "Bash":
                # Branch 1: split compound command, check each subcommand and full command
                # Mirrors posttool-allowlist-consume.py:34 — || before | (double-newline for ||)
                s = command.replace("||", "\n\n").replace("&&", "\n").replace(";", "\n").replace("|", "\n")
                subcommands = [t.strip() for t in s.split("\n") if t.strip()]
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
                # Branch 2 (Bash fallback): exact tool-name match for grants like `/allow Bash`
                if not matched and not is_regex and pattern == tool_name:
                    matched = True
            else:
                if is_regex:
                    # Branch 4
                    matched = bool(re.search(pattern, tool_name))
                else:
                    # Branch 3: exact-only — prevents /allow Write consuming TodoWrite
                    matched = (pattern == tool_name)

            if matched:
                try:
                    os.unlink(grant_path)
                except FileNotFoundError:
                    pass
                sys.stderr.write(f"[ALLOW] grant CONSUMED for {tool_name}\n")
                return True
            return False

    except FileNotFoundError:
        return False
    except Exception:
        return False
