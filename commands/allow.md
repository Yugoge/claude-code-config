---
description: Single-use break-glass — bypass all safety blocks for the next matching bash command this turn. /allow = anything; /allow --tool <pattern> = explicit pattern (regex auto-detected). Trailing tokens become an audit-log comment. Auto-expires at stop.
disable-model-invocation: true
---

(hook-only command; body is not injected because of `disable-model-invocation: true`. This line exists so the body is never empty — see commands/dev-command.md for the empty-body API-400 lesson.)
