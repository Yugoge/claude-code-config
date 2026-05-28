---
description: dev workflow, context-light invocation — same task semantics as /dev, but assumes the /dev workflow instructions are already loaded. Pass --codex to enable adversarial codex consultation on each subagent's draft; default is self-review only.
argument-hint: "[--codex] [--spec <path>] <requirement>"
disable-model-invocation: true
---

Run the **/dev** workflow with the full command specification already loaded in this conversation.

- Use the same behavior as `/dev` for the current user requirement: same argument parsing, same canonical 14-step BA → QA → Dev → QA TodoList (hook will pre-init it), same dev-registry initialization, same artifact conventions, and same gates.
- All /dev hooks remain active: subagent enforce (Gate 4), dev-registry sandboxing, canonical-todo validation, layer-escalation gate.
- Do **not** re-emit the full /dev specification — assume the workflow instructions are still in this conversation's context.
- `/redev` may reuse `/dev` workflow instructions, but MUST NOT reuse prior business task context, prior artifact paths, prior acceptance criteria, or a prior `task_id` unless the user explicitly names that task as the continuation target.

**Precondition:** the `/dev` workflow specification must still be in context (not yet evicted by SDK compaction). If you cannot recall the `/dev` step semantics from earlier turns, abort and ask the user to run `/dev` instead. This is only a prompt-size/context precondition; it is not permission to continue or infer any previous task.

**`--codex` flag passthrough**: `/redev` honors the same `--codex` flag as `/dev`. When `$ARGUMENTS` contains the literal token `--codex`, set `codex_required = true` and propagate the literal line `codex_required: true` to every BA / QA / dev dispatch prompt. When absent, default to `codex_required = false` (subagents skip codex; emit `codex_consult: { invoked: false, status: "not_requested" }`). See `commands/dev.md` Step 1 for the canonical parsing rule.

**`--no-graphify` flag passthrough**: `/redev` inherits `/dev`'s graphify dual-touchpoint integration (pre-BA Bash hydrator between Step 1 and Step 2; graphify enrichment subagent between Step 7 and Step 8). When `$ARGUMENTS` contains `--no-graphify`, pass it to the graphify-query.py Bash call. Otherwise graphify runs per the default (`CLAUDE_GRAPHIFY_ENABLED=auto`). See `commands/dev.md` for the canonical graphify integration steps.
