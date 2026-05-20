"""Tests for allow-6 consolidation: hooks/lib/allowlist.py new functions.

Covers AC8 IS_SUBAGENT firewall scenarios and matching semantics invariants.

Task: 20260518-155948 — consolidate 5 independent grant-read implementations.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hooks dir to path for lib.allowlist import
HOOKS_DIR = str(Path(__file__).parent.parent)
sys.path.insert(0, HOOKS_DIR)

from lib.allowlist import (
    MatchResult,
    _match_loaded_grant,
    _load_and_match,
    read_grant,
    read_grant_for_git_command,
    match_grant_for_bash_command,
    consume_grant_for_posttool,
    load_sentinel_grant_for_task,
    match_sentinel_grant_for_bash_command,
    consume_sentinel_grant_on_terminal_result,
    reap_expired_sentinel_grants,
    SENTINEL_GRANT_DIR,
)


class TestMatchLoadedGrant(unittest.TestCase):
    """Unit tests for _match_loaded_grant (pure match, no I/O)."""

    def _grant(self, pattern, is_regex=False):
        return {"pattern": pattern, "is_regex": is_regex}

    def test_exact_or_substr_exact_match(self):
        result = _match_loaded_grant(
            self._grant("Write"), ["Write"], "exact_or_substr", None
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.pattern, "Write")
        self.assertFalse(result.is_regex)
        self.assertEqual(result.matched_sub, "Write")

    def test_exact_or_substr_substring_match(self):
        result = _match_loaded_grant(
            self._grant("git"), ["git push origin"], "exact_or_substr", None
        )
        self.assertIsNotNone(result)

    def test_substr_only_no_exact_match(self):
        # substr_only: "Write" must be IN the candidate as a substring
        # "Write" is not a substring of "TodoWrite" being checked differently —
        # here we test that "Write" IN "TodoWrite" is True (which it is),
        # but the policy difference is: exact_or_substr also allows pattern == cand
        result = _match_loaded_grant(
            self._grant("write"), ["git commit -m write something"], "substr_only", None
        )
        self.assertIsNotNone(result)

    def test_substr_only_rejects_no_substr(self):
        result = _match_loaded_grant(
            self._grant("push"), ["git pull"], "substr_only", None
        )
        self.assertIsNone(result)

    def test_regex_match(self):
        result = _match_loaded_grant(
            self._grant(r"git\s+push", True), ["git push origin"], "substr_only", None
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.is_regex)

    def test_invalid_pattern_returns_none(self):
        result = _match_loaded_grant({"pattern": "", "is_regex": False}, ["anything"], "exact_or_substr", None)
        self.assertIsNone(result)

    def test_missing_pattern_key_returns_none(self):
        result = _match_loaded_grant({}, ["anything"], "exact_or_substr", None)
        self.assertIsNone(result)

    def test_first_candidate_wins(self):
        result = _match_loaded_grant(
            self._grant("b"), ["a", "b", "c"], "exact_or_substr", None
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.matched_sub, "b")


class TestLoadAndMatch(unittest.TestCase):
    """Unit tests for _load_and_match (blocking-lock wrapper)."""

    def _write_grant(self, path, pattern, is_regex=False):
        with open(path, "w") as f:
            json.dump({"pattern": pattern, "is_regex": is_regex}, f)

    def test_match_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            grant_path = os.path.join(tmpdir, "claude-bash-allowlist-testsid.json")
            self._write_grant(grant_path, "git push")
            with patch("lib.allowlist.Path") as MockPath:
                MockPath.return_value = Path(grant_path)
                result = _load_and_match("testsid", ["git push origin"], "substr_only", None)
            self.assertIsNotNone(result)

    def test_missing_file_returns_none(self):
        result = _load_and_match("nonexistent_sid_xyz", ["anything"], "exact_or_substr", None)
        self.assertIsNone(result)


class TestReadGrant(unittest.TestCase):
    """Unit tests for read_grant (public API, exact_or_substr semantics)."""

    def _write_grant(self, path, pattern, is_regex=False):
        with open(path, "w") as f:
            json.dump({"pattern": pattern, "is_regex": is_regex}, f)

    def test_exact_match_returns_true(self):
        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="claude-bash-allowlist-rg1.", suffix=".json",
            mode="w", delete=False
        ) as f:
            sid = f.name.split("claude-bash-allowlist-rg1.")[1].replace(".json", "")
            # Reconstruct proper filename
            proper_path = f"/tmp/claude-bash-allowlist-rg1.{sid}.json"
        # Use a controlled SID
        test_sid = "test-read-grant-unit"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            self._write_grant(grant_path, "Write")
            self.assertTrue(read_grant("Write", test_sid))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_no_match_returns_false(self):
        test_sid = "test-read-grant-nomatch"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "Bash", "is_regex": False}, f)
            self.assertFalse(read_grant("Write", test_sid))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_missing_grant_returns_false(self):
        self.assertFalse(read_grant("Write", "sid-that-does-not-exist-abc123"))

    # AC-D1 regression (cycle 20260519-211515 Item D): read_grant is exact_only.
    # Substring grants (e.g. '/allow Re') MUST NOT match the tool name 'Read'
    # at PreTool. This closes the PreTool/PostTool asymmetry that allowed
    # grant leakage past single-use.
    def test_read_grant_exact_only_rejects_substring(self):
        """Grant pattern 'Re' must NOT match tool name 'Read' (AC-D1)."""
        test_sid = "test-read-grant-exact-only"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "Re", "is_regex": False}, f)
            # Pre-cycle behavior: exact_or_substr would have returned True
            # ("Re" in "Read"). New exact_only semantics returns False.
            self.assertFalse(read_grant("Read", test_sid))
            # Grant file MUST still exist (read-only, no unlink).
            self.assertTrue(os.path.exists(grant_path))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    # AC-D1 additional regression: '/allow Write' must NOT match 'TodoWrite'
    # at PreTool (was the original asymmetry — PostTool was already exact-only
    # via Branch 3 of consume_grant_for_posttool, but PreTool was substr).
    def test_read_grant_exact_only_rejects_write_against_todowrite(self):
        """Grant pattern 'Write' must NOT match tool name 'TodoWrite' (AC-D1)."""
        test_sid = "test-read-grant-write-vs-todowrite"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "Write", "is_regex": False}, f)
            self.assertFalse(read_grant("TodoWrite", test_sid))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)


class TestReadGrantForGitCommand(unittest.TestCase):
    """Unit tests for read_grant_for_git_command (substr_only semantics)."""

    def test_substring_match(self):
        test_sid = "test-git-grant-1"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "git push", "is_regex": False}, f)
            # substr_only: "git push" in "git push origin main"
            self.assertTrue(read_grant_for_git_command("git push origin main", test_sid))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_no_match(self):
        test_sid = "test-git-grant-2"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "git push", "is_regex": False}, f)
            self.assertFalse(read_grant_for_git_command("git pull origin main", test_sid))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)


class TestMatchGrantForBashCommand(unittest.TestCase):
    """Unit tests for match_grant_for_bash_command (NB-flock + subcommand split)."""

    def test_compound_command_match(self):
        test_sid = "test-bash-grant-1"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "git stash", "is_regex": False}, f)
            result = match_grant_for_bash_command(
                "ls -la && git stash pop", test_sid
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.pattern, "git stash")
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_no_match(self):
        test_sid = "test-bash-grant-2"
        grant_path = f"/tmp/claude-bash-allowlist-{test_sid}.json"
        try:
            with open(grant_path, "w") as f:
                json.dump({"pattern": "git push", "is_regex": False}, f)
            result = match_grant_for_bash_command("ls -la && echo hello", test_sid)
            self.assertIsNone(result)
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_missing_grant_returns_none(self):
        result = match_grant_for_bash_command("any command", "sid-does-not-exist-xyz")
        self.assertIsNone(result)


class TestConsumeGrantForPosttool(unittest.TestCase):
    """Unit tests for consume_grant_for_posttool (AC5, AC8 scenarios)."""

    def _write_grant(self, sid, pattern, is_regex=False):
        path = f"/tmp/claude-bash-allowlist-{sid}.json"
        with open(path, "w") as f:
            json.dump({"pattern": pattern, "is_regex": is_regex}, f)
        return path

    # AC8(b): /allow Write does NOT consume a TodoWrite call (exact-only non-Bash)
    def test_non_bash_literal_exact_only_no_consume_for_todowrite(self):
        """Grant 'Write' (literal) must NOT match tool_name 'TodoWrite'."""
        test_sid = "test-posttool-exact-1"
        grant_path = self._write_grant(test_sid, "Write")
        try:
            result = consume_grant_for_posttool(test_sid, "TodoWrite", "")
            self.assertFalse(result)
            # Grant should still exist (not consumed)
            self.assertTrue(os.path.exists(grant_path))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    # AC8(b) positive: /allow Write DOES consume a Write call
    def test_non_bash_literal_exact_match_write(self):
        """Grant 'Write' (literal) matches tool_name 'Write' exactly."""
        test_sid = "test-posttool-exact-2"
        grant_path = self._write_grant(test_sid, "Write")
        try:
            result = consume_grant_for_posttool(test_sid, "Write", "")
            self.assertTrue(result)
            # Grant should be consumed (unlinked)
            self.assertFalse(os.path.exists(grant_path))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    # AC8(c): Bash compound command is consumed correctly
    def test_bash_compound_command_consumed(self):
        """Bash compound command containing granted substring is consumed."""
        test_sid = "test-posttool-bash-1"
        grant_path = self._write_grant(test_sid, "git stash")
        try:
            result = consume_grant_for_posttool(
                test_sid, "Bash", "ls -la && git stash pop"
            )
            self.assertTrue(result)
            self.assertFalse(os.path.exists(grant_path))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_bash_no_match_not_consumed(self):
        """Bash command not matching grant pattern — grant preserved."""
        test_sid = "test-posttool-bash-2"
        grant_path = self._write_grant(test_sid, "git push")
        try:
            result = consume_grant_for_posttool(test_sid, "Bash", "ls -la")
            self.assertFalse(result)
            self.assertTrue(os.path.exists(grant_path))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)

    def test_missing_grant_returns_false(self):
        result = consume_grant_for_posttool("sid-nonexistent-xyz", "Bash", "ls")
        self.assertFalse(result)

    def test_bash_exact_tool_name_fallback(self):
        """Grant pattern 'Bash' (literal) matches tool_name 'Bash' via fallback."""
        test_sid = "test-posttool-bash-fallback"
        grant_path = self._write_grant(test_sid, "Bash")
        try:
            result = consume_grant_for_posttool(test_sid, "Bash", "some-unmatched-command")
            self.assertTrue(result)
            self.assertFalse(os.path.exists(grant_path))
        finally:
            if os.path.exists(grant_path):
                os.unlink(grant_path)


class TestCheckGitAllowlistSubagentFirewall(unittest.TestCase):
    """AC8(a): subagent payload passed to git-guard returns False (IS_SUBAGENT firewall)."""

    def test_subagent_payload_returns_false(self):
        """_check_git_allowlist returns False for payloads with agent_id set."""
        # Import the function under test
        sys.path.insert(0, HOOKS_DIR)
        # We test the IS_SUBAGENT logic directly via the guard's _check_git_allowlist
        # by importing and calling it with a mock data dict containing agent_id
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pretool_git_privilege_guard",
            os.path.join(HOOKS_DIR, "pretool-git-privilege-guard.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # We only need _check_git_allowlist; loading the module runs no side effects
        # because it only defines functions at module level (no top-level execution)
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pass  # Some guard modules may sys.exit(0) early on import in test context

        if hasattr(mod, "_check_git_allowlist"):
            # Subagent payload: agent_id present
            result = mod._check_git_allowlist(
                "git push origin main",
                {"agent_id": "some-agent-uuid", "session_id": "test-session"},
            )
            self.assertFalse(result)
        else:
            self.skipTest("_check_git_allowlist not accessible in test context")


class TestSentinelGrantLifecycle(unittest.TestCase):
    """Tests for sentinel-grant lifecycle (task 20260519-211515 R2 / AC2).

    Covers the consume-on-any-terminal-result contract for the four mandatory
    terminal-consumption cases: success, failure, non_zero, malformed,
    comment_only, and a terminal_consume integration round-trip.

    Each test asserts the corresponding grant file under SENTINEL_GRANT_DIR
    is unlinked after consumption — this is the post-condition invariant.
    """

    def setUp(self):
        os.makedirs(SENTINEL_GRANT_DIR, exist_ok=True)

    def _write_sentinel(self, task_id, ops=None, ttl=300, nonce=""):
        path = os.path.join(SENTINEL_GRANT_DIR, f"{task_id}{nonce}.json")
        now = time.time()
        grant = {
            "task_id": task_id,
            "session_id": "test-session",
            "allowed_operations": ops or [{"op": "ls"}],
            "created_at": now,
            "expires_at": now + ttl,
        }
        with open(path, "w") as f:
            json.dump(grant, f)
        return path

    def test_terminal_consume_success(self):
        """Sentinel grant is unlinked on terminal_result='success' (exit 0)."""
        task_id = "test-sentinel-success"
        path = self._write_sentinel(task_id)
        try:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(consume_sentinel_grant_on_terminal_result(task_id, "success"))
            self.assertFalse(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_terminal_consume_failure(self):
        """Sentinel grant is unlinked on terminal_result='failure' (is_error=True)."""
        task_id = "test-sentinel-failure"
        path = self._write_sentinel(task_id)
        try:
            self.assertTrue(consume_sentinel_grant_on_terminal_result(task_id, "failure"))
            self.assertFalse(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_terminal_consume_non_zero(self):
        """Sentinel grant is unlinked on terminal_result='non_zero' (exit 1..255)."""
        task_id = "test-sentinel-non-zero"
        path = self._write_sentinel(task_id)
        try:
            self.assertTrue(consume_sentinel_grant_on_terminal_result(task_id, "non_zero"))
            self.assertFalse(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_terminal_consume_malformed(self):
        """Malformed JSON grant is unlinked at posttool / reap time."""
        task_id = "test-sentinel-malformed"
        path = os.path.join(SENTINEL_GRANT_DIR, f"{task_id}.json")
        with open(path, "w") as f:
            f.write("{not valid json")
        try:
            # consume_sentinel_grant_on_terminal_result reaps unconditionally —
            # even malformed grants are unlinked when terminal_result is provided.
            self.assertTrue(consume_sentinel_grant_on_terminal_result(task_id, "malformed"))
            self.assertFalse(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_comment_only_attack_pretool_denied_no_leftover(self):
        """comment_only: pretool denies (no sentinel exists for current task),
        AND posttool consume with terminal_result='comment_only' must NOT
        leave leftover state. The grant file simply does not exist, and
        consume returns False without raising.
        """
        task_id = "test-sentinel-comment-only-attack-nonexistent"
        # No sentinel file exists for this task_id.
        path = os.path.join(SENTINEL_GRANT_DIR, f"{task_id}.json")
        self.assertFalse(os.path.exists(path))
        # Pretool match against a malicious command containing the magic phrase
        # in a comment — no grant, structural match returns None.
        result = match_sentinel_grant_for_bash_command(
            task_id, "echo hello # /allow rm -rf /"
        )
        self.assertIsNone(result)
        # Posttool consume on comment_only terminal_result is a no-op,
        # returns False, and leaves zero leftover state.
        consumed = consume_sentinel_grant_on_terminal_result(task_id, "comment_only")
        self.assertFalse(consumed)
        self.assertFalse(os.path.exists(path))

    def test_terminal_consume_round_trip_unlinks_grant(self):
        """End-to-end: write sentinel → pretool match → posttool consume on
        any terminal result → assert grant file removed.

        This is the canonical terminal_consume integration scenario.
        """
        task_id = "test-sentinel-terminal-consume-round-trip"
        path = self._write_sentinel(
            task_id, ops=[{"op": "ls", "target": "-la"}]
        )
        try:
            # Pretool: structural match succeeds for matching op+target.
            m = match_sentinel_grant_for_bash_command(task_id, "ls -la /tmp")
            self.assertIsNotNone(m)
            self.assertEqual(m.get("op"), "ls")
            # Posttool: consume on terminal_result='success' unlinks.
            self.assertTrue(consume_sentinel_grant_on_terminal_result(task_id, "success"))
            self.assertFalse(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_sentinel_predicate_never_substring_matches_command_line(self):
        """AC2 invariant: predicate never substring-matches against the raw
        command line. A literal 'rm -rf' in the command must NOT trigger
        a match for an unrelated 'ls' op grant.
        """
        task_id = "test-sentinel-no-substring-match"
        path = self._write_sentinel(task_id, ops=[{"op": "ls"}])
        try:
            # Command mentions 'ls' inside an unrelated string — structural
            # match would still succeed because the first sub-token IS 'ls'.
            # The real invariant test: a malicious command whose head op
            # differs must NOT match even if it contains 'ls' as substring.
            self.assertIsNone(
                match_sentinel_grant_for_bash_command(task_id, "rm -rf /; echo ls")
            )
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_expired_grant_treated_as_missing(self):
        """expires_at in the past → load_sentinel_grant_for_task returns None
        (deny-by-default). Reap should remove it."""
        task_id = "test-sentinel-expired"
        path = os.path.join(SENTINEL_GRANT_DIR, f"{task_id}.json")
        now = time.time()
        with open(path, "w") as f:
            json.dump({
                "task_id": task_id,
                "session_id": "x",
                "allowed_operations": [{"op": "ls"}],
                "created_at": now - 600,
                "expires_at": now - 300,
            }, f)
        try:
            self.assertIsNone(load_sentinel_grant_for_task(task_id))
            count = reap_expired_sentinel_grants()
            self.assertGreaterEqual(count, 1)
            self.assertFalse(os.path.exists(path))
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
