"""Regression test for commit.sh maybe_add_path() dotfile-path bug.

Bug surfaced cycle 20260511-100000: dev-report listed 6 `.claude/commands/*`
files in `files_modified`, but commit a46dc0ec silently dropped all of them.
Root cause was `value.strip().strip("`'\".,;)")` at commit.sh:567 — Python's
str.strip(chars) treats the argument as a character class and reads from BOTH
ends, so the leading '.' of dotfile paths was eaten. The mutated path then
failed the `path in planned` check in the ownership classifier, falling
through to "unrelated".

Fix: drop '.' from the strip character set.

This test extracts the strip behavior from commit.sh:567 and asserts:
  (a) dotfile paths survive untouched (.claude/, .github/, .gitignore, etc.)
  (b) wrapping punctuation is still stripped (backticks, quotes, commas, parens)
  (c) the fix did not regress on existing semantics
"""

import re
import subprocess
from pathlib import Path


_HOOK = Path(__file__).resolve().parent.parent / "commit.sh"
# Match the literal: cleaned = value.strip().strip("...") — the inner string
# may contain backslash-escaped double-quotes (\"), so we accept either
# non-quote chars OR \"-escapes.
_LINE_PATTERN = re.compile(
    r'cleaned\s*=\s*value\.strip\(\)\.strip\("((?:[^"\\]|\\.)+)"\)'
)


def _extract_strip_chars() -> str:
    """Read commit.sh and pull the exact characters fed to the strip call."""
    src = _HOOK.read_text()
    m = _LINE_PATTERN.search(src)
    assert m, "commit.sh maybe_add_path strip call not found — refactor broke this test"
    # m.group(1) is the literal between the outer quotes. Python's
    # str.strip(chars) receives this verbatim, so re-interpret the Python
    # escape sequences (\" -> ", \\ -> \, \n -> newline, etc.).
    return m.group(1).encode().decode("unicode_escape")


def _run(value: str) -> str:
    chars = _extract_strip_chars()
    return value.strip().strip(chars)


def test_dotfile_paths_preserved():
    """The whole point of the fix: .claude/, .github/, .gitignore survive."""
    assert _run(".claude/commands/equity-research.md") == ".claude/commands/equity-research.md"
    assert _run(".github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert _run(".gitignore") == ".gitignore"
    assert _run(".dockerignore") == ".dockerignore"
    assert _run(".envrc") == ".envrc"


def test_regular_paths_unchanged():
    assert _run("scripts/utilities/foo.py") == "scripts/utilities/foo.py"
    assert _run("tests/unit/test_x.py") == "tests/unit/test_x.py"
    assert _run("docs/dev/ticket-20260511-100000.md") == "docs/dev/ticket-20260511-100000.md"


def test_wrapping_punctuation_still_stripped():
    """The strip set MUST still remove wrapping characters from prose excerpts."""
    assert _run("`backtick.md`") == "backtick.md"
    assert _run('"quoted.py"') == "quoted.py"
    assert _run("'apostrophe.json'") == "apostrophe.json"
    assert _run("comma,") == "comma"
    assert _run("semicolon;") == "semicolon"
    # Note: the strip set has ')' but not '(' (matches pre-fix behavior;
    # one-sided punctuation in prose excerpts is intentional).
    assert _run("(parens)") == "(parens"


def test_strip_does_not_contain_dot():
    """Direct invariant: the strip character class MUST NOT include '.'."""
    chars = _extract_strip_chars()
    assert "." not in chars, (
        f"commit.sh strip set still includes '.': {chars!r}. "
        "Dotfile paths (.claude/, .github/, .gitignore) will be silently mangled."
    )


if __name__ == "__main__":
    test_dotfile_paths_preserved()
    test_regular_paths_unchanged()
    test_wrapping_punctuation_still_stripped()
    test_strip_does_not_contain_dot()
    print("✅ All 4 commit.sh dotfile-strip regression tests passed.")
