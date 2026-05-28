# Graphify Knowledge Graph Integration

**Spec**: docs/dev/specs/spec-20260527-061433.md
**Architecture**: Dual-touchpoint integration in the /dev pipeline

---

## Overview

Graphify is a code-to-knowledge-graph tool that provides structural codebase context (import chains, module topology, function call graphs). The integration adds two new phases to the /dev workflow:

- **Step 1.5** — Deterministic pre-BA Bash hydrator (`graphify-query.py`): injects structural context BEFORE BA analysis to prevent confirmation bias on ambiguous requirements.
- **Step 7.5** — Graphify subagent enrichment (`graphify-enrich.py`): extracts a focused subgraph seeded by BA's blast-radius-map, AFTER BA-QA validation and BEFORE DEV dispatch.

Both phases are **advisory** (fail-open): Graphify tool failure never blocks DEV. Only requirement ambiguity (unresolved implicit references) is clarification-blocking.

---

## Storage Layout

```
/var/tmp/claude-graphify/<repo_key>/     # Global cache (disk, not /dev/shm)
├── manifest.json                         # branch, HEAD, graphify_version, file_hashes
├── graph.json
├── index/
└── cache/

.claude/dev-registry/{task_id}/graphify/  # Per-task immutable artifacts
├── pre_query.json                        # Step 1.5 output
├── graphify-run.json                     # Step 7.5 run manifest
├── focused-subgraph.json                 # Task-scoped subgraph
├── graph-summary.json                    # Compact summary
└── graph-report.md                       # Human-readable report
```

---

## Failure State Machine

| Status      | Trigger                                                                      |
|-------------|------------------------------------------------------------------------------|
| ok          | Binary present, cache hit, full data extracted without errors                |
| degraded    | Binary present and ran, but output parse error or partial data               |
| failed      | Non-zero exit code, timeout (>5 min incremental / >15 min init), subprocess error |
| unavailable | GRAPHIFY_BIN absent, cache absent, or manifest.json missing                  |
| skipped     | CLAUDE_GRAPHIFY_ENABLED=0, --no-graphify flag, or nil blast-radius-map       |

DEV always receives a valid (possibly empty) `graph_context` object regardless of status.

---

## Feature Flags

| Variable                   | Default | Description                                          |
|----------------------------|---------|------------------------------------------------------|
| CLAUDE_GRAPHIFY_ENABLED    | auto    | auto=run if available; 1=force on; 0=disable         |
| GRAPHIFY_BIN               | (PATH)  | Override CLI path                                    |
| CLAUDE_GRAPHIFY_CACHE_ROOT | /var/tmp/claude-graphify | Override cache root            |

Pass `--no-graphify` to `/dev` for per-invocation disable.

---

## Global Cache Lifecycle

```bash
# One-time initial build (user-triggered only — NEVER auto-triggered inside /dev)
python3 scripts/graphify-maintain.py init

# Incremental refresh (runs automatically at Step 7.5 and post-/pull)
python3 scripts/graphify-maintain.py update

# Status check
python3 scripts/graphify-maintain.py status
```

The first full build is NEVER auto-triggered inside /dev. It requires 2-15 minutes and must be run manually.

---

## Command Coverage

| Command        | Graphify integration                                     |
|----------------|----------------------------------------------------------|
| /dev           | Step 1.5 (pre-BA hydrator) + Step 7.5 (subagent)         |
| /dev-command   | Same as /dev (mirrors commands/dev.md)                   |
| /dev-overnight | Enabled; shares global cache via graphify-maintain.py    |
| /redev         | Inherits /dev behavior                                   |
| /pull          | Post-pull incremental update (non-blocking advisory)     |
| /refactor      | Optional (not implemented in v1)                         |
| /clean         | Disabled                                                 |

---

## Advisory vs Clarification-Blocking

- **Graphify tool failure** (status: degraded/failed/unavailable/skipped) → **advisory**: DEV always receives a valid graph_context object; tool failure never blocks DEV.
- **Requirement ambiguity** (implicit reference trigger words with no unique resolution) → **clarification-blocking**: BA must return `needs_clarification`.

---

## Architecture Note (arch-6)

`context-{ts}.json` is patched in-place by `graphify-enrich.py` to add the `graph_context` field. This diverges from a pure sidecar pattern (writing a separate file) but is accepted per spec Section 5. The deviation is recorded in `graph-report.md` for each task cycle.

---

## Sensitive Data Exclusion (arch-8)

`graphify_lib.py` defines `EXCLUDE_FRAGMENTS` from two authorities:

1. **Sensitive-data patterns** (spec §5 Risk-7 + arch-8): `.env`, `credentials`, `keys`, `/logs/`, `.pem`, `.key`, `.secret`
2. **Filesystem-noise patterns** (blast-radius-tool.py:35-38): `/venv/`, `/worktrees/`, `/.archive/`, `/plugins/`, `/.git/`, `/__pycache__/`, `/node_modules/`

---

## Agent Registration (arch-2)

`graphify` is registered at three sites together:
1. `CP_AGENTS` in `hooks/pretool-cp-checkin.py`
2. `ALLOWED_AGENTS` in `scripts/spec-check.py`
3. `agent_types` list in `hooks/prompt-workflow.py`

This mirrors the test-writer precedent (spec-20260518-225715 §5.2).
