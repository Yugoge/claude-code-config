---
description: Allow main agent to bypass orchestrator-gate restrictions for this turn (subagent-only operations become directly allowed). Auto-clears at stop.
disable-model-invocation: true
---

(hook-only command; body is not injected because of `disable-model-invocation: true`. This line exists so the body is never empty — see commands/dev-command.md for the empty-body API-400 lesson.)

## Closing /do-developed work

`/do` only writes `/tmp/claude-orchestrator-consent-<session-id>.flag`; it does not create any dev cycle artifacts (no context, dev-report, qa-report, or completion). The `/close` normal path requires the full `/dev` artifact chain and will fail without it.

**Escape hatch**: use the forced-path form of `/close`:

```
/close docs/dev/ticket-<task-id>.md --force --reason "developed with /do"
```

The explicit path form (`docs/dev/ticket-<task-id>.md`) is always safe — path-form resolution only verifies the named file exists, not `qa-report`. Bare timestamp form (`/close <task-id> --force`) also works after the forced-path qa-report skip fix (AC1 of ticket 20260517-155838).

If no ticket file exists (you bypassed BA entirely), create a minimal ticket file first (e.g. `docs/dev/ticket-<task-id>.md`) and then use the path form above.

After a successful forced close, follow up with:

```
/commit <task-id> -m "<summary>"
```
