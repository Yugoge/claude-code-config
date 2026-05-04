---
description: dev workflow, skip prompt injection — for re-invocation with /dev context already loaded
disable-model-invocation: true
---

Resume the **/dev** workflow that is already loaded in this session.

- Reuse the canonical 14-step BA → QA → Dev → QA TodoList (hook will pre-init it).
- All /dev hooks remain active: subagent enforce (Gate 4), dev-registry sandboxing, canonical-todo validation, layer-escalation gate.
- Do **not** re-emit the full /dev specification — assume it is still in this conversation's context.

**Precondition:** `/dev` must have run in this same session and its spec must still be in context (not yet evicted by SDK compaction). If you cannot recall the /dev step semantics from earlier turns, abort and ask the user to run `/dev` instead. Guessing step intent from todo names alone causes wrong subagent picks, wrong artefact paths, and skipped gates.

**`--codex` flag passthrough**: `/redev` honors the same `--codex` flag as `/dev`. When `$ARGUMENTS` contains the literal token `--codex`, set `codex_required = true` and propagate the literal line `codex_required: true` to every BA / QA / dev dispatch prompt. When absent, default to `codex_required = false` (subagents skip codex; emit `codex_consult: { invoked: false, status: "not_requested" }`). See `commands/dev.md` Step 1 for the canonical parsing rule.
