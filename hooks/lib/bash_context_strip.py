"""bash_context_strip.py — strip non-executable string contexts from shell commands.

Purpose: enable danger-token safety rules to ignore tokens that appear inside
quoted string arguments to non-shell commands (e.g. `codex exec "killall claude"`
should NOT match `(killall|pkill).*claude` because "killall" is inside a string
passed to a non-shell binary).

Public API:
    strip_non_executable_contexts(cmd: str) -> str

Fail-safe contract (M10): any exception or ambiguity returns the raw cmd unchanged,
so the safety hook errs on the side of blocking rather than permitting.

stdlib only — no bashlex, no non-stdlib packages.
"""

import re
import sys

# Commands treated as shell interpreters (whose arguments are themselves shell code)
_SHELL_INTERPS = frozenset({"bash", "sh", "zsh", "dash", "exec", "eval"})

# Prefixes that appear before the actual command word but are not the command itself
_WRAPPER_PREFIXES = frozenset({"env", "time", "sudo", "nice", "ionice", "nohup",
                                "strace", "ltrace", "timeout", "doas", "run0"})


def strip_non_executable_contexts(cmd: str) -> str:
    """Return cmd with non-executable string-content contexts removed.

    Four layered passes:
      Pass 1 — split on top-level control operators and process each segment
      Pass 2 — within each segment, strip string args to non-shell commands
      Pass 3 — heredoc classification (shell-consuming vs data heredocs)
      Pass 4 note — the kill-signal word-boundary tightening is done in the
                    bash hook pattern, not here.

    Fail-safe: any exception returns raw cmd.
    """
    try:
        return _process_compound(cmd)
    except Exception:
        return cmd


def _process_compound(cmd: str) -> str:
    """Process a full compound command (may contain heredocs and control ops)."""
    # Pass 3: handle heredoc body stripping first (operates on full command)
    cmd = _process_heredocs(cmd)
    # Pass 1+2: split on top-level control operators and process each segment
    parts = _split_top_level(cmd)
    result_parts = []
    for sep, segment in parts:
        processed = _strip_segment_args(segment)
        result_parts.append(sep + processed)
    return "".join(result_parts)


# ── Pass 1: top-level splitting ───────────────────────────────────────────────

def _split_top_level(cmd: str) -> list:
    """Split cmd on top-level control operators (;, &&, ||, |, newlines).

    Returns list of (separator, segment) tuples. The first segment has separator="".
    Quotes, $() and backticks are respected — operators inside them are not split points.
    """
    parts = []
    current = []
    sep_buf = ""
    i = 0
    n = len(cmd)

    while i < n:
        ch = cmd[i]

        # Skip quoted regions
        if ch in ('"', "'", "`"):
            span, end_i = _consume_quoted(cmd, i)
            current.append(span)
            i = end_i
            continue

        # Skip $( ... ) command substitutions
        if ch == '$' and i + 1 < n and cmd[i+1] == '(':
            span, end_i = _consume_paren_subst(cmd, i + 1)
            current.append('$' + span)
            i = end_i
            continue

        # Control operators
        if cmd[i:i+2] in ("&&", "||"):
            parts.append((sep_buf, "".join(current)))
            sep_buf = cmd[i:i+2]
            current = []
            i += 2
            continue

        if ch == '|':
            # Single pipe (not ||)
            parts.append((sep_buf, "".join(current)))
            sep_buf = "|"
            current = []
            i += 1
            continue

        if ch == ';':
            parts.append((sep_buf, "".join(current)))
            sep_buf = ";"
            current = []
            i += 1
            continue

        if ch == '\n':
            parts.append((sep_buf, "".join(current)))
            sep_buf = "\n"
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    parts.append((sep_buf, "".join(current)))
    return parts


# ── Pass 2: per-segment argument stripping ────────────────────────────────────

def _strip_segment_args(segment: str) -> str:
    """Within a single segment (no top-level control operators), strip quoted
    string args to non-shell commands. Preserve $() and backtick spans by
    recursively processing them as executable contexts."""
    segment = segment.strip()
    if not segment:
        return segment

    # Tokenize the segment into (token_text, token_type) pairs
    # token_type: 'word' | 'quoted' | 'subst' | 'space' | 'comment'
    tokens = _tokenize_segment(segment)
    if not tokens:
        return segment

    # Find the actual command word (skip wrappers like env VAR=val, sudo, time, etc.)
    cmd_word_idx = _find_command_word_idx(tokens)
    if cmd_word_idx is None:
        return segment

    cmd_word = tokens[cmd_word_idx][0].strip()

    # Determine if this command is a shell interpreter
    is_shell = cmd_word in _SHELL_INTERPS

    if is_shell:
        # For shell interpreters: look for -c flag; extract payload and recurse
        return _handle_shell_interp(tokens, cmd_word_idx)
    else:
        # For non-shell commands: strip quoted string arguments past the command word
        # but preserve $() and backtick substitutions (recursively process)
        return _strip_non_shell_quoted_args(tokens, cmd_word_idx)


def _tokenize_segment(segment: str) -> list:
    """Tokenize a segment into (text, type) pairs.
    Types: 'word', 'single_quoted', 'double_quoted', 'backtick', 'subst', 'space', 'comment'
    """
    tokens = []
    i = 0
    n = len(segment)

    while i < n:
        ch = segment[i]

        if ch == ' ' or ch == '\t':
            # Collect whitespace
            j = i
            while j < n and segment[j] in (' ', '\t'):
                j += 1
            tokens.append((segment[i:j], 'space'))
            i = j
            continue

        if ch == '#':
            # Shell comment: rest of line is non-executable
            tokens.append((segment[i:], 'comment'))
            break

        if ch == "'":
            span, end_i = _consume_quoted(segment, i)
            tokens.append((span, 'single_quoted'))
            i = end_i
            continue

        if ch == '"':
            span, end_i = _consume_quoted(segment, i)
            tokens.append((span, 'double_quoted'))
            i = end_i
            continue

        if ch == '`':
            span, end_i = _consume_quoted(segment, i)
            tokens.append((span, 'backtick'))
            i = end_i
            continue

        if ch == '$' and i + 1 < n and segment[i+1] == '(':
            span, end_i = _consume_paren_subst(segment, i + 1)
            tokens.append(('$' + span, 'subst'))
            i = end_i
            continue

        # Regular word character
        j = i
        while j < n and segment[j] not in (' ', '\t', "'", '"', '`', '#', '$', '\n'):
            if segment[j] == '$' and j + 1 < n and segment[j+1] == '(':
                break
            j += 1
        tokens.append((segment[i:j], 'word'))
        i = j

    return tokens


def _find_command_word_idx(tokens: list) -> int | None:
    """Find the index of the actual command word, skipping wrapper prefixes and VAR=val."""
    for idx, (text, ttype) in enumerate(tokens):
        if ttype == 'space':
            continue
        if ttype != 'word':
            return idx  # quoted or subst as first token — treat as command word
        word = text.strip()
        if not word:
            continue
        # Skip VAR=val assignments
        if re.match(r'^[A-Z_][A-Z_0-9]*=', word):
            continue
        # Skip wrapper prefixes
        if word in _WRAPPER_PREFIXES:
            continue
        return idx
    return None


def _handle_shell_interp(tokens: list, cmd_idx: int) -> str:
    """Handle shell interpreter commands: find -c flag and recursively strip payload."""
    # Look for -c flag after the command word
    i = cmd_idx + 1
    result_tokens = tokens[:i]

    while i < len(tokens):
        text, ttype = tokens[i]
        if ttype == 'space':
            result_tokens.append(tokens[i])
            i += 1
            continue
        if ttype == 'word' and text.strip() == '-c':
            result_tokens.append(tokens[i])
            i += 1
            # Next non-space token is the -c payload
            while i < len(tokens) and tokens[i][1] == 'space':
                result_tokens.append(tokens[i])
                i += 1
            if i < len(tokens):
                payload_text, payload_type = tokens[i]
                # Unwrap quotes from payload
                if payload_type in ('single_quoted', 'double_quoted'):
                    inner = payload_text[1:-1]  # strip surrounding quotes
                    processed = strip_non_executable_contexts(inner)
                    # Re-wrap in same quote style
                    quote_char = payload_text[0]
                    result_tokens.append((quote_char + processed + quote_char, payload_type))
                else:
                    result_tokens.append(tokens[i])
                i += 1
            # Remaining tokens: keep as-is (they are args to the shell process, not to -c)
            result_tokens.extend(tokens[i:])
            break
        else:
            result_tokens.append(tokens[i])
        i += 1
    else:
        result_tokens = tokens  # No -c found, keep everything

    return "".join(t[0] for t in result_tokens)


def _strip_non_shell_quoted_args(tokens: list, cmd_idx: int) -> str:
    """For non-shell commands: replace quoted string arg tokens with empty string.
    Preserve $() substitutions (recursively processed) and backtick spans.
    Keep all tokens up to and including the command word unchanged.
    """
    result = []
    for i, (text, ttype) in enumerate(tokens):
        if i <= cmd_idx:
            result.append(text)
            continue
        if ttype == 'single_quoted':
            # Non-executable string arg — replace with empty (preserve surrounding space)
            result.append('')
        elif ttype == 'double_quoted':
            # Strip text but recursively process any $() inside
            stripped = _strip_double_quoted_content(text)
            result.append(stripped)
        elif ttype == 'backtick':
            # Backtick subst is executable — recursively process its body
            inner = text[1:-1]
            processed = strip_non_executable_contexts(inner)
            result.append('`' + processed + '`')
        elif ttype == 'subst':
            # $() is executable — recursively process its body
            inner = text[2:-1]  # strip $( and )
            processed = strip_non_executable_contexts(inner)
            result.append('$(' + processed + ')')
        elif ttype == 'comment':
            # Strip comments — non-executable
            result.append('')
        else:
            result.append(text)
    return "".join(result)


def _strip_double_quoted_content(text: str) -> str:
    """Strip content of a double-quoted string but preserve $() substitutions inside."""
    # text includes the surrounding double quotes
    inner = text[1:-1]
    # Extract only $( ... ) substs — strip everything else
    result = []
    i = 0
    while i < len(inner):
        if inner[i] == '$' and i + 1 < len(inner) and inner[i+1] == '(':
            span, end_i = _consume_paren_subst(inner, i + 1)
            body = span[1:-1]  # strip ( and )
            processed = strip_non_executable_contexts(body)
            result.append('$(' + processed + ')')
            i = end_i
        else:
            i += 1
    return '"' + "".join(result) + '"'


# ── Pass 3: heredoc classification ───────────────────────────────────────────

# Shell-consuming consumers: when heredoc is fed to these, body is executable
_SHELL_CONSUMERS_RE = re.compile(
    r'(?:bash|sh|zsh|dash|eval)\b', re.IGNORECASE
)

# Non-shell consumers where body should be stripped
_NONSHELL_CONSUMERS_RE = re.compile(
    r'(?:python3?|ruby|node|perl|tee|cat|grep|sed|awk)\b', re.IGNORECASE
)

# Heredoc opener pattern
_HEREDOC_RE = re.compile(
    r'<<-?([\'"]?)(\w+)\1',
)


def _process_heredocs(cmd: str) -> str:
    """Classify heredoc bodies as executable or data, and strip data bodies.

    Rules:
    - bash|sh|zsh|dash|eval << ... : body is executable, preserve
    - python3|ruby|node|perl << ... : body is non-shell, strip
    - cat << ... | bash : shell context downstream, preserve
    - cat << ... (no shell downstream): data context, strip
    - Any ambiguity/error: preserve raw (fail-safe)
    """
    if '<<' not in cmd:
        return cmd

    try:
        return _do_heredoc_strip(cmd)
    except Exception:
        return cmd


def _do_heredoc_strip(cmd: str) -> str:
    """Perform heredoc stripping. Called only when '<<' present."""
    lines = cmd.split('\n')
    result_lines = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        m = _HEREDOC_RE.search(line)
        if not m:
            result_lines.append(line)
            i += 1
            continue

        delimiter = m.group(2)
        # Determine the consumer: look at text before the << on this line
        before_heredoc = line[:m.start()].strip()
        cmd_word_match = re.match(r'\S+', before_heredoc)
        consumer = cmd_word_match.group(0).split('/')[-1] if cmd_word_match else ''

        # Determine if shell-consuming context
        is_shell_ctx = False
        if _SHELL_CONSUMERS_RE.search(consumer):
            is_shell_ctx = True
        elif consumer in ('cat', ''):
            # Check for downstream pipe to shell on same line or next line
            after_heredoc = line[m.end():]
            rest_of_cmd = after_heredoc + '\n' + '\n'.join(lines[i+1:])
            # Look for the closing delimiter first, then check for | bash after it
            is_shell_ctx = _has_shell_pipe_after_heredoc(rest_of_cmd, delimiter)

        # Collect heredoc body
        result_lines.append(line)
        i += 1
        body_lines = []
        while i < n:
            stripped = lines[i].lstrip()
            if stripped == delimiter or lines[i].strip() == delimiter:
                break
            body_lines.append(lines[i])
            i += 1

        if is_shell_ctx:
            # Preserve body (executable shell code)
            result_lines.extend(body_lines)
        else:
            # Strip body (data/non-shell context)
            # Replace each line with empty to preserve line count for error messages
            result_lines.extend('' for _ in body_lines)

        # Add closing delimiter if present
        if i < n:
            result_lines.append(lines[i])
            i += 1

    return '\n'.join(result_lines)


def _has_shell_pipe_after_heredoc(text: str, delimiter: str) -> bool:
    """Check if there's a | bash/sh downstream after the heredoc closing delimiter."""
    lines = text.split('\n')
    past_delimiter = False
    for line in lines:
        stripped = line.strip()
        if not past_delimiter:
            if stripped == delimiter:
                past_delimiter = True
            continue
        if re.search(r'\|\s*(bash|sh|zsh|dash)\b', stripped):
            return True
        if stripped:  # non-empty line after delimiter that isn't a pipe to shell
            return False
    return False


# ── Quoted-span consumers ─────────────────────────────────────────────────────

def _consume_quoted(text: str, start: int) -> tuple:
    """Consume a quoted span (single, double, or backtick) starting at text[start].
    Returns (span, next_index).
    """
    quote = text[start]
    i = start + 1
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '\\' and quote != "'":
            i += 2  # skip escaped char
            continue
        if ch == quote:
            return text[start:i+1], i + 1
        i += 1
    # Unterminated quote — return rest
    return text[start:], n


def _consume_paren_subst(text: str, start: int) -> tuple:
    """Consume a $(...) or (...) span starting at text[start] (which is the '(').
    Returns (span_including_parens, next_index).
    """
    depth = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'", '`'):
            span, i = _consume_quoted(text, i)
            continue
        if ch == '(':
            depth += 1
            i += 1
        elif ch == ')':
            depth -= 1
            i += 1
            if depth == 0:
                return text[start:i], i
        else:
            i += 1
    return text[start:], n
