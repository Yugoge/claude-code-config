#!/usr/bin/env python3
"""PreToolUse hook: deny direct subagent writes to cp-state-*.json.

Cycle 2 hardening (spec-20260507-191743):
  Cycle 1 (spec-20260507-142952) shipped the structural cp-state matcher
  (`_is_cp_state_components`) and the orchestrator-bypass logic. Cycle 2
  closes 22 Bash-write bypass forms (4 codex cycle-1 reproducer + 18
  high-risk natural-shell forms across 11 verb-classes — see BA spec
  20260507-191743 AC-1+AC-2). All cycle-2 augmentation lives in this
  file (codex Q1 Option B verdict; lib/bash_write_targets.py untouched).

Threat model (per BA spec W3): cooperative-but-buggy subagent that may
naturally produce one of the listed Bash forms when manipulating a
cp-state JSON. NOT in threat model: subshell `(cd X; cmd)`, env-var
path obfuscation, `bash -c 'eval'` wrappers, named pipes, `tar -xf -C`
extraction. Adversarial defenses require a separate hardening cycle.

Behavior:
  - Orchestrator (no agent_id, no subagent_type) -> exit 0.
  - Subagent + Edit/Write/MultiEdit/NotebookEdit on cp-state path -> exit 2.
  - Subagent + Bash command writing to a cp-state-shaped path -> exit 2.

Bash extraction layers (cycle 2 additions are all in THIS file):
  L1 — shared extractor lib.bash_write_targets.extract_bash_write_paths
       returns redirect/tee/cp/mv/sed/install candidate paths (cycle 1).
  L2 — guard-local cd-context resolver: linear `cd X && cmd` /
       `cd X; cmd` / `cd X<newline>cmd` segments resolved left-to-right;
       relative paths in subsequent segments are joined against the
       post-cd cwd.
  L3 — guard-local dest-basename synthesizer for cp/mv/install/rsync/ln
       and python shutil family when dest ends `/` or os.path.isdir(dest).
  L4 — guard-local additional verb-class scanners (11 verb-classes):
       VC1 ln, VC2 python -c / heredoc body (write modes only:
       open(..., 'w'/'a'/'x'/'+...'), write_text, write_bytes,
       shutil.{copy,copy2,copyfile,move,copytree}), VC3 dd of=,
       VC4 curl -o / wget -O, VC5 &> redirect, VC6 git checkout/restore,
       VC7 touch, VC8 rsync to dir (basename synth), VC9 truncate -s
       0/-s0, VC10 bash-builtin `: > PATH` and standalone `> PATH`,
       VC11 python shutil family (folded into VC2 with dest-dir synth).

Codex cycle-2 review (transcript /var/tmp/codex-outputs/codex-output-512584-1778183870.txt)
flagged 9 issues; all 9 fixed in this revision:
  1. dd of='quoted-path' — _tokenize handles outer quotes; for `of=...`
     fused token, strip surrounding quotes from value before resolve.
  2. python heredoc `<<-TAG` — regex extended to `<<-?`.
  3. heredoc terminator on whitespace-prefixed line — for `<<TAG` use
     strict ^TAG (regex column 0); only <<-TAG allows leading tabs.
  4. shutil.copy/copy2/move to DEST_DIR — basename synthesis added.
  5. ln -sf SRC DEST_DIR/ — basename synthesis added.
  6. cp/mv/install -t DEST_DIR SRC — `-t`/`--target-directory` path
     captured and synthesis applied.
  7. cd_relative\\nprintf — newline added to segment splitter.
  8. Read-only python `open(p)` / `open(p,'r')` — only flag write modes
     ('w','a','x','+').
  9. dest-basename synthesis false-positive when dest is a non-cp-state
     FILE under specs/ — restrict synthesis to dest ending `/` OR
     os.path.isdir(resolved_dest); drop the over-aggressive fallback.

Failsafe: any unexpected exception writes diagnostic to stderr and
exits 0 to avoid bricking the tool pipeline. OUTERMOST layer.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.bash_write_targets import extract_bash_write_paths  # noqa: E402

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

_CP_STATE_GLOBS = [
    "*/.claude/specs/*/cp-state-*.json",
    "*/docs/dev/specs/*/cp-state-*.json",
    "*/dot-claude/specs/*/cp-state-*.json",
]


def _read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def _path_candidates(path: str) -> list:
    abs_p = os.path.abspath(path)
    try:
        real = os.path.realpath(path)
    except OSError:
        return [abs_p]
    if real == abs_p:
        return [abs_p]
    return [abs_p, real]


def _matches_any_glob(candidate: str) -> bool:
    return any(fnmatch.fnmatchcase(candidate, p) for p in _CP_STATE_GLOBS)


def _is_cp_state_components(candidate: str) -> bool:
    if not candidate or not isinstance(candidate, str):
        return False
    parts = candidate.rstrip("/").split("/")
    if len(parts) < 3:
        return False
    basename = parts[-1]
    if not basename.startswith("cp-state-") or not basename.endswith(".json"):
        return False
    return parts[-3] == "specs"


def _is_cp_state_path(path: str) -> bool:
    if not path:
        return False
    for c in _path_candidates(path):
        if _is_cp_state_components(c) or _matches_any_glob(c):
            return True
    return False


# ---------------------------------------------------------------------------
# Cycle-2 Bash extraction additions (M2/AC-2; 11 verb-classes / 18 forms).
# ---------------------------------------------------------------------------


def _strip_outer_quotes(s: str) -> str:
    """Strip a single matched pair of surrounding ' or " quotes."""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _mask_quotes(s: str) -> str:
    """Replace single/double-quoted spans with whitespace; preserves offsets."""
    out = list(s)
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in ("'", '"'):
            j = i + 1
            while j < n and s[j] != ch:
                j += 1
            for k in range(i, min(j + 1, n)):
                out[k] = ' '
            i = j + 1
        else:
            i += 1
    return ''.join(out)


def _tokenize(segment: str) -> list:
    """Naive shell-tokenizer: handles single/double quotes; whitespace split.

    Sufficient for cooperative-but-buggy threat model. Quoted tokens have
    their outer quotes stripped (so `of='/path'` becomes the bare token
    `of=/path`).
    """
    tokens = []
    i, n = 0, len(segment)
    while i < n:
        while i < n and segment[i].isspace():
            i += 1
        if i >= n:
            break
        # Build a single token by concatenating bare runs and quoted runs
        # until the next whitespace-or-EOF boundary. This handles fused
        # forms like `of='/path/with spaces'` -> `of=/path/with spaces`.
        start = i
        out_chars: list = []
        while i < n and not segment[i].isspace():
            ch = segment[i]
            if ch in ("'", '"'):
                quote = ch
                j = i + 1
                while j < n and segment[j] != quote:
                    out_chars.append(segment[j])
                    j += 1
                i = j + 1
            else:
                out_chars.append(ch)
                i += 1
        # If the original token started with a quote and is fully quoted
        # (no fused content), strip outer quotes was already done by
        # building from inner chars. Otherwise out_chars is the literal.
        tokens.append(''.join(out_chars) if out_chars or start != i
                      else segment[start:i])
    return tokens


# Splitter on `&&`, `||`, `;`, and newline (codex finding 7).
def _split_segments_with_seps(command: str) -> list:
    masked = _mask_quotes(command)
    segments = []
    start = 0
    i, n = 0, len(masked)
    while i < n:
        ch = masked[i]
        if i + 1 < n and ((ch == '&' and masked[i + 1] == '&')
                          or (ch == '|' and masked[i + 1] == '|')):
            segments.append(command[start:i])
            i += 2
            start = i
            continue
        if ch == ';' or ch == '\n':
            segments.append(command[start:i])
            i += 1
            start = i
            continue
        i += 1
    segments.append(command[start:])
    return [s.strip() for s in segments if s.strip()]


def _is_cd_segment(segment: str):
    tokens = _tokenize(segment)
    if not tokens or tokens[0] != "cd":
        return None
    for t in tokens[1:]:
        if not t.startswith("-"):
            return t
    return None


def _resolve_with_cwd(path_token: str, cwd: str) -> str:
    if not path_token:
        return path_token
    expanded = path_token
    for var in ("CLAUDE_PROJECT_DIR", "HOME"):
        val = os.environ.get(var)
        if val:
            expanded = expanded.replace(f"${var}", val).replace(
                f"${{{var}}}", val)
    if expanded.startswith("~/"):
        home = os.environ.get("HOME", "")
        if home:
            expanded = home + expanded[1:]
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    if cwd:
        return os.path.normpath(os.path.join(cwd, expanded))
    return expanded


# ---- Dest-basename synthesis for cp/mv/install/rsync/ln/shutil ----

def _looks_like_directory(dest_token: str, resolved_dest: str) -> bool:
    """True if dest looks like a directory destination.

    Conservative: only `dest_token endswith '/'` OR `os.path.isdir(resolved)`.
    Codex finding 9: dropped the over-aggressive `not basename starts
    cp-state-` heuristic — it false-positived on `cp src /tmp/specs/file`
    where `file` is a regular destination file.
    """
    if dest_token.endswith("/"):
        return True
    try:
        return os.path.isdir(resolved_dest)
    except OSError:
        return False


def _synthesize_dest_for_dir(srcs: list, dest_token: str, cwd: str) -> list:
    """Return [resolved_dest, *synthesized_basenames_for_each_cp_state_src].

    Synthesis runs only when dest looks like a directory (per
    `_looks_like_directory`). Each src whose basename starts `cp-state-`
    contributes a synthesized `dest/basename(src)` candidate.
    """
    resolved_dest = _resolve_with_cwd(dest_token, cwd)
    targets = [resolved_dest]
    if not _looks_like_directory(dest_token, resolved_dest):
        return targets
    for src in srcs:
        base = os.path.basename(src.rstrip("/"))
        if base.startswith("cp-state-") and base.endswith(".json"):
            synth = os.path.normpath(os.path.join(resolved_dest, base))
            targets.append(synth)
    return targets


# ---- VC1: ln -sf / ln -s ----
def _scan_ln(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if len(tokens) < 3 or tokens[0] != "ln":
        return []
    has_symlink_flag = False
    positionals = []
    for t in tokens[1:]:
        if t.startswith("--"):
            if t in ("--symbolic", "--symbolic-link"):
                has_symlink_flag = True
            continue
        if t.startswith("-") and len(t) > 1:
            if "s" in t[1:]:
                has_symlink_flag = True
            continue
        positionals.append(t)
    if not has_symlink_flag or len(positionals) < 2:
        return []
    dest = positionals[-1]
    srcs = positionals[:-1]
    # Codex finding 5: ln to dir needs basename synthesis.
    return _synthesize_dest_for_dir(srcs, dest, cwd)


# ---- VC2 + VC11: python3 -c "..." / python3 - <<HEREDOC ... ----
# Writer detection: split into "open mode-aware" vs "always-write" verbs.
# - open(...) is a writer ONLY when called with mode 'w','a','x' or '+' flag
#   (codex finding 8 — read-only open should not block).
# - write_text / write_bytes / shutil.* are always writers.
_PY_OPEN_WRITE_RE = re.compile(
    r"open\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"][^'\"]*[wax+][^'\"]*['\"]"
)
_PY_ALWAYS_WRITER_RE = re.compile(
    r"(?:write_text\b|write_bytes\b|"
    r"shutil\.(?:copy|copy2|copyfile|move|copytree)\b)"
)
_PY_PATH_RE = re.compile(
    r"""['"]([^'"]*?cp-state-[^'"]*?\.json)['"]"""
)
# Two-arg shutil call: capture src + dest path literals.
_PY_SHUTIL_CALL_RE = re.compile(
    r"shutil\.(?:copy|copy2|copyfile|move|copytree)\s*\(\s*"
    r"['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
)


def _scan_python_body(body: str, cwd: str) -> list:
    """Surface cp-state-shaped paths from a python -c arg or heredoc body.

    Conservative match: needs at least one writer marker. Always-writers
    (write_text/write_bytes/shutil.*) flag immediately. open() flagged
    only in write modes. Then quoted cp-state literals are surfaced. For
    shutil two-arg calls, the dest argument is also synthesized when it
    looks like a directory and the src basename starts cp-state-.
    """
    if not body or "cp-state-" not in body or ".json" not in body:
        # Shutil-to-dir form: src has cp-state-, dest is a dir without
        # cp-state- in its path. Detected separately below.
        if not body or "shutil." not in body:
            return []
    candidates: list = []
    has_writer = bool(_PY_OPEN_WRITE_RE.search(body)
                      or _PY_ALWAYS_WRITER_RE.search(body))
    if has_writer:
        for m in _PY_PATH_RE.finditer(body):
            candidates.append(_resolve_with_cwd(m.group(1), cwd))
    # Shutil dest-basename synthesis (codex finding 4): src basename starts
    # cp-state- and dest looks like a dir.
    for m in _PY_SHUTIL_CALL_RE.finditer(body):
        src, dest = m.group(1), m.group(2)
        candidates.extend(_synthesize_dest_for_dir([src], dest, cwd))
    return candidates


def _scan_python(segment: str, cwd: str, full_command: str) -> list:
    tokens = _tokenize(segment)
    if not tokens:
        return []
    cmd0 = tokens[0]
    if cmd0 not in ("python", "python3", "python2"):
        return []
    candidates: list = []

    # Form A: python3 -c "BODY"
    body_a = ""
    for i, t in enumerate(tokens[1:], start=1):
        if t == "-c" and i + 1 < len(tokens):
            body_a = tokens[i + 1]
            break
    candidates.extend(_scan_python_body(body_a, cwd))

    # Form B: python3 - <<TAG / <<-TAG (codex findings 2 + 3)
    if "<<" in segment:
        # Match python heredoc opener with optional `-` (tab-stripping).
        for m in re.finditer(
            r"python3?\s+-\s+<<(-?)\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?",
            full_command,
        ):
            dash = m.group(1)
            tag = m.group(2)
            body_start = full_command.find("\n", m.end())
            if body_start < 0:
                continue
            body_start += 1
            # Codex finding 3: only `<<-TAG` permits leading tabs on the
            # terminator. Plain `<<TAG` requires the terminator to start
            # in column 0 (no leading whitespace).
            if dash:
                term_re = re.compile(rf"^\t*{re.escape(tag)}\s*$",
                                     re.MULTILINE)
            else:
                term_re = re.compile(rf"^{re.escape(tag)}\s*$",
                                     re.MULTILINE)
            tm = term_re.search(full_command, pos=body_start)
            body = full_command[body_start:tm.start()] if tm else \
                full_command[body_start:]
            candidates.extend(_scan_python_body(body, cwd))

    return candidates


# ---- VC3: dd of=PATH ----
def _scan_dd(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if not tokens or tokens[0] != "dd":
        return []
    targets = []
    for t in tokens[1:]:
        if t.startswith("of="):
            # Codex finding 1: handle quoted value (e.g. `of='/path'`).
            value = _strip_outer_quotes(t[3:])
            targets.append(_resolve_with_cwd(value, cwd))
    return targets


# ---- VC4: curl -o PATH / wget -O PATH ----
def _scan_curl_wget(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if not tokens or tokens[0] not in ("curl", "wget"):
        return []
    flag = "-o" if tokens[0] == "curl" else "-O"
    long_flag = None if tokens[0] == "curl" else "--output-document"
    targets = []
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t == flag or (long_flag and t == long_flag):
            if i + 1 < len(tokens):
                targets.append(_resolve_with_cwd(tokens[i + 1], cwd))
                i += 2
                continue
        elif long_flag and t.startswith(long_flag + "="):
            targets.append(_resolve_with_cwd(t[len(long_flag) + 1:], cwd))
        elif t.startswith(flag) and len(t) > 2 and not t.startswith("--"):
            targets.append(_resolve_with_cwd(t[2:], cwd))
        i += 1
    return targets


# ---- VC5: combined-stream redirect &> / &>> ----
_AMP_REDIR_RE = re.compile(r"&>>?")


def _scan_amp_redirect(segment: str, cwd: str) -> list:
    masked = _mask_quotes(segment)
    targets = []
    for m in _AMP_REDIR_RE.finditer(masked):
        i = m.end()
        n = len(segment)
        while i < n and segment[i].isspace():
            i += 1
        if i >= n:
            continue
        if segment[i] in ("'", '"'):
            quote = segment[i]
            j = i + 1
            while j < n and segment[j] != quote:
                j += 1
            token = segment[i + 1:j]
        else:
            j = i
            while j < n and segment[j] not in " \t\n;|&<>":
                j += 1
            token = segment[i:j]
        if token:
            targets.append(_resolve_with_cwd(token, cwd))
    return targets


# ---- VC6: git checkout -- PATH / git restore PATH ----
def _scan_git(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if len(tokens) < 3 or tokens[0] != "git":
        return []
    sub = tokens[1]
    if sub == "checkout":
        if "--" not in tokens:
            return []
        idx = tokens.index("--")
        return [_resolve_with_cwd(t, cwd) for t in tokens[idx + 1:]
                if t and not t.startswith("-")]
    if sub == "restore":
        targets = []
        for t in tokens[2:]:
            if t.startswith("-"):
                continue
            targets.append(_resolve_with_cwd(t, cwd))
        return targets
    return []


# ---- VC7: touch PATH... ----
def _scan_touch(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if not tokens or tokens[0] != "touch":
        return []
    targets = []
    skip_next = False
    for t in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if t in ("-d", "--date", "-t", "-r", "--reference"):
            skip_next = True
            continue
        if t.startswith("-"):
            continue
        targets.append(_resolve_with_cwd(t, cwd))
    return targets


# ---- VC8: rsync src... DEST_DIR/ ----
def _scan_rsync(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if not tokens or tokens[0] != "rsync":
        return []
    value_flags = {"--exclude", "--include", "-e", "--rsh", "--bwlimit",
                   "--port", "--timeout"}
    positionals = []
    skip_next = False
    for t in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if t in value_flags:
            skip_next = True
            continue
        if t.startswith("-"):
            continue
        positionals.append(t)
    if len(positionals) < 2:
        return []
    dest = positionals[-1]
    srcs = positionals[:-1]
    return _synthesize_dest_for_dir(srcs, dest, cwd)


# ---- cp/mv/install with optional -t DEST_DIR (codex finding 6) ----
def _scan_cp_mv_install(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if not tokens:
        return []
    verb = tokens[0]
    if verb not in ("cp", "mv", "install"):
        return []
    value_flags = {"-m", "--mode", "-o", "--owner", "-g", "--group"}
    target_dir_flags = {"-t", "--target-directory"}
    positionals = []
    explicit_target_dir = None
    skip_next = False
    take_target = False
    for t in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if take_target:
            explicit_target_dir = t
            take_target = False
            continue
        if t in target_dir_flags:
            take_target = True
            continue
        if t.startswith("--target-directory="):
            explicit_target_dir = t.split("=", 1)[1]
            continue
        if t in value_flags:
            skip_next = True
            continue
        if t.startswith("-"):
            continue
        positionals.append(t)
    if explicit_target_dir is not None:
        # All positionals are sources; explicit target dir is the dest dir.
        # `-t`/`--target-directory` definitionally implies a directory, so
        # synthesize unconditionally (skip the on-disk isdir() heuristic).
        resolved_dir = _resolve_with_cwd(explicit_target_dir, cwd)
        synthesized = [resolved_dir]
        for src in positionals:
            base = os.path.basename(src.rstrip("/"))
            if base.startswith("cp-state-") and base.endswith(".json"):
                synthesized.append(
                    os.path.normpath(os.path.join(resolved_dir, base)))
        return synthesized
    if len(positionals) < 2:
        return []
    dest = positionals[-1]
    srcs = positionals[:-1]
    return _synthesize_dest_for_dir(srcs, dest, cwd)


# ---- VC9: truncate -s SIZE PATH / truncate -sSIZE PATH ----
def _scan_truncate(segment: str, cwd: str) -> list:
    tokens = _tokenize(segment)
    if not tokens or tokens[0] != "truncate":
        return []
    targets = []
    skip_next = False
    for t in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if t == "-s" or t == "--size":
            skip_next = True
            continue
        if t.startswith("-s") and len(t) > 2:
            continue
        if t.startswith("-"):
            continue
        targets.append(_resolve_with_cwd(t, cwd))
    return targets


# ---- VC10: bash-builtin truncating-redirect `: > PATH` / `> PATH` ----
def _scan_colon_redirect(segment: str, cwd: str) -> list:
    s = segment.lstrip()
    targets = []
    m = re.match(r":\s*>>?\s*(\S+)", s)
    if m:
        targets.append(_resolve_with_cwd(m.group(1), cwd))
        return targets
    m = re.match(r">>?\s*(\S+)", s)
    if m:
        targets.append(_resolve_with_cwd(m.group(1), cwd))
    return targets


# ---- Master Bash extraction (cycle-2 augmentation orchestrator) ----
def _extract_bash_targets(command: str) -> list:
    if not isinstance(command, str) or not command.strip():
        return []
    targets: list = []

    # (a) Shared-extractor results (cycle-1 layer).
    try:
        targets.extend(extract_bash_write_paths(command))
    except Exception:
        pass

    # (b)+(c)+(d) Per-segment cwd-aware scanners.
    cwd = ""
    for segment in _split_segments_with_seps(command):
        cd_target = _is_cd_segment(segment)
        if cd_target is not None:
            cwd = _resolve_with_cwd(cd_target, cwd) if cwd else cd_target
            if not os.path.isabs(cwd):
                cwd = os.path.abspath(cwd) if cwd else cwd
            continue

        # Re-run shared extractor on segment to surface relative paths.
        try:
            seg_paths = extract_bash_write_paths(segment)
        except Exception:
            seg_paths = []
        for p in seg_paths:
            if p and not os.path.isabs(p):
                targets.append(_resolve_with_cwd(p, cwd))
            else:
                targets.append(p)

        targets.extend(_scan_cp_mv_install(segment, cwd))
        targets.extend(_scan_ln(segment, cwd))
        targets.extend(_scan_python(segment, cwd, command))
        targets.extend(_scan_dd(segment, cwd))
        targets.extend(_scan_curl_wget(segment, cwd))
        targets.extend(_scan_amp_redirect(segment, cwd))
        targets.extend(_scan_git(segment, cwd))
        targets.extend(_scan_touch(segment, cwd))
        targets.extend(_scan_rsync(segment, cwd))
        targets.extend(_scan_truncate(segment, cwd))
        targets.extend(_scan_colon_redirect(segment, cwd))

    seen = set()
    deduped = []
    for t in targets:
        if t and t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def _extract_targets(tool_name: str, tool_input: dict) -> list:
    if not isinstance(tool_input, dict):
        return []
    if tool_name in WRITE_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        return [target] if target else []
    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        return _extract_bash_targets(command)
    return []


def _emit_block(tool_name: str, target: str) -> None:
    sys.stderr.write(
        "BLOCKED by cp-state write-guard: direct subagent writes to cp-state "
        "files are forbidden (AC-1, spec-20260507-142952; cycle-2 hardening "
        "spec-20260507-191743).\n"
        f"  tool: {tool_name}\n"
        f"  target: {target}\n"
        "spec-check.py is the only legal writer. Use one of:\n"
        "  python3 /root/.claude/scripts/spec-check.py mark "
        "--spec-id <SPEC_ID> --agent <ROLE> --agent-id <AID> --cp-id <CP>\n"
        "  python3 /root/.claude/scripts/spec-check.py waive "
        "--spec-id <SPEC_ID> --agent <ROLE> --agent-id <AID> --cp-id <CP>\n"
        "  python3 /root/.claude/scripts/spec-check.py check-in "
        "--spec-id <SPEC_ID> --agent <ROLE> --agent-id <AID>\n"
        "  python3 /root/.claude/scripts/spec-check.py check-out "
        "--spec-id <SPEC_ID> --agent <ROLE> --agent-id <AID>\n"
    )


def _check_targets(tool_name: str, targets: list) -> None:
    for target in targets:
        if _is_cp_state_path(target):
            _emit_block(tool_name, target)
            sys.exit(2)


def _is_in_scope(tool_name: str) -> bool:
    return tool_name in WRITE_TOOLS or tool_name == "Bash"


def _is_subagent(data: dict) -> bool:
    if data.get("agent_id"):
        return True
    if isinstance(data.get("subagent_type"), str) and data.get("subagent_type"):
        return True
    return False


def main() -> None:
    data = _read_payload()
    if not data:
        sys.exit(0)
    if not _is_subagent(data):
        sys.exit(0)
    tool_name = data.get("tool_name")
    if not isinstance(tool_name, str) or not _is_in_scope(tool_name):
        sys.exit(0)
    tool_input = data.get("tool_input") or {}
    targets = _extract_targets(tool_name, tool_input)
    _check_targets(tool_name, targets)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # pragma: no cover
        sys.stderr.write(f"pretool-cp-state-write-guard: unexpected ({e})\n")
        sys.exit(0)
