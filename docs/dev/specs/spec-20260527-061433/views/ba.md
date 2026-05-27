<!-- AUTO-GENERATED VIEW for ba | source: docs/dev/specs/spec-20260527-061433.md | extracted: 2026-05-27T06:30:00+00:00 -->

# ba view of spec-20260527-061433

**Monolith**: docs/dev/specs/spec-20260527-061433.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> Orchestrator directly calls `graphify-query.py` via Bash (NOT a subagent — avoids adding another LLM interpretation layer that could propagate confirmation bias)

> Injected into BA's input so BA sees repo structure BEFORE forming its initial interpretation

> When user requirement contains implicit reference words (之前/已有/现有/原来的/previous/existing/original), BA MUST complete Reference Resolution before entering solution analysis:

---

## Acceptance Criterion

Integrate Graphify (code-to-knowledge-graph tool) into the existing Claude Code multi-agent orchestration system as a dual-touchpoint architecture, based on 5-round Claude+Codex consensus. The integration solves two problems: (1) DEV agents lack structural codebase context during implementation, and (2) BA agents suffer from confirmation bias when interpreting ambiguous user requirements that reference existing code structures.

---

## Dual Touchpoint — BA-Relevant Steps

**Step 1.5 — Pre-BA Graph Pre-query (deterministic context hydrator)**
- Orchestrator directly calls `graphify-query.py` via Bash (NOT a subagent — avoids adding another LLM interpretation layer that could propagate confirmation bias)
- Extracts file/concept mentions from user requirement text using 3-layer extraction: deterministic rules → repo alias index → graph/fuzzy query
- Queries the global Graphify cache (read-only) and returns `structural_context` (800-1500 tokens, 2000 hard cap)
- Must include `ambiguity_hypotheses` when implicit reference words detected (之前/已有/现有/原来的/previous/existing/original)
- Output: `dev-registry/{task_id}/graphify/pre_query.json`
- Injected into BA's input so BA sees repo structure BEFORE forming its initial interpretation

---

## BA Reference Resolution Rule

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

## Failure Strategy — BA-Relevant

- `graph_context.status` state machine: `ok | degraded | failed | unavailable | skipped`
- Graphify tool failure is **advisory** — never blocks DEV
- Requirement ambiguity is **NOT advisory** — BA must block and ask user for clarification
- Step 1.5 without global cache: `status=unavailable`, skip silently, BA runs original flow

---

## BA Agent Modifications

- agents/ba.md (modify — Reference Resolution rule + implicit reference detection)

---

## Risk Items — BA-Relevant

1. No decimal Step headings in files (style-inspector rejects) — use "between Step N and Step N+1"
4. structural_context too large — hard cap 2000 tokens
6. Advisory vs ambiguity confusion — tool failure advisory; requirement ambiguity blocking
