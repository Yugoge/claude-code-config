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

Bare timestamp form works in all cases — the forced path skips ALL file existence checks (no ticket, no qa-report required):

```
/close <task-id> --force --reason "developed with /do"
```

After a successful forced close, follow up with:

```
/commit <task-id> -m "<summary>"
```
