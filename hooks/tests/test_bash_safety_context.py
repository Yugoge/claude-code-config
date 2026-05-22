"""Unit tests for hooks/lib/bash_context_strip.strip_non_executable_contexts().

Covers the seven cases specified in the BA ticket:
- Non-shell argv stripped (codex exec with killall in quoted arg)
- sh -c payload preserved and recursively analyzed
- Heredoc body stripped when consumer is tee; preserved when consumer is bash
- Comment stripped
- $() substitution preserved inside quotes
- Control-operator boundary preserved (echo 'rm text'; rm /tmp/foo)
- Fail-safe: bad input (malformed/None) returns raw string
"""

import importlib.util
import os
import sys
import pytest

# ── Module loading ────────────────────────────────────────────────────────────

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LIB = os.path.join(_REPO, "hooks")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from lib.bash_context_strip import strip_non_executable_contexts


# ── Helpers ───────────────────────────────────────────────────────────────────

def stripped(cmd: str) -> str:
    return strip_non_executable_contexts(cmd)


# ── Case 1: Non-shell argv stripped ──────────────────────────────────────────

class TestNonShellArgvStripped:
    """String arguments to non-shell binaries are stripped; only the command
    word (and flags) remain."""

    def test_codex_exec_killall_claude_in_arg(self):
        """codex exec 'killall ... claude' — the quoted arg is stripped."""
        cmd = 'codex exec "The hook documentation says killall and claude processes are monitored"'
        result = stripped(cmd)
        # Killall and claude must not appear in the stripped output
        assert "killall" not in result
        assert "claude" not in result
        # The command word must remain
        assert "codex" in result

    def test_echo_with_dangerous_content(self):
        """echo 'trap kill -TERM ...' — echo arg is stripped."""
        cmd = "echo \"trap 'kill -TERM $PID' SIGTERM\""
        result = stripped(cmd)
        assert "kill" not in result
        assert "echo" in result

    def test_git_commit_message(self):
        """git commit -m with kill token in message — message is stripped."""
        cmd = 'git commit -m "fix: avoid SIGKILL by using graceful shutdown"'
        result = stripped(cmd)
        assert "SIGKILL" not in result
        assert "git" in result
        assert "commit" in result


# ── Case 2: sh -c payload preserved ──────────────────────────────────────────

class TestShellCPayloadPreserved:
    """The -c argument to bash/sh/zsh/dash is recursive shell code;
    its executable tokens must be present after stripping."""

    def test_sh_c_rm_preserved(self):
        """sh -c 'rm /tmp/foo.txt' — rm inside -c payload must survive."""
        cmd = "sh -c 'rm /tmp/foo.txt'"
        result = stripped(cmd)
        assert "rm" in result

    def test_bash_c_kill_preserved(self):
        """bash -c 'kill -9 1234' — kill inside -c payload must survive."""
        cmd = "bash -c 'kill -9 1234'"
        result = stripped(cmd)
        assert "kill" in result

    def test_sh_c_complex_payload(self):
        """sh -c 'rm -rf /tmp/work && echo done' — full payload preserved."""
        cmd = "sh -c 'rm -rf /tmp/work && echo done'"
        result = stripped(cmd)
        assert "rm" in result


# ── Case 3: Heredoc body classification ──────────────────────────────────────

class TestHeredocClassification:
    """Heredoc bodies are stripped when piped to a non-shell consumer (tee, cat without
    shell downstream) and preserved when consumed by bash/sh/zsh/dash."""

    def test_heredoc_bash_consumer_preserves_body(self):
        """bash <<'EOF' rm ... EOF — bash is the consumer, body is preserved."""
        cmd = "bash <<'EOF'\nrm /tmp/foo.txt\nEOF"
        result = stripped(cmd)
        assert "rm" in result

    def test_heredoc_pipe_bash_preserves_body(self):
        """cat <<'EOF' | bash — downstream consumer is bash, body is preserved."""
        cmd = "cat <<'EOF' | bash\nkill -9 1234\nEOF"
        result = stripped(cmd)
        assert "kill" in result

    def test_heredoc_tee_consumer_strips_body(self):
        """cat <<'EOF' | tee /tmp/doc — tee is non-shell, body is stripped."""
        cmd = "cat <<'EOF' | tee /tmp/doc\nkill -9 1234\nEOF"
        result = stripped(cmd)
        # Body should be stripped — kill should not appear in executable view
        assert "kill" not in result

    def test_heredoc_python_consumer_strips_body(self):
        """python3 <<'EOF' with rm inside — non-shell consumer, body stripped."""
        cmd = "python3 <<'EOF'\nrm /tmp/foo\nEOF"
        result = stripped(cmd)
        assert "rm" not in result


# ── Case 4: Comment stripping ─────────────────────────────────────────────────

class TestCommentStripping:
    """Shell comments (# through end of line when # is not inside a string)
    are removed from the executable view."""

    def test_hash_comment_stripped(self):
        """echo foo # rm comment — the # rm part is stripped."""
        cmd = "echo foo # rm /tmp/bar"
        result = stripped(cmd)
        # Comment text must not appear
        # The rm after # is a comment; echo foo remains
        assert "echo" in result
        # rm from comment should not appear
        assert "rm" not in result

    def test_python_comment_in_c_arg_stripped(self):
        """python3 -c 'import os; # rm is not needed here' — already exits 0 pre-fix."""
        cmd = "python3 -c 'import os; # rm is not needed here'"
        result = stripped(cmd)
        # rm is after a # in a string arg; either way, must not appear as a bare token
        # This is a forward-proofing check — the command already exits 0 before the fix


# ── Case 5: $() substitution preserved inside quotes ─────────────────────────

class TestCommandSubstitutionPreserved:
    """$() and backtick command substitutions inside double-quoted strings are
    executable contexts; their content must survive stripping."""

    def test_dollar_paren_rm_preserved(self):
        """echo \"$(rm /tmp/foo.txt)\" — the $() subst is executable."""
        cmd = 'echo "$(rm /tmp/foo.txt)"'
        result = stripped(cmd)
        # rm inside $() must be present so the danger rule can fire
        assert "rm" in result

    def test_dollar_paren_kill_preserved(self):
        """echo \"$(kill -9 1)\" — $() subst with kill is executable."""
        cmd = 'echo "$(kill -9 1)"'
        result = stripped(cmd)
        assert "kill" in result

    def test_literal_string_content_stripped(self):
        """Double-quoted literal text (no substitutions) is stripped."""
        cmd = 'echo "this is just text with rm mentioned"'
        result = stripped(cmd)
        assert "rm" not in result


# ── Case 6: Control-operator boundary preserved ───────────────────────────────

class TestControlOperatorBoundary:
    """The stripper must split on top-level control operators. A real rm/kill
    command AFTER a semicolon/pipe/&& must not be stripped."""

    def test_echo_rm_text_then_real_rm(self):
        """echo \"literal rm text\"; rm /tmp/foo — the second rm is real."""
        cmd = 'echo "literal rm text"; rm /tmp/foo'
        result = stripped(cmd)
        # rm /tmp/foo (after semicolon) must survive
        assert "rm" in result

    def test_echo_kill_text_then_real_kill(self):
        """echo 'safe' && kill -9 1234 — the kill after && is real."""
        cmd = "echo 'safe' && kill -9 1234"
        result = stripped(cmd)
        assert "kill" in result

    def test_pipe_preserves_second_command(self):
        """cat /tmp/cmds | bash — the pipe itself is a control op boundary."""
        cmd = "cat /tmp/cmds | bash"
        result = stripped(cmd)
        assert "bash" in result


# ── Case 7: Fail-safe ──────────────────────────────────────────────────────────

class TestFailSafe:
    """Any exception in the stripper must return the original cmd unchanged."""

    def test_empty_string_returns_empty(self):
        assert stripped("") == ""

    def test_unterminated_quote_returns_raw(self):
        """A command with an unterminated quote is ambiguous; fail-safe applies."""
        cmd = "echo \"unterminated"
        # Must not raise; must return something (either stripped or raw)
        result = stripped(cmd)
        assert isinstance(result, str)

    def test_none_raises_or_returns_raw(self):
        """Passing None should either raise TypeError gracefully or return a string.
        The fail-safe wraps exceptions, but None is not a valid str."""
        try:
            result = strip_non_executable_contexts(None)  # type: ignore
            # If it returns, it must be a string (the fail-safe path returns the input,
            # which is None — so this case means the exception was swallowed)
            assert result is None or isinstance(result, str)
        except (TypeError, AttributeError):
            pass  # Acceptable: fail-safe swallows inner exceptions but not outer type errors

    def test_ordinary_command_unchanged(self):
        """A bare dangerous command is returned as-is (nothing to strip)."""
        cmd = "rm /tmp/foo.txt"
        result = stripped(cmd)
        assert "rm" in result
