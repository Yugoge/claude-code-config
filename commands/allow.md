---
description: Grant the main agent one-shot consent to run a developer-class bash command that would otherwise be blocked by pretool-bash-safety.sh. Usage: /allow <pattern> (literal substring match, or re:<regex> for regex).
disable-model-invocation: true
---

(hook-only command; body is not injected because of `disable-model-invocation: true`. This line exists so the body is never empty — see commands/dev-command.md for the empty-body API-400 lesson.)
