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
import re
import sys


RULE_DOC_POINTER = (
    'See /root/.claude/commands/dev.md "Orchestrator Prompt Purity" section'
    ' and /root/.claude/CLAUDE.md "Orchestrator Prompt Purity" section.'
)

STDERR_HEADER = (
    "orchestrator must not specify HOW; rewrite prompt to describe WHAT only."
)

PRESCRIBED_TOOL_NAMES = (
    r"Write|Edit|Read|Bash|Glob|Grep|Skill|Agent|TodoWrite|"
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

USER_VERBATIM_RE = re.compile(
    r"<USER_VERBATIM>.*?</USER_VERBATIM>",
    re.DOTALL,
)
DEV_REGISTRY_HEREDOC_RE = re.compile(
    r"cat\s*>\s*/root/\.claude/dev-registry/[^\n]*<<\s*['\"]?REGEOF['\"]?"
    r".*?\nREGEOF\b",
    re.DOTALL,
)


def _redact_exempt_regions(prompt: str) -> str:
    redacted = USER_VERBATIM_RE.sub(" [USER_VERBATIM_REDACTED] ", prompt)
    redacted = DEV_REGISTRY_HEREDOC_RE.sub(
        " [DEV_REGISTRY_REGISTRATION_REDACTED] ", redacted,
    )
    return redacted


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


def _scan_prompt(prompt: str):
    redacted = _redact_exempt_regions(prompt)
    for patterns, label in (
        (TOOL_PRESCRIPTION_PATTERNS, "tool-name prescription"),
        (SHELL_COMMAND_PATTERNS, "shell-command token"),
        (SHELL_SYNTAX_PATTERNS, "shell-syntax token"),
    ):
        hit = _scan_category(redacted, patterns, label)
        if hit:
            return hit
    return _scan_fenced_blocks(redacted)


def _emit_block(category: str, snippet: str) -> None:
    msg = (
        f"{STDERR_HEADER}\n"
        f"  category: {category}\n"
        f'  snippet:  "{snippet}"\n'
        f"  rule:     {RULE_DOC_POINTER}\n"
        f"  remedy:   describe the desired end-state (problem, constraints,\n"
        f"            acceptance criteria) and let the subagent select its\n"
        f"            own tool per its agent.md.\n"
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
    if data.get("agent_id"):
        return None
    tool_name = data.get("tool_name") or data.get("toolName") or ""
    if tool_name and tool_name != "Agent":
        return None
    tool_input = data.get("tool_input") or data.get("toolInput") or {}
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return None
    return prompt


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
    _emit_block(category, snippet)
    return 2


if __name__ == "__main__":
    sys.exit(main())
