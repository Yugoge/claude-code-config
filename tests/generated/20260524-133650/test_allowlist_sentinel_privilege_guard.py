"""Tests for sentinel grant bypass in pretool-git-privilege-guard._check_git_allowlist.

Task: 20260524-133650 — /allow sentinel bypass for git ref-mutation privilege guard.

Covers AC1-AC8 from acceptance-criteria-20260524-133650.json.
"""

import ast
import json
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add hooks dir to path so imports resolve the same way as the hook itself.
# parent = .../20260524-133650, parent.parent = generated, parent.parent.parent = tests,
# parent.parent.parent.parent = dot-claude (repo root), then + hooks/.
HOOKS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "hooks")
sys.path.insert(0, HOOKS_DIR)

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "pretool_git_privilege_guard",
    Path(HOOKS_DIR) / "pretool-git-privilege-guard.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_check_git_allowlist = _mod._check_git_allowlist


SENTINEL_GRANT_DIR = "/tmp/claude-grants"
LEGACY_GRANT_PREFIX = "/tmp/claude-bash-allowlist-"

TEST_TASK_ID = "test-task-20260524-133650"
TEST_SID = "test-session-20260524-133650"


def _write_sentinel_grant(task_id: str, sid: str, ops: list, *, expired: bool = False) -> Path:
    """Write a sentinel grant JSON to /tmp/claude-grants/<task_id>.json."""
    Path(SENTINEL_GRANT_DIR).mkdir(parents=True, exist_ok=True)
    path = Path(SENTINEL_GRANT_DIR) / f"{task_id}.json"
    expires_at = time.time() - 1 if expired else time.time() + 300
    grant = {
        "task_id": task_id,
        "session_id": sid,
        "allowed_operations": ops,
        "created_at": time.time(),
        "expires_at": expires_at,
    }
    path.write_text(json.dumps(grant))
    return path


def _write_legacy_grant(sid: str, pattern: str) -> Path:
    """Write a legacy grant JSON to /tmp/claude-bash-allowlist-<sid>.json."""
    path = Path(f"{LEGACY_GRANT_PREFIX}{sid}.json")
    grant = {"pattern": pattern, "is_regex": False}
    path.write_text(json.dumps(grant))
    return path


def _remove_sentinel(task_id: str) -> None:
    path = Path(SENTINEL_GRANT_DIR) / f"{task_id}.json"
    path.unlink(missing_ok=True)


def _remove_legacy(sid: str) -> None:
    path = Path(f"{LEGACY_GRANT_PREFIX}{sid}.json")
    path.unlink(missing_ok=True)


class TestSentinelPrivilegeGuard(unittest.TestCase):
    """AC1-AC8 tests for _check_git_allowlist() sentinel grant support."""

    def setUp(self):
        # Ensure clean state: remove any leftover sentinel/legacy grants for test IDs.
        _remove_sentinel(TEST_TASK_ID)
        _remove_legacy(TEST_SID)

    def tearDown(self):
        _remove_sentinel(TEST_TASK_ID)
        _remove_legacy(TEST_SID)

    # ------------------------------------------------------------------
    # AC1: sentinel grant bypasses privilege guard for main-agent
    # ------------------------------------------------------------------
    def test_sentinel_grant_bypasses_guard_main_agent(self):
        """AC1: valid sentinel + no agent_id → True."""
        _write_sentinel_grant(
            TEST_TASK_ID,
            TEST_SID,
            [{"op": "git", "args_contain": ["branch -D foo"]}],
        )
        data = {"session_id": TEST_SID}
        with patch.dict(os.environ, {"CLAUDE_TASK_ID": TEST_TASK_ID}, clear=False):
            result = _check_git_allowlist("git branch -D foo", data)
        self.assertTrue(result, "Sentinel grant must allow main-agent to run git branch -D foo")

    # ------------------------------------------------------------------
    # AC2: sentinel grant bypasses subagent firewall
    # ------------------------------------------------------------------
    def test_sentinel_grant_bypasses_subagent_firewall(self):
        """AC2: valid sentinel + agent_id present → True (sentinel not gated by firewall)."""
        _write_sentinel_grant(
            TEST_TASK_ID,
            TEST_SID,
            [{"op": "git", "args_contain": ["branch -D foo"]}],
        )
        data = {"session_id": TEST_SID, "agent_id": "test-subagent-id"}
        with patch.dict(os.environ, {"CLAUDE_TASK_ID": TEST_TASK_ID}, clear=False):
            result = _check_git_allowlist("git branch -D foo", data)
        self.assertTrue(result, "Sentinel grant must bypass the subagent firewall per M2 decision")

    # ------------------------------------------------------------------
    # AC3: no grant → False
    # ------------------------------------------------------------------
    def test_no_grant_returns_false(self):
        """AC3: no sentinel and no legacy grant → False."""
        data = {"session_id": TEST_SID}
        with patch.dict(os.environ, {"CLAUDE_TASK_ID": TEST_TASK_ID}, clear=False):
            result = _check_git_allowlist("git branch -D foo", data)
        self.assertFalse(result, "No grant must preserve default-deny behavior")

    # ------------------------------------------------------------------
    # AC4: legacy grant still works for main-agent
    # ------------------------------------------------------------------
    def test_legacy_grant_still_works_main_agent(self):
        """AC4: legacy grant + no agent_id → True (legacy path unchanged)."""
        _write_legacy_grant(TEST_SID, "git branch -D foo")
        data = {"session_id": TEST_SID}
        # No CLAUDE_TASK_ID: falls back to SID, sentinel lookup finds nothing.
        with patch.dict(os.environ, {}, clear=False):
            env_without_task_id = {k: v for k, v in os.environ.items() if k != "CLAUDE_TASK_ID"}
            with patch.dict(os.environ, env_without_task_id, clear=True):
                result = _check_git_allowlist("git branch -D foo", data)
        self.assertTrue(result, "Legacy grant must still allow main-agent commands")

    # ------------------------------------------------------------------
    # AC5: legacy grant + subagent → False (firewall preserved for legacy)
    # ------------------------------------------------------------------
    def test_legacy_grant_subagent_firewall_preserved(self):
        """AC5: legacy grant only + agent_id → False (subagent firewall on legacy path)."""
        _write_legacy_grant(TEST_SID, "git branch -D foo")
        data = {"session_id": TEST_SID, "agent_id": "sub"}
        # Ensure no sentinel exists for the SID-derived task_id.
        _remove_sentinel(TEST_SID)
        with patch.dict(os.environ, {}, clear=False):
            env_without_task_id = {k: v for k, v in os.environ.items() if k != "CLAUDE_TASK_ID"}
            with patch.dict(os.environ, env_without_task_id, clear=True):
                result = _check_git_allowlist("git branch -D foo", data)
        self.assertFalse(result, "Subagent firewall must be preserved for the legacy grant path")

    # ------------------------------------------------------------------
    # AC6: sentinel does not over-match unrelated commands
    # ------------------------------------------------------------------
    def test_sentinel_does_not_match_unrelated_command(self):
        """AC6: sentinel for 'git branch -D foo' must NOT match 'git status'."""
        _write_sentinel_grant(
            TEST_TASK_ID,
            TEST_SID,
            [{"op": "git", "args_contain": ["branch -D foo"]}],
        )
        data = {"session_id": TEST_SID}
        with patch.dict(os.environ, {"CLAUDE_TASK_ID": TEST_TASK_ID}, clear=False):
            result = _check_git_allowlist("git status", data)
        self.assertFalse(result, "Sentinel must not authorize commands outside its args_contain scope")

    # ------------------------------------------------------------------
    # AC7: expired sentinel → False
    # ------------------------------------------------------------------
    def test_expired_sentinel_not_honored(self):
        """AC7: expired sentinel (expires_at in the past) → False."""
        _write_sentinel_grant(
            TEST_TASK_ID,
            TEST_SID,
            [{"op": "git", "args_contain": ["branch -D foo"]}],
            expired=True,
        )
        data = {"session_id": TEST_SID}
        with patch.dict(os.environ, {"CLAUDE_TASK_ID": TEST_TASK_ID}, clear=False):
            result = _check_git_allowlist("git branch -D foo", data)
        self.assertFalse(result, "Expired sentinel must not be honored")

    # ------------------------------------------------------------------
    # AC8: _evaluate_push() call ordering — _push_has_forbidden_ref_mutation
    #       must appear BEFORE _check_git_allowlist in the function body.
    # ------------------------------------------------------------------
    def test_push_ordering_preserved(self):
        """AC8: in _evaluate_push(), _push_has_forbidden_ref_mutation call line
        must be numerically less than _check_git_allowlist call line.
        """
        guard_path = Path(HOOKS_DIR) / "pretool-git-privilege-guard.py"
        src = guard_path.read_text()
        tree = ast.parse(src)
        lines = src.splitlines()

        # Find _evaluate_push function node.
        eval_push_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_evaluate_push":
                eval_push_node = node
                break
        self.assertIsNotNone(eval_push_node, "_evaluate_push function not found in source")

        # Collect line numbers of calls to the two functions within _evaluate_push.
        forbidden_lines = []
        allowlist_lines = []
        for node in ast.walk(eval_push_node):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                else:
                    continue
                if name == "_push_has_forbidden_ref_mutation":
                    forbidden_lines.append(node.lineno)
                elif name == "_check_git_allowlist":
                    allowlist_lines.append(node.lineno)

        self.assertTrue(
            len(forbidden_lines) >= 1,
            "_push_has_forbidden_ref_mutation must be called in _evaluate_push",
        )
        self.assertTrue(
            len(allowlist_lines) >= 1,
            "_check_git_allowlist must be called in _evaluate_push",
        )
        self.assertLess(
            min(forbidden_lines),
            min(allowlist_lines),
            "_push_has_forbidden_ref_mutation must appear BEFORE _check_git_allowlist in _evaluate_push",
        )


if __name__ == "__main__":
    unittest.main()
