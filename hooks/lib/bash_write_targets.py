#!/usr/bin/env python3
"""Shared helper: parse Bash commands to extract write targets.

Provides two public functions used by tool-policy and overnight-hook-guard:

  command_without_heredoc_bodies(command) -> str
      Strip heredoc PAYLOAD lines from a shell command, keeping the
      heredoc OPENER line intact. Supports <<EOF, <<-EOF (tab-stripped),
      and <<'QUOTED' / <<"QUOTED" variants. Unclosed heredocs (no closing
      delimiter) fall back to dropping all lines after the opener.

  extract_bash_write_paths(command) -> list[str]
      Parse the heredoc-stripped command and extract every write target
      from common shell write idioms:
        - '> FILE' / '>> FILE' (redirect / append redirect)
        - 'tee FILE' / 'tee -a FILE' (tee / append-tee)
        - 'cp X DEST' / 'mv X DEST'
        - 'sed -i [PATTERN] FILE' (in-place editor)
        - 'install [-m MODE] X DEST'
        - here-string '<<<' followed by a redirect on the same line
      Resolves $HOME, ~, and $CLAUDE_PROJECT_DIR. Leaves other
      $UNRESOLVED_VAR tokens as-is. Returns absolute or workspace-
      relative path strings.

These helpers are intentionally regex-based (NOT a full shell parser).
They prioritize correctness on the patterns documented above and fail
soft on exotic syntax (compound substitutions, dynamic eval, etc.).

Doctest examples (run via `python3 -m doctest bash_write_targets.py`):

>>> command_without_heredoc_bodies('cat > /tmp/a << EOF\\nhello\\nEOF')
'cat > /tmp/a << EOF'

>>> extract_bash_write_paths('cat > /root/foo.txt << EOF\\nhello\\nEOF')
['/root/foo.txt']

>>> extract_bash_write_paths('cat > /root/a.txt << EOF\\necho > /root/b.txt\\nEOF')
['/root/a.txt']

>>> extract_bash_write_paths('tee /root/x.txt')
['/root/x.txt']

>>> extract_bash_write_paths('tee -a /root/x.txt')
['/root/x.txt']

>>> extract_bash_write_paths('cp src dest')
['dest']

>>> extract_bash_write_paths('mv src dest')
['dest']

>>> extract_bash_write_paths('sed -i s/a/b/ /root/file')
['/root/file']

>>> extract_bash_write_paths('install -m 755 src /usr/local/bin/x')
['/usr/local/bin/x']

>>> extract_bash_write_paths('echo X')
[]

>>> extract_bash_write_paths('cmd <<<"hello world" > /root/out')
['/root/out']

>>> extract_bash_write_paths('echo hello >> /var/log/app.log')
['/var/log/app.log']

>>> extract_bash_write_paths("cat <<-'END'\\n\\techo > /tmp/inside\\n\\tEND") == []
True
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

# Heredoc opener pattern. Captures three groups:
#   1: dash flag (- means tab-stripped form)
#   2: optional quote (' or ")
#   3: delimiter token
# Examples matched: '<< EOF', '<<EOF', '<<-EOF', "<<'QUOTED'", '<<"QUOTED"'
_HEREDOC_OPENER_RE = re.compile(r"<<(-?)\s*([\"'])?([A-Za-z_][A-Za-z0-9_]*)\2?")


def _detect_heredoc_opener(line: str) -> Tuple[bool, str, bool]:
    """Return (found, delimiter, dash_form) for the right-most heredoc opener."""
    matches = list(_HEREDOC_OPENER_RE.finditer(line))
    if not matches:
        return (False, "", False)
    m = matches[-1]
    return (True, m.group(3), m.group(1) == "-")


def _is_heredoc_closer(payload_line: str, delim: str, dash: bool) -> bool:
    """True if payload_line is the matching delimiter line."""
    stripped = payload_line.lstrip("\t") if dash else payload_line
    return stripped.strip() == delim


def _skip_heredoc_payload(lines: List[str], start: int, delim: str, dash: bool) -> int:
    """Advance past heredoc payload lines and the closing delimiter.

    Returns the index of the line AFTER the closing delimiter, or
    len(lines) if the heredoc is unclosed.
    """
    i = start
    while i < len(lines):
        if _is_heredoc_closer(lines[i], delim, dash):
            return i + 1
        i += 1
    return i


def command_without_heredoc_bodies(command: str) -> str:
    """Return command with heredoc payload lines stripped.

    The opener line (e.g. 'cat > FILE << EOF') is preserved so that
    write-target extraction still sees the redirect; payload lines and
    the closing delimiter line are removed.

    Multiple heredocs in a single command are handled sequentially.
    Unclosed heredocs (no matching delimiter found) drop all
    subsequent lines.
    """
    if not isinstance(command, str):
        return ""
    if "<<" not in command:
        return command
    lines = command.split("\n")
    out_lines: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out_lines.append(line)
        found, delim, dash = _detect_heredoc_opener(line)
        if not found:
            i += 1
            continue
        i = _skip_heredoc_payload(lines, i + 1, delim, dash)
    return "\n".join(out_lines)


def _resolve_path(token: str) -> str:
    """Resolve $HOME, ~, and $CLAUDE_PROJECT_DIR. Leave others as-is."""
    if not token:
        return token
    # Strip surrounding quotes if present
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        token = token[1:-1]
    # Tilde expansion
    if token.startswith("~"):
        token = os.path.expanduser(token)
    # $HOME / ${HOME}
    home = os.environ.get("HOME", "/root")
    token = token.replace("${HOME}", home).replace("$HOME", home)
    # $CLAUDE_PROJECT_DIR / ${CLAUDE_PROJECT_DIR}
    cpd = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if cpd:
        token = token.replace("${CLAUDE_PROJECT_DIR}", cpd)
        token = token.replace("$CLAUDE_PROJECT_DIR", cpd)
    return token


# Regex for redirect targets. Matches '>' or '>>' followed by optional
# whitespace and a token (path). Excludes '>&' (fd duplication like '2>&1')
# and process substitution '>(...)'. The '(?<![<>])' lookbehind prevents
# matching the '>' inside '<<'.
_REDIRECT_RE = re.compile(r"(?<![<>])(?:>>?)\s*(?![&\(])([^\s;|&<>]+)")

# tee FILE / tee -a FILE  (also -ai, --append, etc — keep simple: -a flag form)
_TEE_RE = re.compile(r"(?:^|[\s;|&])tee\b((?:\s+-[aAip]+)*)\s+([^\s;|&<>]+)")

# cp/mv: capture rest-of-segment after 'cp '/'mv '. Caller takes last
# non-flag token as DEST.
_CP_MV_RE = re.compile(r"(?:^|[\s;|&])(cp|mv)\b([^;|&\n]+)")

# sed -i [PATTERN] FILE  — '-i' may be combined with other flags. Capture
# all tokens after 'sed -i' so caller can take the last one as FILE.
_SED_I_RE = re.compile(r"(?:^|[\s;|&])sed\b([^;|&\n]*?-i[^\s;|&\n]*)([^;|&\n]+)")

# install -m MODE SRC DEST  (DEST is last positional)
_INSTALL_RE = re.compile(r"(?:^|[\s;|&])install\b([^;|&\n]+)")


def _extract_redirect_targets(command_no_heredoc: str) -> List[str]:
    """Extract '>' and '>>' redirect targets."""
    targets: List[str] = []
    for m in _REDIRECT_RE.finditer(command_no_heredoc):
        token = m.group(1).strip()
        if not token or token.isdigit():
            continue
        targets.append(_resolve_path(token))
    return targets


def _extract_tee_targets(command: str) -> List[str]:
    targets: List[str] = []
    for m in _TEE_RE.finditer(command):
        path = m.group(2).strip()
        if path:
            targets.append(_resolve_path(path))
    return targets


def _last_non_flag_token(tokens: List[str]) -> str:
    """Return the last token that does not start with '-'."""
    for t in reversed(tokens):
        if not t.startswith("-"):
            return t
    return ""


def _split_at_redirect(rest: str) -> str:
    """Truncate the segment at the first redirect operator."""
    return re.split(r"(?:>>?|<<?)", rest, maxsplit=1)[0]


def _extract_cp_mv_targets(command: str) -> List[str]:
    targets: List[str] = []
    for m in _CP_MV_RE.finditer(command):
        rest = _split_at_redirect(m.group(2).strip())
        dest = _last_non_flag_token(rest.split())
        if dest:
            targets.append(_resolve_path(dest))
    return targets


def _extract_sed_i_targets(command: str) -> List[str]:
    targets: List[str] = []
    for m in _SED_I_RE.finditer(command):
        rest = _split_at_redirect(m.group(2).strip())
        file_arg = _last_non_flag_token(rest.split())
        if file_arg:
            targets.append(_resolve_path(file_arg))
    return targets


# Flag tokens that take a separate value argument (skip next token).
_INSTALL_VALUE_FLAGS = {"-m", "--mode", "-o", "--owner", "-g", "--group"}


def _filter_install_positionals(tokens: List[str]) -> List[str]:
    """Return install command positional arguments (drop flags + flag values)."""
    cleaned: List[str] = []
    skip_next = False
    for t in tokens:
        if skip_next:
            skip_next = False
            continue
        if t in _INSTALL_VALUE_FLAGS:
            skip_next = True
            continue
        if t.startswith("-"):
            continue
        cleaned.append(t)
    return cleaned


def _extract_install_targets(command: str) -> List[str]:
    targets: List[str] = []
    for m in _INSTALL_RE.finditer(command):
        rest = _split_at_redirect(m.group(1).strip())
        positionals = _filter_install_positionals(rest.split())
        if not positionals:
            continue
        # DEST is last positional; if only one positional, install creates
        # that path (directory or file).
        targets.append(_resolve_path(positionals[-1]))
    return targets


def extract_bash_write_paths(command: str) -> List[str]:
    """Extract write-target paths from a bash command string.

    Strips heredoc bodies first, then scans for redirect targets, tee,
    cp/mv DEST, sed -i FILE, and install DEST. Returns a deduplicated
    list preserving first-seen order.
    """
    if not isinstance(command, str) or not command.strip():
        return []
    stripped = command_without_heredoc_bodies(command)
    targets: List[str] = []
    targets.extend(_extract_redirect_targets(stripped))
    targets.extend(_extract_tee_targets(stripped))
    targets.extend(_extract_cp_mv_targets(stripped))
    targets.extend(_extract_sed_i_targets(stripped))
    targets.extend(_extract_install_targets(stripped))
    # Dedupe while preserving order
    seen = set()
    deduped: List[str] = []
    for t in targets:
        if t and t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


if __name__ == "__main__":
    # Self-test entrypoint: run doctests when invoked directly.
    import doctest

    failures, _ = doctest.testmod(verbose=True)
    raise SystemExit(0 if failures == 0 else 1)
