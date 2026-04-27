#!/usr/bin/env python3
"""Tool-policy registry loader and authorization decisions.

Reads /root/.claude/policies/tool-policy.v1.json and provides a single
is_allowed(role, tool_name, target_path) entrypoint shared by:
  - pretool-tool-policy.py (canonical enforcement)
  - pretool-subagent-code-block.py (backstop shim)

Fail-safe contract:
  - On policy load failure (file missing, parse error), `dev` role gets
    fail-safe ALLOW (preserves the historical ALLOWED_TYPES = {'dev'}
    behavior), every other role gets fail-CLOSED DENY.
  - On any unexpected exception, return (True, "fail-safe-exception")
    for the dev role, (False, "fail-closed-exception") for others.

Path prefix matching (T1.2 fix for B.11):
  - Targets are normalized via os.path.realpath (collapses symlinks
    such as /root/.claude -> /dev/shm/dev-workspace/dot-claude/).
  - Universal allow: prefix '*' always matches.
  - Glob: prefix containing '*' uses fnmatch.fnmatchcase, with a
    trailing '*' auto-appended so '*/docs/dev/foo-' matches any suffix
    after the prefix anchor (e.g. inside any worktree).
  - Absolute prefix (starts with '/'): boundary-aware — matches when
    the prefix occurs at the start of the target OR immediately after
    a '/' boundary character. This prevents the old substring-collision
    bug where '/.claude/hooks/' matched a target containing
    '/root/.claude/worktrees/<sid>/docs/dev/...' just because the
    string '.claude/' appeared somewhere; the matcher now respects
    path boundaries.
  - Relative prefix (doesn't start with '/' and contains no '*'):
    falls back to legacy substring containment. New policies should
    always anchor with '/' or '*'; relative prefixes remain only for
    backward compatibility.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from typing import Optional, Tuple

POLICY_PATH = "/root/.claude/policies/tool-policy.v1.json"
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
ALLOWED_TYPES_FALLBACK = {"dev"}

_CACHE: Optional[dict] = None
_CACHE_LOADED = False


def load_policy() -> Optional[dict]:
    """Read tool-policy.v1.json. Returns dict or None on error."""
    global _CACHE, _CACHE_LOADED
    if _CACHE_LOADED:
        return _CACHE
    _CACHE_LOADED = True
    try:
        with open(POLICY_PATH) as f:
            _CACHE = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"policy_registry: load failed ({e})\n")
        _CACHE = None
    return _CACHE


def _reset_cache_for_tests() -> None:
    global _CACHE, _CACHE_LOADED
    _CACHE = None
    _CACHE_LOADED = False


def get_role_policy(role: str) -> dict:
    """Return the role's policy dict, or a deny-all fallback."""
    policy = load_policy()
    if not policy:
        return {"allowed_tools": [], "default_action": "deny"}
    roles = policy.get("roles", {})
    return roles.get(role, {"allowed_tools": [], "default_action": "deny"})


def _entry_matches(entry: str, tool_name: str) -> bool:
    if entry.endswith("*"):
        return tool_name.startswith(entry[:-1])
    return entry == tool_name


def _tool_in_list(tool_name: str, items: list) -> bool:
    """Match tool against a list, supporting `*` wildcard suffix."""
    for entry in items or []:
        if isinstance(entry, str) and _entry_matches(entry, tool_name):
            return True
    return False


def _normalize_target(target: str) -> str:
    """Resolve target to canonical absolute path, collapsing symlinks.

    On any failure (target missing, permission denied), fall back to
    os.path.abspath so policy decisions never crash on non-existent paths
    (e.g. Write to a file that does not exist yet).
    """
    try:
        return os.path.realpath(target)
    except OSError:
        try:
            return os.path.abspath(target)
        except Exception:  # pragma: no cover
            return target


def _glob_match(prefix: str, target_canonical: str) -> bool:
    """fnmatch glob match; conditionally auto-extend trailing '*'.

    Auto-append '*' ONLY when the pattern ends with a prefix marker
    (a trailing '-' for artifact prefixes like '*/docs/dev/qa-report-',
    or a trailing '/' for directory prefixes like '*/docs/dev/overnight/').
    Patterns that end with anything else (e.g., a literal filename like
    '*/cp-state-ba.json') are matched EXACTLY as written, with no
    auto-suffix. This closes the codex-flagged leak where
    '*/cp-state-ba.json' would otherwise match
    '/root/.../cp-state-ba.json.bak' or '/root/.../cp-state-ba.json/evil'.

    Patterns already ending in '*' are passed through untouched.
    """
    if prefix.endswith("*") or prefix.endswith("-") or prefix.endswith("/"):
        pattern = prefix if prefix.endswith("*") else prefix + "*"
    else:
        pattern = prefix
    return fnmatch.fnmatchcase(target_canonical, pattern)


def _boundary_substring_match(prefix: str, target_canonical: str) -> bool:
    """True if prefix appears as a path-segment boundary substring of target.

    Semantics: prefix starts with '/' (caller guarantees), so the leading
    '/' is itself a path-segment boundary marker. The prefix is a valid
    path-segment match iff it appears as a literal substring of target —
    the leading '/' of the prefix coincides with a real '/' character in
    the target, which is by definition a path-component boundary.

    Example: prefix '/.claude/hooks/' MATCHES target '/root/.claude/hooks/x.py'
    because '/.claude/hooks/' appears as a substring starting at position 5,
    where target[5] is '/' (a path boundary).

    What this rule prevents (the B.11 substring-collision bug): the BROAD
    prefix '/.claude/' must not be in the policy — the policy file's
    explicit subdir list (hooks/, agents/, commands/, policies/, schemas/,
    scripts/, settings.json) is the only correct way to express
    'protected /.claude subdirectory'. Broad '/.claude/' would match
    legitimate worktree artifact paths like
    '/root/.claude/worktrees/X/docs/dev/...' — which is a policy-file
    issue, not a matcher issue, and is enforced by the BA's policy
    review (T1.2 implementation_notes explicitly forbids broad
    '/.claude/').
    """
    return prefix in target_canonical


def _prefix_matches(prefix: str, target_canonical: str) -> bool:
    """Boundary-aware prefix match — see module docstring for full rules."""
    if prefix == "*":
        return True
    if "*" in prefix:
        return _glob_match(prefix, target_canonical)
    if prefix.startswith("/"):
        return _boundary_substring_match(prefix, target_canonical)
    # Relative prefix — fall back to substring containment for legacy
    # entries. New policies should always anchor with '/' or '*'.
    return prefix in target_canonical


def _candidate_targets(target: str) -> list:
    """Return both the original absolute target and its realpath form.

    Logical path prefixes like '/.claude/specs/' are written against the
    user-facing path, but realpath collapses the
    /root/.claude -> /dev/shm/dev-workspace/dot-claude/ symlink at runtime.
    Matching against BOTH forms keeps logical anchors working AND still
    catches escapes that go through the canonical form.
    """
    if not target:
        return []
    abs_t = os.path.abspath(target)
    canonical = _normalize_target(target)
    if abs_t != canonical:
        return [abs_t, canonical]
    return [abs_t]


def _prefix_matches_any_candidate(prefix: str, candidates: list) -> bool:
    for cand in candidates:
        if _prefix_matches(prefix, cand):
            return True
    return False


def _path_in_prefixes(target: Optional[str], prefixes: list) -> bool:
    if not target or not prefixes:
        return False
    candidates = _candidate_targets(target)
    for p in prefixes:
        if isinstance(p, str) and _prefix_matches_any_candidate(p, candidates):
            return True
    return False


def _check_tool_lists(role_pol: dict, tool_name: str) -> Optional[Tuple[bool, str]]:
    if _tool_in_list(tool_name, role_pol.get("denied_tools", [])):
        return (False, f"tool {tool_name} explicitly denied")
    allowed = role_pol.get("allowed_tools", [])
    if allowed and not _tool_in_list(tool_name, allowed):
        return (False, f"tool {tool_name} not in allowed_tools")
    return None


def _check_write_path(role_pol: dict, target: Optional[str]) -> Tuple[bool, str]:
    denied_w = role_pol.get("denied_write_path_prefixes", [])
    if _path_in_prefixes(target, denied_w):
        return (False, f"write target {target} matches denied_write_path_prefixes")
    allowed_w = role_pol.get("allowed_write_path_prefixes", [])
    if allowed_w and "*" not in allowed_w and not _path_in_prefixes(target, allowed_w):
        return (False, f"write target {target} not in allowed_write_path_prefixes")
    return (True, "ok")


def _check_read_path(role_pol: dict, target: Optional[str]) -> Tuple[bool, str]:
    denied_r = role_pol.get("denied_path_prefixes", [])
    if _path_in_prefixes(target, denied_r):
        return (False, f"read target {target} matches denied_path_prefixes")
    return (True, "ok")


def _fail_open_or_closed(role: str, reason: str) -> Tuple[bool, str]:
    if role in ALLOWED_TYPES_FALLBACK:
        return (True, f"fail-safe-{reason}")
    return (False, f"fail-closed-{reason}")


def is_allowed(
    role: str, tool_name: str, target_path: Optional[str]
) -> Tuple[bool, str]:
    """Return (allowed: bool, reason: str). See module docstring."""
    try:
        policy = load_policy()
        if not policy:
            return _fail_open_or_closed(role, "policy-unavailable")
        role_pol = get_role_policy(role)
        tool_check = _check_tool_lists(role_pol, tool_name)
        if tool_check is not None:
            return tool_check
        if tool_name in WRITE_TOOLS:
            return _check_write_path(role_pol, target_path)
        return _check_read_path(role_pol, target_path)
    except Exception as e:  # pragma: no cover
        sys.stderr.write(f"policy_registry: unexpected ({e})\n")
        return _fail_open_or_closed(role, "exception")
