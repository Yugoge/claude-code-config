---
description: Allow main agent to bypass orchestrator-gate restrictions for this turn (subagent-only operations become directly allowed). Auto-clears at stop.
disable-model-invocation: true
---

(hook-only: `disable-model-invocation: true` suppresses a standalone AI turn, but the body IS injected into context. This line exists so the body is never empty — see commands/dev-command.md for the empty-body API-400 lesson.)

## --codex flag

If `$ARGUMENTS` starts with `--codex`, strip the flag and treat the remainder as the task prompt:

```
TASK = $ARGUMENTS with "--codex" prefix removed (trimmed)
```

Invoke `Skill(name: "codex", args: TASK)`. After codex completes, write the do-report and `/close` as normal.

If `$ARGUMENTS` is exactly `--codex` with no further text, ask the user for the task prompt before proceeding.

## Before /close: write do-report

Before invoking `/close`, the agent MUST write `docs/dev/do-report-<session-id>.json`. The session-id comes from the consent flag `/tmp/claude-orchestrator-consent-<session-id>.flag`. Use the same timestamp as the task-id so `/close <session-id>` resolves it.

```json
{
  "task_id": "<session-id>",
  "request_id": "<session-id>",
  "source": "do",
  "request": "<original /do args verbatim>",
  "do": {
    "status": "completed",
    "summary": "<1-2 sentence description of what was accomplished>",
    "files_modified": ["<file1>", "<file2>"],
    "files_created": []
  }
}
```

`files_modified` and `files_created` MUST be filled by the agent from its own knowledge of what it changed — NOT derived from `git diff` (git diff is session-unaware and breaks under parallel /do sessions).

Then: `/close <session-id>` runs the normal QA path using the do-report as the source artifact. `--force` is no longer required.
