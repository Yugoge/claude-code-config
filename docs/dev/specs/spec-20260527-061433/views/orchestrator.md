<!-- AUTO-GENERATED VIEW for orchestrator | source: docs/dev/specs/spec-20260527-061433.md | extracted: 2026-05-27T06:30:00+00:00 -->

# orchestrator view of spec-20260527-061433

**Monolith**: docs/dev/specs/spec-20260527-061433.md

---

## Role Mandate (from spec)

> Integrate Graphify (code-to-knowledge-graph tool) into the existing Claude Code multi-agent orchestration system as a dual-touchpoint architecture, based on 5-round Claude+Codex consensus. The integration solves two problems: (1) DEV agents lack structural codebase context during implementation, and (2) BA agents suffer from confirmation bias when interpreting ambiguous user requirements that reference existing code structures.

---

## Pipeline Workflow

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

## Hard Rules Relevant to Orchestrator

- Orchestrator directly calls `graphify-query.py` via Bash (NOT a subagent — avoids adding another LLM interpretation layer that could propagate confirmation bias)
- DEV consumes graph_context but NEVER runs Graphify itself
- Graphify tool failure is **advisory** — never blocks DEV
- Requirement ambiguity is **NOT advisory** — BA must block and ask user for clarification
- First full build NEVER auto-triggered inside /dev flow

---

## Spec Preamble

# Spec: Graphify Knowledge Graph Integration — Dual-Touchpoint Architecture

**Pipeline**: graphify-integration
**Session**: codex-5round-consensus
**Created**: 2026-05-27T06:14:33+00:00

---

## Section Structure

### Architecture: Dual Touchpoint

### BA Reference Resolution Rule

### Global Graph Maintenance (A+B Scheme)

### Storage Layout

### Failure Strategy

### Feature Flags

### QA Final Verification Enhancement

### Command Coverage

### Implementation Plan (3 PRs, 32 files)

### Risk Checklist

### Origin

---

## Empty Section Templates

## Section 1: Before

<!-- WHO WRITES: PM (autonomous mode) or User (user-spec mode) or BA (if Section 1 empty and BA has context) -->
<!-- WHAT: Screenshot path + text description of the current state BEFORE any fix attempt. -->
<!-- This establishes the baseline so later cycles can compare. -->

### Cycle 1

## Section 2: What Was Attempted

<!-- WHO WRITES: Dev (after each implementation attempt) -->
<!-- WHAT: Per-cycle record of what approach was tried, what the rationale was, and why it failed (if it failed). -->
<!-- This prevents the next cycle's Dev from repeating the same approach. -->

### Cycle 1

## Section 3: What Was Changed

<!-- WHO WRITES: Dev (after each implementation) -->
<!-- WHAT: Exact file changes with line numbers and old->new values. -->
<!-- FORMAT: - **file.tsx:42** -- `property: oldValue` -> `property: newValue` -->

### Cycle 1

## Section 4: Current State

<!-- WHO WRITES: QA (after each verification) -->
<!-- WHAT: Actual measured values -- pixel dimensions, computed CSS, console output, screenshot paths. -->
<!-- This gives the next cycle's Dev concrete data to work with instead of vague "it failed". -->

### Cycle 1

## Section 5: User's Acceptance Criterion

<!-- WHO WRITES: BA (on first analysis) -->
<!-- WHAT: Verbatim quote from user's requirement or focus string. -->
<!-- This is the single source of truth for what "done" means. Do not paraphrase. -->

## Section 6: Why Not Met

<!-- WHO WRITES: QA (when verdict is fail) -->
<!-- WHAT: Specific gap between measured state (Section 4) and acceptance criterion (Section 5). -->
<!-- Must include evidence: actual value vs expected value. -->

### Cycle 1

## Section 7: What Must Be Done

<!-- WHO WRITES: QA (on fail) or PM-Retro -->
<!-- WHAT: Prescriptive next step for this specific issue. Not generic advice -- a concrete action. -->
<!-- Example: "Increase padding from 8px to 16px in Chat.tsx:42" not "fix the padding" -->

### Cycle 1

## Section 8: Attention Notes

<!-- WHO WRITES: PM-Retro -->
<!-- WHAT: Issue-specific traps, warnings, and things to watch out for in the next cycle/session. -->
<!-- Example: "This file is imported by 12 components -- changes here cascade widely" -->

---

## Agent Relevance Analysis

| Agent | Relevant | Reason |
|-------|----------|--------|
| ui-specialist | no | No visual design, CSS, or UI component work in this spec |
| ba | yes | Spec defines BA Reference Resolution Rule, implicit reference detection, new BA-QA fail gates |
| dev | yes | Primary implementer: 32 files across 3 PRs, scripts, schemas, hooks, feature flags |
| qa | yes | QA Final Verification Enhancement (graph_verification), BA-QA validation fail gates |
| pm | no | No priority rankings or timeline constraints beyond the self-contained spec |
| architect | yes | Dual-touchpoint architecture, storage layout, data flow, failure state machine, cache design |
| product-owner | no | No user stories or business requirements beyond technical integration |
| user | no | No end-user scenarios or interaction flows |
| cleaner | no | No cleanup actions specified |
| cleanliness-inspector | no | No file organization inspection needed |
| git-edge-case-analyst | no | No git history edge cases |
| prompt-inspector | no | No prompt inspection task defined |
| rule-inspector | no | No folder rule discovery |
| style-inspector | no | Style constraint is a dev risk note, not a style audit task |
| test-executor | no | No existing tests to execute (tests are to be written) |
| test-validator | no | No existing test files to validate |

## Views Created

- ba.md
- dev.md
- qa.md
- architect.md
- orchestrator.md

## Monolith Sections

### Section 1: Before
_Not yet populated._

### Section 2: What Was Attempted
_Not yet populated._

### Section 3: What Was Changed
_Not yet populated._

### Section 4: Current State
_Not yet populated._

### Section 5: User's Acceptance Criterion
Integrate Graphify (code-to-knowledge-graph tool) into the existing Claude Code multi-agent orchestration system...

### Section 6: Why Not Met
_Not yet populated._

### Section 7: What Must Be Done
_Not yet populated._

### Section 8: Attention Notes
_Not yet populated._
