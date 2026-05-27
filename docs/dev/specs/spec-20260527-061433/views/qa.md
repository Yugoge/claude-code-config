<!-- AUTO-GENERATED VIEW for qa | source: docs/dev/specs/spec-20260527-061433.md | extracted: 2026-05-27T06:30:00+00:00 -->

# qa view of spec-20260527-061433

**Monolith**: docs/dev/specs/spec-20260527-061433.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> QA Step 11 adds `graph_verification` field to qa-report:

> Requirement ambiguity is **NOT advisory** — BA must block and ask user for clarification

---

## Acceptance Criterion

Integrate Graphify (code-to-knowledge-graph tool) into the existing Claude Code multi-agent orchestration system as a dual-touchpoint architecture, based on 5-round Claude+Codex consensus. The integration solves two problems: (1) DEV agents lack structural codebase context during implementation, and (2) BA agents suffer from confirmation bias when interpreting ambiguous user requirements that reference existing code structures.

---

## BA Reference Resolution Rule — QA Verification Gates

When user requirement contains implicit reference words (之前/已有/现有/原来的/previous/existing/original), BA MUST complete Reference Resolution before entering solution analysis:
1. User phrase verbatim
2. At least two possible interpretations
3. Repo/session evidence for each interpretation
4. Reason for excluding rejected interpretation
5. Final choice with confidence
6. If confidence insufficient → needs_clarification

BA-QA validation gains new fail gates:
- BA ignores structural_context.candidate_anchors → FAIL
- BA has no Reference Resolution when implicit references detected → FAIL
- BA only proves its initial interpretation without listing counter-evidence → FAIL

---

## QA Final Verification Enhancement

QA Step 11 adds `graph_verification` field to qa-report:
- Check if DEV touched god_nodes / high-risk paths identified by graph
- Flag impacted-but-untouched paths
- Read graph_context summary for static coverage check
- No full graph diff in v1 (too costly/noisy)

---

## Failure Strategy — QA-Relevant

- `graph_context.status` state machine: `ok | degraded | failed | unavailable | skipped`
- Graphify tool failure is **advisory** — never blocks DEV
- Requirement ambiguity is **NOT advisory** — BA must block and ask user for clarification
- Timeout: 5 min (incremental) / 15 min (first build)
- CLI not installed → `status=unavailable`; parse errors → `status=degraded`; no cache → `status=unavailable`

---

## Feature Flags

- `CLAUDE_GRAPHIFY_ENABLED=auto|1|0` (default: auto — run if cache/tool available, degrade gracefully if not)
- `/dev --no-graphify` — explicit per-invocation disable

---

## Command Coverage

- `/dev`: default enabled (Step 1.5 + Step 7.5)
- `/dev-overnight`: enabled, shares global update
- `/redev`: inherits /dev behavior
- `/refactor`: optional
- `/clean`: disabled
- `/pull`: post-pull incremental update trigger

---

## Risk Checklist

1. No decimal Step headings in files (style-inspector rejects) — use "between Step N and Step N+1"
2. Cache cross-branch pollution — manifest records branch + HEAD + graphify_version
3. Global cache concurrent writes — file lock on /var/tmp/claude-graphify/<repo_key>
4. structural_context too large — hard cap 2000 tokens
5. DEV accidentally runs Graphify — dev.md explicitly prohibits
6. Advisory vs ambiguity confusion — tool failure advisory; requirement ambiguity blocking
7. Sensitive data in graph cache — exclude .env, credentials, keys, logs
8. /dev-command parity — must sync structural_context and graphify enrichment
