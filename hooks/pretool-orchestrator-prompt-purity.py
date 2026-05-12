#!/usr/bin/env python3
"""
PreToolUse hook: Orchestrator Prompt Purity.

Intercepts Agent tool dispatches from the main-agent (orchestrator) to
subagents and rejects dispatch prompts that prescribe HOW (tool names,
shell-command fragments, shell syntax, fenced bash blocks). Orchestrator
prompts must describe WHAT (problem, constraints, acceptance criteria)
only; subagents choose their own toolchain per their agent.md.

Behavior contract (BA spec ba-spec-redev-prompt-purity-20260426.md
section "Hook Behavior Contract"):
  - Read PreToolUse Agent payload JSON from stdin.
  - Inspect tool_input.prompt.
  - Match four blacklist categories:
      1. Tool-name prescription (use|via|invoke|call|run + ToolName + tool)
      2. Shell-command tokens with option syntax (sed/jq/curl/git/...)
      3. Shell-syntax tokens ($(...) heredoc redirection chain pipe)
      4. Fenced bash blocks (```bash / ```sh / ```shell / ```zsh)
  - On hit: exit 2 with stderr beginning
        "orchestrator must not specify HOW; rewrite prompt to describe WHAT only."
  - On miss: exit 0 silently.
  - Fail-open on parse errors / missing fields / unexpected exceptions
    so a malformed payload never blocks legitimate work.

Exemptions:
  - Subagent dispatches (data.agent_id is truthy) bypass the scan
    entirely; this hook governs orchestrator -> subagent dispatch only.
  - Content delimited by <USER_VERBATIM>...</USER_VERBATIM> markers is
    redacted before scanning so user-quoted text containing tool names
    does not trigger false positives.
  - Standard dev-registry sentinel-registration boilerplate
    ("cat > .../.claude/dev-registry/<sid>/<role>.json << 'REGEOF'") is
    stripped before scanning because it is subagent-internal scaffolding,
    not orchestrator HOW-prescription.

Exit codes:
  0  Allow (no blacklist hit, or fail-open).
  2  Block (Claude Code PreToolUse blocking convention).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


RULE_DOC_POINTER = (
    'See /root/.claude/commands/dev.md "Orchestrator Prompt Purity" section'
    ' and /root/.claude/CLAUDE.md "Orchestrator Prompt Purity" section.'
)

STDERR_HEADER = (
    "⚠ prompt-purity warning: HOW prescription detected (not blocking). Prefer describing WHAT only."
)

# PRESCRIBED_TOOL_NAMES: built-in tool names that the orchestrator must not
# prescribe imperatively in subagent dispatch prompts. The bare token "Skill"
# is intentionally OMITTED (T1.1 bugfix harness-bugfix-20260427): "Skill" is
# the meta-delegation primitive — it appears legitimately in narrative prose
# (e.g. "the Skill tool exists for delegating to other models") and in the
# orchestrator's own dev.md instructions for codex consultation. False-firing
# on bare "Skill" caused valid dispatches to be blocked. The other built-in
# tool names below remain enforced because prescribing them substitutes a
# specific HOW for the desired WHAT.
PRESCRIBED_TOOL_NAMES = (
    r"Write|Edit|Read|Bash|Glob|Grep|Agent|TodoWrite|"
    r"WebFetch|WebSearch|NotebookEdit|EnterWorktree|ExitWorktree|"
    r"AskUserQuestion|ScheduleWakeup|CronCreate|CronDelete|CronList|"
    r"TaskStop|mcp__\w+"
)

TOOL_PRESCRIPTION_PATTERNS = (
    re.compile(
        r"\b(?:Use|use|using|Using|via|Via|invoke|Invoke|call|Call|run|Run)\b"
        r"\s+(?:the\s+)?"
        r"(?:" + PRESCRIBED_TOOL_NAMES + r")\b"
        r"\s+tool\b",
    ),
    re.compile(
        r"\b(?:" + PRESCRIBED_TOOL_NAMES + r")\b\s+tool\b\s+(?:to|for)\b",
    ),
    re.compile(
        r"\(\s*not\s+(?:" + PRESCRIBED_TOOL_NAMES + r")\b",
    ),
)

SHELL_COMMANDS = (
    r"sed|awk|curl|wget|jq|yq|python3|node|npm|pip|"
    r"mkdir|chmod|chown|cp|mv|rm|ln|tar|gzip|gunzip|find|xargs|"
    r"kill|pkill|systemctl|docker|kubectl|ssh|scp|rsync"
)
SHELL_COMMAND_PATTERNS = (
    re.compile(
        r"\b(?:" + SHELL_COMMANDS + r")\b"
        r"\s+(?:-{1,2}[A-Za-z][\w-]*|<<\s*['\"]?\w+['\"]?|>>?\s*\S|2>&?\d?|\|)",
    ),
    re.compile(
        r"\bgit\s+(?:checkout|reset|revert|push|merge|rebase|cherry-pick|"
        r"stash|branch|commit|add|rm|mv|clone|fetch|pull)\b\s+\S",
    ),
)

SHELL_SYNTAX_PATTERNS = (
    re.compile(r"\$\([^)]+\)"),
    re.compile(r"<<\s*['\"]?[A-Za-z_]\w*['\"]?"),
    re.compile(r"&&\s*\S"),
    re.compile(r"\|\|\s*\S"),
    re.compile(
        r"\|\s+(?:" + SHELL_COMMANDS + r"|grep|cat|head|tail|sort|uniq|wc|tr|cut)\b",
    ),
    re.compile(r"\S\s*>{1,2}\s*[\w./~-]+"),
    re.compile(r"\S\s*2>&\d"),
)

FENCED_BASH_PATTERN = re.compile(
    r"```(?:bash|sh|shell|zsh)\b",
    re.IGNORECASE,
)
FENCED_UNTAGGED_BASH_PATTERN = re.compile(
    r"```\s*\n\s*(?:\$\s|cd\s|export\s|source\s|alias\s|cat\s|ls\s|echo\s)",
)

# Overnight-gated category: orchestrator MUST NOT dispatch <options> XML
# blocks during an active /dev-overnight session. The block prompt would
# cause the chat UI to go idle awaiting user input even though the Stop
# hook is blocking termination -- the documented Stop-continuation contract
# is overridden in practice by interrogative agent output. See BA spec
# ba-spec-stop-hook-gap-20260426-2250.md (M2 / AC2).
OPTIONS_XML_PATTERNS = (
    re.compile(r"<options>", re.IGNORECASE),
    re.compile(r"<option\s", re.IGNORECASE),
)
OPTIONS_XML_HEADER = (
    "orchestrator must not dispatch <options> blocks during overnight; "
    "choose autonomously or write a deadlock report and skip."
)
OPTIONS_XML_LABEL = "options-xml block (overnight forbids)"

# C3: daemon-restart-prescription category (TASK-ID c3-20260504-223115).
# Hard-hit pattern: an imperative restart-class verb within ~30 tokens of
# happy-daemon vocabulary OR a direct invocation of an admin-restart script.
# Hard hits → exit 2 (escalation from warn-only — see main()).
# Soft hits → exit 0 with WARN AND audit log entry.
# Subagent dispatches ALSO trigger this category (the line-315 agent_id
# exemption is removed for this category only — see _extract_prompt /
# _scan_prompt interaction below).
DAEMON_RESTART_VERB_TOKENS = (
    r"restart|reload|stop|disable|kick|cycle|bounce|kill|try-restart|"
    r"reload-or-restart|hup|HUP"
)
DAEMON_RESTART_TARGET_TOKENS = (
    r"happy-daemon(?:-(?:dev|jade|qijie))?|happy-cli\s+daemon|systemctl"
)
DAEMON_RESTART_PRESCRIPTION_PATTERNS = (
    # Pattern 1: verb within ~30 tokens of happy-daemon vocabulary
    # (verb-then-target order)
    re.compile(
        r"\b(?:" + DAEMON_RESTART_VERB_TOKENS + r")\b"
        r"(?:\W+\w+){0,30}?\W+"
        r"\b(?:" + DAEMON_RESTART_TARGET_TOKENS + r")\b",
        re.IGNORECASE,
    ),
    # Pattern 2: target-then-verb order
    re.compile(
        r"\b(?:" + DAEMON_RESTART_TARGET_TOKENS + r")\b"
        r"(?:\W+\w+){0,30}?\W+"
        r"\b(?:" + DAEMON_RESTART_VERB_TOKENS + r")\b",
        re.IGNORECASE,
    ),
    # Pattern 3: direct invocation of admin restart scripts
    re.compile(
        r"\b(?:bash\s+)?/root/bin/(?:happy-restart|safe-daemon-restart)\b",
        re.IGNORECASE,
    ),
)
DAEMON_RESTART_PRESCRIPTION_LABEL = "daemon-restart-prescription"
DAEMON_RESTART_AUDIT_LOG = os.path.expanduser(
    os.environ.get(
        "CLAUDE_DAEMON_RESTART_AUDIT_LOG",
        "~/.claude/logs/claude-daemon-restart-grants.log",
    )
)

# M8: positive-authorization-of-pollution-seeds category
# (BA spec 20260505-231740 / AC8 / W5).
# Detects orchestrator dispatch prompts that POSITIVELY authorize one of the
# pollution seed words {placeholder, TBD, stub, include later, to plan} —
# e.g. "include placeholder entries", "use TBD", "leave a stub". These seeds
# in dispatch prompts caused the B3 placeholder regression in cycle
# 20260505-123425 (orchestrator's own prompt told subagents to "include
# placeholder entries"). Hard-block at exit 2 with the standard prompt-purity
# error header. Scope is intentionally narrow: positive-authorization grammar
# in dispatch templates only, NOT a full ban on the word "placeholder" (CMD-3
# REJECTED). Negative phrasings ("never use placeholder", "do not include
# TBD", "MUST NOT leave a stub") MUST pass through.
POSITIVE_AUTHORIZATION_VERBS = (
    r"include|includes|including|use|uses|using|leave|leaves|leaving|"
    r"add|adds|adding|insert|inserts|inserting|put|puts|putting|"
    r"allow|allows|allowing|permit|permits|permitting|"
    r"keep|keeps|keeping|write|writes|writing|fill|fills|filling|"
    r"set|sets|setting|mark|marks|marking"
)
# Seed words. Note "to plan" and "include later" are multi-token; we list the
# anchor token of each multi-token seed and let the verb-prefix regex carry
# the leading verb. "include later" is matched as verb=include + seed=later;
# "to plan" is matched directly via the SEED_TOKENS alternation since the
# preceding "to" is part of the phrase rather than a separate verb.
POSITIVE_AUTHORIZATION_SEED_TOKENS = (
    r"placeholder(?:s)?|TBD|stub(?:s)?|to[- ]plan|later"
)
# Negation words that, if appearing within ~6 tokens BEFORE the verb, suppress
# the match (so "never use placeholder" / "do not include TBD" / "MUST NOT
# leave a stub" / "without TBD" pass through).
POSITIVE_AUTHORIZATION_NEGATION_LOOKBEHIND = (
    r"(?<!\bnever\s)(?<!\bnever\s\s)"
    r"(?<!\bnot\s)(?<!\bnot\s\s)"
    r"(?<!\bno\s)(?<!\bno\s\s)"
    r"(?<!\bwithout\s)(?<!\bwithout\s\s)"
    r"(?<!\bdon't\s)(?<!\bdoesn't\s)(?<!\bdidn't\s)"
    r"(?<!\bcannot\s)(?<!\bcan't\s)(?<!\bmustn't\s)"
    r"(?<!\bavoid\s)(?<!\bforbid\s)(?<!\bforbids\s)(?<!\bforbidden\s)"
)
POSITIVE_AUTHORIZATION_PATTERNS = (
    # Pattern 1: <verb> [optional article/adjective ≤2 words] <seed>
    # with negation suppression in a ~30-char lookbehind window (approximated
    # by single-token negation lookbehinds above; covers the common cases).
    re.compile(
        r"\b(?<!\bnever\s)(?<!\bnot\s)(?<!\bno\s)(?<!\bwithout\s)"
        r"(?<!\bdon't\s)(?<!\bcannot\s)(?<!\bmustn't\s)(?<!\bavoid\s)"
        r"(?<!\bforbid\s)(?<!\bforbidden\s)"
        r"(?:" + POSITIVE_AUTHORIZATION_VERBS + r")\b"
        r"(?:\s+(?:a|an|the|some|any|one|more|extra|additional|few|several))?"
        r"(?:\s+\w+){0,2}?"
        r"\s+(?:" + POSITIVE_AUTHORIZATION_SEED_TOKENS + r")\b",
        re.IGNORECASE,
    ),
    # Pattern 2: bare "to plan" / "to-plan" appearing as a positive
    # authorization phrase (e.g. "leave entries to plan" → already caught by
    # Pattern 1; "set value to plan" → also caught by Pattern 1 via "set".
    # This pattern catches phrasings where the verb is implied:
    # "field 'method': 'to plan'" — quoted authorization tokens.
    re.compile(
        r"['\"](?:to[- ]plan|TBD|placeholder|stub)['\"]",
        re.IGNORECASE,
    ),
)
POSITIVE_AUTHORIZATION_LABEL = "positive-authorization-of-pollution-seeds"

USER_VERBATIM_RE = re.compile(
    r"<USER_VERBATIM>.*?</USER_VERBATIM>",
    re.DOTALL,
)
DEV_REGISTRY_HEREDOC_RE = re.compile(
    r"cat\s*>\s*/root/\.claude/dev-registry/[^\n]*<<\s*['\"]?REGEOF['\"]?"
    r".*?\nREGEOF\b",
    re.DOTALL,
)
# Pre-redact <options>...</options> XML blocks before the generic 4-category
# scan so XML closing-tag tokens (e.g. `</options>`, `n>A`) cannot collide
# with SHELL_SYNTAX_PATTERNS' redirection regex. The OPTIONS_XML category
# scans the UN-redacted prompt separately (overnight-gated) so it can still
# fire its dedicated header when active.
OPTIONS_XML_BLOCK_RE = re.compile(
    r"<options\b[^>]*>.*?</options\s*>",
    re.IGNORECASE | re.DOTALL,
)

# T1.1 bugfix (harness-bugfix-20260427): angle-bracket documentation
# placeholders like <SPEC_ID>, <agent-name>, <cp-NN>, <role>, <N> are a
# documentation convention denoting variable names — they are NOT shell
# syntax, NOT tool prescriptions, and NOT prescriptive HOW. Redact them
# before the 4-category scan so they cannot accidentally match any pattern
# (e.g. `<x>` could collide with redirection-style heuristics). The match
# is restricted to simple identifier-shape contents (letters, digits,
# underscore, hyphen) with no whitespace or attribute syntax, so it does
# NOT match real XML elements with attributes (e.g. `<option name="a">`).
# The OPTIONS_XML category scans the UN-redacted prompt separately, so this
# redaction never weakens the overnight OPTIONS_XML enforcement (AC5).
PLACEHOLDER_TOKEN_RE = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*>")


def _redact_exempt_regions(prompt: str) -> str:
    redacted = USER_VERBATIM_RE.sub(" [USER_VERBATIM_REDACTED] ", prompt)
    redacted = DEV_REGISTRY_HEREDOC_RE.sub(
        " [DEV_REGISTRY_REGISTRATION_REDACTED] ", redacted,
    )
    redacted = OPTIONS_XML_BLOCK_RE.sub(
        " [OPTIONS_XML_BLOCK_REDACTED] ", redacted,
    )
    redacted = PLACEHOLDER_TOKEN_RE.sub(
        " [PLACEHOLDER_REDACTED] ", redacted,
    )
    return redacted


def _state_file_has_future_end_time(state_path: Path, now: datetime) -> bool:
    try:
        data = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    end_time_str = data.get("end_time")
    if not end_time_str:
        return False
    try:
        end_time = datetime.fromisoformat(end_time_str)
    except (TypeError, ValueError):
        return False
    if end_time.tzinfo is not None:
        end_time = end_time.replace(tzinfo=None)
    return end_time > now


def _overnight_active() -> bool:
    """Return True iff any .claude/overnight-state-*.json exists with a
    non-expired end_time. Fail-soft on any error.
    """
    try:
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
        claude_dir = project_dir / ".claude"
        if not claude_dir.is_dir():
            return False
        now = datetime.now()
        return any(
            _state_file_has_future_end_time(p, now)
            for p in claude_dir.glob("overnight-state-*.json")
        )
    except Exception:
        return False


def _truncate_snippet(text: str, limit: int = 80) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ")
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


def _scan_category(prompt: str, patterns, category_label: str):
    for pat in patterns:
        m = pat.search(prompt)
        if m:
            return (category_label, _truncate_snippet(m.group(0)))
    return None


def _scan_fenced_blocks(prompt: str):
    m = FENCED_BASH_PATTERN.search(prompt)
    if m:
        return ("fenced bash block (tagged)", _truncate_snippet(m.group(0)))
    m = FENCED_UNTAGGED_BASH_PATTERN.search(prompt)
    if m:
        return (
            "fenced bash block (untagged shell content)",
            _truncate_snippet(m.group(0)),
        )
    return None


def _scan_generic_categories(redacted: str):
    categories = [
        (TOOL_PRESCRIPTION_PATTERNS, "tool-name prescription"),
        (SHELL_COMMAND_PATTERNS, "shell-command token"),
        (SHELL_SYNTAX_PATTERNS, "shell-syntax token"),
    ]
    for patterns, label in categories:
        hit = _scan_category(redacted, patterns, label)
        if hit:
            return hit
    return _scan_fenced_blocks(redacted)


def _scan_prompt(prompt: str):
    # OPTIONS_XML scans the un-redacted prompt FIRST when overnight is active.
    if _overnight_active():
        hit = _scan_category(prompt, OPTIONS_XML_PATTERNS, OPTIONS_XML_LABEL)
        if hit:
            return hit
    redacted = _redact_exempt_regions(prompt)
    # C3 daemon-restart-prescription scans BEFORE generic categories so its
    # dedicated label and escalation path win.
    hit = _scan_category(
        redacted,
        DAEMON_RESTART_PRESCRIPTION_PATTERNS,
        DAEMON_RESTART_PRESCRIPTION_LABEL,
    )
    if hit:
        return hit
    # M8 positive-authorization-of-pollution-seeds scans BEFORE generic
    # categories so its dedicated hard-block path wins (BA spec
    # 20260505-231740 / AC8 / W5).
    hit = _scan_category(
        redacted,
        POSITIVE_AUTHORIZATION_PATTERNS,
        POSITIVE_AUTHORIZATION_LABEL,
    )
    if hit:
        return hit
    return _scan_generic_categories(redacted)


def _audit_daemon_restart_prescription(
    sid: str, hit_kind: str, snippet: str, exit_code: int,
) -> None:
    """Append a JSON-line audit entry per c3-20260504-223115 AC8.5."""
    try:
        log_path = DAEMON_RESTART_AUDIT_LOG
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.isdir(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        entry = {
            "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sid": sid,
            "source": "prompt-purity",
            "category": DAEMON_RESTART_PRESCRIPTION_LABEL,
            "hit_kind": hit_kind,
            "snippet": (snippet or "")[:200],
            "exit_code": exit_code,
        }
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
        try:
            os.chmod(log_path, 0o644)
        except OSError:
            pass
    except Exception:
        # Audit-log failure must never break the hook.
        pass


_OPTIONS_XML_REMEDY = (
    "describe the work autonomously: pick one path,\n"
    "            execute it, or write docs/dev/overnight-deadlock-<ts>.md\n"
    "            and skip to the next pipeline. Defer all user-input\n"
    "            questions to the end-of-overnight summary."
)
_DAEMON_RESTART_HEADER = (
    "BLOCKED: daemon-restart-prompt — Agent prompt prescribes a "
    "happy-daemon-* restart (per c3-20260504-223115)."
)
_DAEMON_RESTART_REMEDY = (
    "do NOT instruct any subagent to restart, reload, stop, kill,\n"
    "            disable, or otherwise disrupt happy-daemon-*. Only the\n"
    "            user may run /root/bin/claude-allow-restart from a TTY."
)
_GENERIC_REMEDY = (
    "describe the desired end-state (problem, constraints,\n"
    "            acceptance criteria) and let the subagent select its\n"
    "            own tool per its agent.md."
)
# M8: hard-block header reuses the standard prompt-purity error substring
# `orchestrator must not specify HOW; rewrite prompt to describe WHAT only.`
# (per AC8 self-test contract — the canonical phrase QA greps for).
_POSITIVE_AUTHORIZATION_HEADER = (
    "BLOCKED: orchestrator must not specify HOW; rewrite prompt to "
    "describe WHAT only. Positive authorization of pollution seeds "
    "(placeholder/TBD/stub/include later/to plan) detected in dispatch "
    "prompt — these seeds caused the B3 placeholder regression in cycle "
    "20260505-123425. (BA spec 20260505-231740 / AC8 / M8.)"
)
_POSITIVE_AUTHORIZATION_REMEDY = (
    "describe what the subagent should produce in concrete terms\n"
    "            (real POI names / real values / actual content). If a\n"
    "            field is unknown, instruct the subagent to research or\n"
    "            mark it as a research blocker — never authorize a\n"
    "            placeholder/TBD/stub/to-plan/include-later token in the\n"
    "            data itself."
)


def _header_remedy_for(category: str):
    if category == OPTIONS_XML_LABEL:
        return OPTIONS_XML_HEADER, _OPTIONS_XML_REMEDY
    if category == DAEMON_RESTART_PRESCRIPTION_LABEL:
        return _DAEMON_RESTART_HEADER, _DAEMON_RESTART_REMEDY
    if category == POSITIVE_AUTHORIZATION_LABEL:
        return _POSITIVE_AUTHORIZATION_HEADER, _POSITIVE_AUTHORIZATION_REMEDY
    return STDERR_HEADER, _GENERIC_REMEDY


def _emit_block(category: str, snippet: str) -> None:
    header, remedy = _header_remedy_for(category)
    msg = (
        f"{header}\n"
        f"  category: {category}\n"
        f'  snippet:  "{snippet}"\n'
        f"  rule:     {RULE_DOC_POINTER}\n"
        f"  remedy:   {remedy}\n"
    )
    sys.stderr.write(msg)
    sys.stderr.flush()


def _parse_payload():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return None
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return None


def _extract_prompt(data: dict):
    # Per c3-20260504-223115 AC8 (subagent exemption removed for the
    # daemon-restart-prescription category only): we do NOT early-return on
    # agent_id here. Instead, main() filters out subagent hits AFTER scanning,
    # preserving subagent-exempt behavior for all other categories.
    tool_name = data.get("tool_name") or data.get("toolName") or ""
    if tool_name and tool_name != "Agent":
        return None
    tool_input = data.get("tool_input") or data.get("toolInput") or {}
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return None
    return prompt


def _resolve_session_id(data: dict) -> str:
    return (
        data.get("session_id")
        or data.get("sessionId")
        or os.environ.get("CLAUDE_SESSION_ID", "")
        or "unknown"
    )


def _route_hit(category: str, snippet: str, is_subagent: bool, sid: str) -> int:
    """Route a scan hit to its appropriate exit code per category contract.

    Categories:
      - DAEMON_RESTART_PRESCRIPTION_LABEL: hard-block exit 2; applies to
        subagents AS WELL (c3-20260504-223115).
      - POSITIVE_AUTHORIZATION_LABEL: hard-block exit 2; orchestrator only
        (BA spec 20260505-231740 / AC8 / W5 / M8).
      - All other categories: orchestrator-only, warn-only exit 0;
        subagent hits exit 0 silently with no emission.
    """
    if category == DAEMON_RESTART_PRESCRIPTION_LABEL:
        _emit_block(category, snippet)
        _audit_daemon_restart_prescription(sid, "hard", snippet, 2)
        return 2
    if is_subagent:
        return 0
    if category == POSITIVE_AUTHORIZATION_LABEL:
        _emit_block(category, snippet)
        return 2
    _emit_block(category, snippet)
    return 0


def main() -> int:
    data = _parse_payload()
    if data is None:
        return 0
    prompt = _extract_prompt(data)
    if prompt is None:
        return 0
    hit = _scan_prompt(prompt)
    if hit is None:
        return 0
    category, snippet = hit
    is_subagent = bool(data.get("agent_id"))
    sid = _resolve_session_id(data)
    return _route_hit(category, snippet, is_subagent, sid)


if __name__ == "__main__":
    sys.exit(main())
