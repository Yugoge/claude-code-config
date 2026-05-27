<!-- AUTO-GENERATED VIEW for architect | source: docs/dev/specs/spec-20260527-061433.md | extracted: 2026-05-27T06:30:00+00:00 -->

# architect view of spec-20260527-061433

**Monolith**: docs/dev/specs/spec-20260527-061433.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> Dispatched as `graphify` subagent (mode=enrich) after BA-QA validation passes, before DEV

> Runs `graphify --update` for incremental refresh, then extracts focused subgraph based on BA's blast-radius-map.json

---

## Architecture: Dual Touchpoint

**Step 1.5 — Pre-BA Graph Pre-query (deterministic context hydrator)**
- Orchestrator directly calls `graphify-query.py` via Bash (NOT a subagent — avoids adding another LLM interpretation layer that could propagate confirmation bias)
- Extracts file/concept mentions from user requirement text using 3-layer extraction: deterministic rules → repo alias index → graph/fuzzy query
- Queries the global Graphify cache (read-only) and returns `structural_context` (800-1500 tokens, 2000 hard cap)
- Must include `ambiguity_hypotheses` when implicit reference words detected (之前/已有/现有/原来的/previous/existing/original)
- Output: `dev-registry/{task_id}/graphify/pre_query.json`
- Injected into BA's input so BA sees repo structure BEFORE forming its initial interpretation

**Step 7.5 — Pre-DEV Graph Enrichment (graphify subagent)**
- Dispatched as `graphify` subagent (mode=enrich) after BA-QA validation passes, before DEV
- Runs `graphify --update` for incremental refresh, then extracts focused subgraph based on BA's blast-radius-map.json
- Output: `dev-registry/{task_id}/graphify/` containing `graphify-run.json`, `focused-subgraph.json`, `graph-summary.json`, `graph-report.md`
- Patches `context-{ts}.json` with `graph_context` field (summary + path references)
- DEV consumes graph_context but NEVER runs Graphify itself

---

## Global Graph Maintenance (A+B Scheme)

- Initial build: user manually runs `scripts/graphify-maintain.py init` (one-time, 2-15 min)
- /dev Step 7.5: `graphify --update` incremental refresh per task
- /pull: post-pull trigger `graphify-maintain.py update` (non-blocking advisory)
- Step 1.5 without global cache: `status=unavailable`, skip silently, BA runs original flow
- First full build NEVER auto-triggered inside /dev flow

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

## Failure Strategy

- `graph_context.status` state machine: `ok | degraded | failed | unavailable | skipped`
- Graphify tool failure is **advisory** — never blocks DEV
- Requirement ambiguity is **NOT advisory** — BA must block and ask user for clarification
- Timeout: 5 min (incremental) / 15 min (first build)
- CLI not installed → `status=unavailable`; parse errors → `status=degraded`; no cache → `status=unavailable`

---

## Feature Flags

- `CLAUDE_GRAPHIFY_ENABLED=auto|1|0` (default: auto — run if cache/tool available, degrade gracefully if not)
- `/dev --no-graphify` — explicit per-invocation disable
- `GRAPHIFY_BIN` — override CLI path
- `CLAUDE_GRAPHIFY_CACHE_ROOT` — override `/var/tmp/claude-graphify`

---

## Risk Checklist

2. Cache cross-branch pollution — manifest records branch + HEAD + graphify_version
3. Global cache concurrent writes — file lock on /var/tmp/claude-graphify/<repo_key>
4. structural_context too large — hard cap 2000 tokens
7. Sensitive data in graph cache — exclude .env, credentials, keys, logs

---

## Origin

This spec was produced from 5 rounds of Claude+Codex architectural discussion:
- R1: Embedding position → Step 7.5 (independent phase)
- R2: Data flow → global incremental cache + task-level focused subgraph + manifest dedup
- R3: Boundaries → best-effort advisory, performance budgets, failure recovery
- R4: Dual touchpoint → Step 1.5 as deterministic Bash hydrator + BA Reference Resolution
- R5: Implementation plan → 32 files, 3 PRs, feature flags, 8 risk items
