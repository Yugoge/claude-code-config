# BA Specification: Dev Harness Extension — Cycle 2 Remediation

**Request ID**: 20260519-211515
**Task ID**: 20260519-211515
**Tier**: STANDARD
**Risk**: medium
**Cycle**: 2
**Created**: 2026-05-20T04:55:00Z
**Spec**: docs/dev/specs/spec-20260518-225715.md
**Prior**: docs/dev/ticket-20260519-132417.md (Cycle 1)

TASK-ID: 20260519-211515

---

## Goal

Close the three /close-gate failure axes from Cycle 1 (workflow integrity, gitignore cleanliness, style violations) by executing spec Section 7's Cycle 1 → Cycle 2 remediation plan Priorities 1-3 only (P4 deferred to Cycle 3 per user pre-dispatch decision). Cycle 1's 18 ACs PASSED and MUST NOT regress.

---

## Context

Cycle 1 (task-id 20260519-132417) delivered all 6 spec Section 5 components and 18 ACs verified PASS by QA. The /close gate returned CLOSE:NO with three concurring failure axes documented in spec Section 6:

1. **Workflow Integrity Bullet 1 (downstream consumability)**: `test-writer` agent unconsumable on first dispatch — `policies/tool-policy.v1.json` lacks the `test-writer` role, and the manifest contract between `agents/test-writer.md` and `agents/qa.md` is misaligned.
2. **Workflow Integrity Bullet 4 sub-iv (cleanliness)**: 3 runtime artifact patterns leak into git: `agent-scores.json`, `agent-scores.json.lock`, `.claude/specs/spec-*/`. Auto-regenerated indices (`README.md`, `INDEX.md`, `.claude/INDEX.md`) list the leaked entries.
3. **Style violations newly introduced in diff (12 critical)**: 5 `python3` invocations missing venv-activation prefix; `Sub-step 12.1` violates integer-step-numbering; 2 hardcoded `/tmp/` paths in canary-verify.sh; Chinese-language rank names + AskUserQuestion choices flagged under Standard 6.

User pre-dispatch decisions:
- **Q1 — Standard 6 Chinese-language**: "Add documented exemption" (do NOT translate user-facing source-language strings).
- **Q2 — P4 scope**: "Defer P4 to Cycle 3" (Cycle 2 is strictly P1+P2+P3).

---

## Setup / Environment

- **applicability**: N/A
- **reason**: non-UI -- agent-prompt edit + config; cycle does not produce (1) rendered UI changes, (2) browser interaction, (3) Playwright invocation, (4) screenshot evidence, or (5) any change to user-triggered code paths (no pipeline step or API endpoint changes — only orchestrator policy/dispatch/style configuration)

---

## Evidence (Contract A)

- **Observed**: User invoked `/dev` for Cycle 2; orchestrator captured spec Section 7 P1+P2+P3 as the binding remediation plan.
- **Measured** (17 observation points, all direct from current code/git state):
  - `grep test-writer policies/tool-policy.v1.json` → 0 hits (role absent)
  - `git check-ignore agent-scores.json` → exit 1 (NOT ignored)
  - `git check-ignore agent-scores.json.lock` → exit 1 (NOT ignored)
  - `git check-ignore .claude/specs/spec-20260518-225715/cp-state-ba.json` → exit 1 (NOT ignored)
  - `grep agent-scores README.md` → matches at lines 16-17
  - `grep agent-scores INDEX.md` → matches at lines 3417-3418, 11443-11444, 21534-21535
  - `agents/test-writer.md` schema block lines 80-127 implements Option (b) correctly; procedural sentences at lines 139, 181, 183, 198, 216 still cite root manifest as active (drift)
  - `agents/qa.md:992-998` reads root `manifest.json.active_tests[]` directly (Option (a) shape — wrong)
  - `commands/dev.md:856` contains literal `Sub-step 12.1:`
  - `commands/dev.md:1110` contains literal `from Sub-step 12.1`
  - `scripts/score-inject.sh:43` invokes `python3 - "${SCORES_FILE}" "${AGENT}" <<'PYEOF'` (heredoc form, no venv prefix)
  - `scripts/score-update.sh:70` invokes same heredoc form, no venv prefix
  - `scripts/canary-verify.sh:95`, `:106`, `:125` invoke `echo "${payload}" | python3 "${hook}"` (piped form, no venv prefix)
  - `scripts/canary-verify.sh:79` contains literal `/tmp/canary-safe.txt`
  - `scripts/canary-verify.sh:103` contains literal `/tmp/canary-oversized-$$.txt`
  - `agents/style-inspector.md:308-329` declares Standard 6 with existing Exemption paragraph at `:318` (task-id 20260509-153155 verbatim user-binding quotes); no source-language exemption exists yet
- **Expected**: Section 7 P1+P2+P3 prescribed changes applied → /close gate CLOSE:YES.
- **Gap**: 12 files need surgical edits across 8 ACs.

---

## Scope (Contract B)

- **Search pattern**: `test-writer|manifest|agent-scores|specs/spec-|python3|Sub-step 12\.1|/tmp/|Standard 6`
- **Search scope**: `policies/`, `agents/`, `commands/`, `scripts/`, `.gitignore`, `README.md`, `INDEX.md`, `.claude/INDEX.md`
- **User reported**: all 12 files (Section 7 enumerates them by name)
- **Additional found via grep**: none (Section 7 already enumerates every site)

**In-user-path files (12)**:
- `.gitignore` (append 3 patterns)
- `README.md` (regenerate)
- `INDEX.md` (regenerate)
- `.claude/INDEX.md` (regenerate)
- `policies/tool-policy.v1.json` (add test-writer role)
- `agents/test-writer.md` (procedural sentences at 5 line refs)
- `agents/qa.md` (Phase 5 logic + schema)
- `agents/style-inspector.md` (Standard 6 second exemption paragraph)
- `commands/dev.md` (test-writer dispatch + Dev dispatch + Sub-step 12.1 renumber + :1110 cross-ref)
- `scripts/score-inject.sh` (venv prefix at :43)
- `scripts/score-update.sh` (venv prefix at :70)
- `scripts/canary-verify.sh` (venv prefix at :95/:106/:125 + mktemp at :79/:103)

---

## Reference Source (Contract C)

- **Tier**: tier_2_verified
- **Source**: `docs/dev/specs/spec-20260518-225715.md` Section 7 — Cycle 1 → Cycle 2 remediation plan derived from /close debate (2026-05-19T20:02:00Z) + user pre-dispatch clarifications (Q1 + Q2).
- **Location**: spec Section 7 lines 335-359; user-decision answers in this BA dispatch prompt.
- **Copy allowed**: yes
- **Dev constraint**: All 8 changes are explicitly prescribed by Section 7. Do NOT invent values; do NOT widen scope; do NOT touch any of the 5 P4-deferred items.

---

## Prior Attempts (Contract D)

- **Triggered**: yes
- **Trigger source**: user_phrasing (orchestrator dispatch explicitly states "Cycle 2 of spec-20260518-225715")

### Attempts

- **Attempt 1 — Cycle 1 (task-id 20260519-132417)**, see `docs/dev/ticket-20260519-132417.md` + `docs/dev/dev-report-20260519-132417.json` + `docs/dev/qa-report-20260519-132417.json` + `docs/dev/close-report-20260519-132417.md`
  - **Proposed**: Implement all 6 spec Section 5 components (5.1-5.6) in a single COMPLEX dev cycle.
  - **Changed**: 6 new files created (5 scripts + 1 agent) + 5 existing files modified + SessionStart hook registered + agent-scores.json created with 21 agents.
  - **Outcome**: QA: 18/18 ACs PASS. /close: CLOSE:NO. Three failure axes (workflow integrity, gitignore cleanliness, 12 style-inspector critical findings + 1 Standard 6 escalation).
  - **Failure category**: `wrong_scope` (per-component delivery missed integration boundaries + repo hygiene + style standards)
  - **Target layer**: L5-infrastructure (created scripts/hooks/new agent) + L4-logic (event deltas, manifest schema, blast-radius algorithm)

### Novelty Check

- **This attempt's layer**: **L5-infrastructure** (tool-policy.v1.json role addition + .gitignore + indices regen) + **L4-logic** (manifest contract reconciliation between test-writer.md and qa.md, with QA verification scoped to current task_id per codex F4) + **L3-data** (script venv prefix edits, decimal-numbering renumber, /tmp → mktemp -d + EXIT trap, narrow Standard 6 exemption text)
- **Differs from all priors**: yes
- **Rationale**: Cycle 1 CREATED the harness extension artifacts. Cycle 2 RECONCILES the integration boundaries Cycle 1 introduced. Concretely: (1) `policies/tool-policy.v1.json` — Cycle 1 did NOT touch this file; (2) `.gitignore`, `README.md`, `INDEX.md`, `.claude/INDEX.md`, `agents/style-inspector.md` — NONE were in Cycle 1's files_to_modify; (3) Cycle-1-touched files Cycle 2 re-enters carry surgical-only edits: `commands/dev.md` (renumber + dispatch text only; logic unchanged), `scripts/*.sh` (venv prefix + mktemp only; logic unchanged), `agents/qa.md` (Phase 5 schema only; rest unchanged), `agents/test-writer.md` (5 procedural mentions only; schema unchanged). No overlap with Cycle 1 logic content. Cycle 1's failure category was `wrong_scope` (omitting integration + hygiene + style); Cycle 2 specifically targets exactly that omitted layer with no overlap of action.

---

## Requirements (MoSCoW)

### Must Have (P1+P2+P3 prescribed by Section 7)

- **P1.1**: Add `test-writer` role to `policies/tool-policy.v1.json` with proper allowed/denied lists.
- **P1.2**: Reconcile manifest contract to **Option (b)** — per-task `tests/generated/<task_id>/manifest.json` holds `active_tests[]`; root `tests/generated/manifest.json` is an INDEX (`kind: "index"`, `tasks: [...]`). Propagate to `agents/test-writer.md` (procedural sentences), `agents/qa.md` (Phase 5 + schema), `commands/dev.md` (dispatch + verification).
- **P2.3**: Append 3 patterns to `.gitignore`.
- **P2.4**: Regenerate `README.md`, `INDEX.md`, `.claude/INDEX.md` (AFTER .gitignore edit per codex F7).
- **P3.6**: Prefix `source ~/.claude/venv/bin/activate &&` to 5 python3 sites, preserving stdin-pipe semantics (codex F8).
- **P3.7**: Renumber `Sub-step 12.1` → `Step 12a` + update cross-reference at `:1110`.
- **P3.8**: Replace hardcoded `/tmp/canary-*` in `scripts/canary-verify.sh` with `mktemp -d "${TMPDIR:-/tmp}/canary-verify.XXXXXX"` + EXIT-trap cleanup (codex F9).
- **P3.9**: Add narrow Standard 6 exemption paragraph in `agents/style-inspector.md` for user-facing source-language strings only.

### Should Have

(none — all binding items are Must)

### Could Have

(none — Cycle 2 scope is strictly Section 7 P1+P2+P3)

### Won't Have (Non-Goals — per user P4 decision)

- **P2.5**: `agent-scores.example.json` tracked seed (spec says "Optionally"; defer to keep scope minimal)
- **B-IT3F-1**: BA tool-policy prefix patch for `docs/dev/acceptance-criteria-*` and `.claude/dev-registry/*/blast-radius-map.json` (BA's iter-2 Python-write workaround stays authorized for THIS cycle's BA outputs only; proper policy patch is Cycle 3)
- **B-IT3F-4**: `session-info.sh` / `session-git-init.sh` stdout→stderr fix
- **blast-radius Phase 2** untracked-file detection gap
- **QA Phase 5 trigger asymmetry** (gate stays as-is: `complexity_tier >= STANDARD OR risk_level=high`)
- **Canary fail-closed depth** for write-guard / git-privilege-guard

---

## Requirements Decomposition

| ID | Source phrase (verbatim from Section 7) | Classification | Acceptance criterion |
|----|-----------------------------------------|----------------|----------------------|
| R-C2-1 | "tool-policy.v1.json: add `test-writer` role with Read access + Write/Edit limited to `tests/generated/**` + its registry/cp-state paths" | user-need | AC-C2-01 |
| R-C2-2 | "manifest contract reconciliation: pick ONE shape and propagate ... Update test-writer.md AND qa.md AND commands/dev.md verification step in lockstep" | user-need | AC-C2-02 |
| R-C2-3 | "Append to `.gitignore`: `/agent-scores.json`, `/agent-scores.json.lock`, `/.claude/specs/spec-*/`" | user-need | AC-C2-03 |
| R-C2-4 | "Regenerate auto-generated indices (README.md, INDEX.md, .claude/INDEX.md) to drop the leaked entries" | user-need | AC-C2-04 |
| R-C2-5 | "Add venv-activation prefix to all python3 invocations in scripts/score-inject.sh, scripts/score-update.sh, scripts/canary-verify.sh" | user-need | AC-C2-05 |
| R-C2-6 | "Renumber `Sub-step 12.1` in commands/dev.md to `Step 12a` ... (and update cross-reference at line ~1110)" | user-need | AC-C2-06 |
| R-C2-7 | "Replace hardcoded `/tmp/` in scripts/canary-verify.sh with a portable temp-file mechanism" | user-need | AC-C2-07 |
| R-C2-8 | "Standard 6 Chinese-language decision: add documented exemption clause in /dev quality standards declaring user-facing strings authored in the spec's source language are exempt from Standard 6" (per user Q1 answer) | user-need | AC-C2-08 |

---

## Edge Cases & Risks

1. **Cycle 1 regression risk** — Cycle 1's 18 ACs are the most important non-regression target. Dev MUST verify representative Cycle 1 outputs (AC-01 ba +8, AC-02 stdout 41-60 / stderr empty, AC-14 all 13 events, AC-15 canary SessionStart entry, AC-17 21-agent schema, AC-18 inject format) still hold after Cycle 2 edits.

2. **JSON syntax integrity of tool-policy** — `policies/tool-policy.v1.json` gates every subagent tool call. A malformed edit corrupts the JSON and bricks every subagent across the repo. Dev MUST run `python3 -c "import json; json.load(open('policies/tool-policy.v1.json'))"` before declaring P1.1 done.

3. **codex F1 — denied list must NOT include `/tests/`** — copying other non-core roles' denied lists verbatim would include `/tests/`, which would override the role's own `tests/generated/**` allowlist and brick the new role. Use only the protected/source denies: `/src/`, `/app/`, `/lib/`, `/.claude/hooks/`, `/.claude/agents/`, `/.claude/commands/`, `/.claude/policies/`, `/.claude/schemas/`, `/.claude/scripts/`, `/.claude/settings.json`.

4. **codex F2 — glob form must use `*/` prefix** — bare `tests/generated/**` does not match absolute normalized paths. Use the existing policy idiom: `*/tests/generated/`, `*/.claude/dev-registry/*/test-writer.json`, etc.

5. **codex F3 — test-writer.md is NOT unchanged** — schema block (80-127) is already Option (b), but procedural mentions at lines 139, 181, 183, 198, 216 (and the JSON `manifest_path` example at line 198 in the report template) describe root manifest as active. Cycle 2 surgical edit to those 5 references only — DO NOT change the schema.

6. **codex F4 — QA scoped to current task_id** — `qa.md` Phase 5 must read the root INDEX only to find the current task_id, then verify only that task's per-task manifest. Iterating ALL tasks would regress on stale tests from previous cycles.

7. **codex F5 — commands/dev.md verification needs both manifests + report** — the existing line 632 check (`tests/generated/manifest.json AND test-writer-report-<task_id>.json BOTH exist`) must be EXPANDED to require all three artifacts (root index + per-task manifest + report).

8. **codex F6 — qa.md output schema fields** — `manifest_verification` block must add `root_index_path`, `per_task_manifest_path`, `task_id` so QA reports correctly under the Option (b) shape.

9. **codex F7 — .gitignore must precede regen** — if regen runs first, the leaked entries reappear (regenerator walks the filesystem; only .gitignore-respecting walkers skip them). Order: .gitignore edit → regen → verify no leaks remain.

10. **codex F8 — stdin pipe form preserved** — Naively prepending `source ... &&` to the bare `python3` token in a pipe context (`echo "$payload" | python3 hook`) results in `echo "$payload" | source ... && python3 hook`, which sends the payload to `source`, not python3. The correct form is `source ~/.claude/venv/bin/activate && echo "$payload" | python3 "$hook" ...`. Heredoc form (`python3 - <<'PYEOF'`) is simpler: `source ... && python3 - <<'PYEOF'`.

11. **codex F9 — mktemp -d + EXIT trap** — Replace both `/tmp/canary-*` literals with a single `CANARY_TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/canary-verify.XXXXXX")"` + `trap 'rm -rf "$CANARY_TMPDIR"' EXIT`. Files live under `$CANARY_TMPDIR/`. The `exec >/dev/null` invariant at the top of canary-verify.sh is preserved — EXIT traps still fire under `exec >/dev/null`.

12. **codex F10 — narrow Standard 6 exemption** — A broad "user-facing source-language strings" exemption could mask real Standard 6 violations. The exemption MUST be narrow: ONLY literal user-facing labels/messages (rank names, AskUserQuestion choice strings, prompt-injection tail phrases) in spec-authored UI surfaces; comments, diagnostic stderr, command prose, implementation notes remain English-only. The exemption text MUST cite `spec-20260518-225715` and task-id `20260519-211515` so future readers can trace authority.

13. **P4 scope guard** — Section 7's P4 parentheticals can lure expansion. Dev MUST NOT touch: B-IT3F-1 (BA tool-policy prefixes), B-IT3F-4 (stdout/stderr hooks), blast-radius Phase 2 untracked-file gap, QA Phase 5 trigger asymmetry, canary fail-closed depth.

---

## Out-of-Scope Observations

| ts | file:line | observation | security_relevant |
|----|-----------|-------------|-------------------|
| 2026-05-20T04:55:00Z | agents/style-inspector.md:318 | Existing Exemption paragraph (task-id 20260509-153155 verbatim user-binding quotes) is preserved verbatim; Cycle 2 adds a SECOND exemption paragraph adjacent. Recorded for explicit additive nature. | false |
| 2026-05-20T04:55:00Z | agents/test-writer.md:80-127 | Schema block already implements Option (b) correctly. Cycle 2 surgical edit touches procedural sentences only (lines 139, 181, 183, 198, 216). Schema unchanged. | false |
| 2026-05-20T04:55:00Z | policies/tool-policy.v1.json (BA role) | Per orchestrator P4 decision, BA's iter-2 Python-write workaround stays authorized for THIS cycle's outputs. B-IT3F-1 proper policy patch deferred to Cycle 3. | false |
| 2026-05-20T04:55:00Z | hooks/session-info.sh + hooks/session-git-init.sh | Cycle 1 documented these as stdout-emitting; canary-verify.sh emits stderr advisories without exit 2. B-IT3F-4 fix deferred to Cycle 3. | false |

---

## Acceptance Criteria

ac_uid algorithm: `sha256(type + given + when + then + json.dumps(check, sort_keys=True, separators=(',',':'), ensure_ascii=False))[:16]`. Full canonical AC items live in `docs/dev/acceptance-criteria-20260519-211515.json` (8 items); concise summary here:

### AC-C2-01: tool-policy.v1.json has correctly-shaped test-writer role
- GIVEN `policies/tool-policy.v1.json` after Cycle 2 dev edits
- WHEN the JSON is parsed and `roles['test-writer']` is read
- THEN allowed_tools is exactly `[Read,Glob,Grep,Bash,Write,Edit,MultiEdit]` (set equality); allowed_write_path_prefixes contains all 5 required `*/`-prefix entries; denied_write_path_prefixes contains the 10-entry protected-dir set; denied list DOES NOT contain `/tests/` (codex F1).

### AC-C2-02: manifest contract Option (b) consistent across 3 files
- GIVEN `agents/test-writer.md`, `agents/qa.md`, `commands/dev.md` after Cycle 2 dev edits
- WHEN each file's manifest-contract sentences are inspected
- THEN all three describe Option (b) consistently: per-task `tests/generated/<task_id>/manifest.json` holds `active_tests[]`; root is INDEX (`kind: "index"`, `tasks: [...]`); QA reads root to find current task_id, verifies only that task's per-task manifest; pytest scoped to `tests/generated/<task_id>/` (codex F4); test-writer.md procedural mentions at lines ~139/181/183/198/216 align (codex F3).

### AC-C2-03: .gitignore contains 3 new patterns AND git check-ignore returns exit 0
- GIVEN `.gitignore` after Cycle 2 dev edits
- WHEN the file is read AND `git check-ignore` is invoked on the 3 runtime artifact paths
- THEN `.gitignore` contains the literal lines `/agent-scores.json`, `/agent-scores.json.lock`, `/.claude/specs/spec-*/`; all three `git check-ignore` invocations exit 0.

### AC-C2-04: README.md / INDEX.md / .claude/INDEX.md no longer list leaked entries
- GIVEN the 3 index files after Cycle 2 dev edits
- WHEN each file is grepped for `agent-scores.json` and `agent-scores.json.lock`
- THEN zero matches across all three files (codex F7: .gitignore applied BEFORE regen).

### AC-C2-05: 5 python3 sites have venv-activation prefix with stdin pipe form preserved
- GIVEN the 3 scripts after Cycle 2 dev edits
- WHEN each python3 invocation is inspected
- THEN all 5 sites have `source ~/.claude/venv/bin/activate &&` preceding python3; canary-verify.sh sites use the form `source ... && echo "$payload" | python3 "$hook" ...` (NOT `echo "$payload" | source ... && python3 ...`) per codex F8; score-inject.sh and score-update.sh use the heredoc form `source ... && python3 - <<'PYEOF'`.

### AC-C2-06: commands/dev.md no longer contains 'Sub-step 12.1'; cross-reference updated
- GIVEN `commands/dev.md` after Cycle 2 dev edits
- WHEN the file is grepped for `Sub-step 12.1`
- THEN zero matches; new heading is `**Step 12a**`; cross-reference at the former line ~1110 now reads `from Step 12a`.

### AC-C2-07: canary-verify.sh uses mktemp -d + EXIT trap, no hardcoded /tmp/canary-* literals
- GIVEN `scripts/canary-verify.sh` after Cycle 2 dev edits
- WHEN the file is grepped for `/tmp/canary-` literals
- THEN zero matches; the script uses `mktemp -d "${TMPDIR:-/tmp}/canary-verify.XXXXXX"`; an EXIT trap registers cleanup (`trap 'rm -rf ...' EXIT`).

### AC-C2-08: narrow Standard 6 exemption clause exists with citation
- GIVEN `agents/style-inspector.md` after Cycle 2 dev edits
- WHEN the Standard 6 Exemption block is read
- THEN a SECOND exemption paragraph follows the existing verbatim-user-binding-quotes paragraph; the new exemption is narrow (only user-facing source-language labels in spec-authored UI surfaces — rank names, AskUserQuestion choices, prompt-injection tail); explicitly excludes comments/diagnostics/prose/implementation notes; cites `spec-20260518-225715` and task-id `20260519-211515`.

---

## Technical Hints

**Affected files (12)**:
- Modify: `policies/tool-policy.v1.json`, `agents/test-writer.md`, `agents/qa.md`, `agents/style-inspector.md`, `commands/dev.md`, `scripts/score-inject.sh`, `scripts/score-update.sh`, `scripts/canary-verify.sh`, `.gitignore`, `README.md`, `INDEX.md`, `.claude/INDEX.md`
- Create: none

**Suggested edit order (codex F7 enforced)**:
1. `policies/tool-policy.v1.json` (P1.1; do first so future test-writer dispatches work; validate JSON after)
2. `agents/test-writer.md` procedural mentions (P1.2 — 5 surgical edits at lines 139, 181, 183, 198, 216)
3. `agents/qa.md` Phase 5 logic+schema (P1.2 — qa.md:992-998 + output schema `manifest_verification` block adds `root_index_path`, `per_task_manifest_path`, `task_id`)
4. `commands/dev.md` test-writer dispatch + Dev dispatch + verification (P1.2 — :628, :632, :661 expand to mention both manifests)
5. `.gitignore` append 3 lines (P2.3 — BEFORE regen)
6. Regen `README.md`, `INDEX.md`, `.claude/INDEX.md` (P2.4)
7. `scripts/score-inject.sh:43`, `scripts/score-update.sh:70` venv prefix (heredoc form)
8. `scripts/canary-verify.sh:95/:106/:125` venv prefix (piped form, codex F8)
9. `commands/dev.md:856` Sub-step 12.1 -> Step 12a; `commands/dev.md:1110` cross-ref update (P3.7)
10. `scripts/canary-verify.sh:79/:103` mktemp -d + EXIT trap (P3.8, codex F9)
11. `agents/style-inspector.md:~318` add second exemption paragraph (P3.9, codex F10)

**Final validation Dev MUST run**:
- `python3 -c "import json; json.load(open('policies/tool-policy.v1.json'))"` -> exit 0 (after step 1)
- All 8 Cycle-2 ACs pass (`docs/dev/acceptance-criteria-20260519-211515.json`)
- Cycle 1 spot-check: AC-01 (ba +8), AC-02 (rank+range in stdout, stderr empty), AC-14 (13 canonical events), AC-15 (SessionStart canary entry), AC-17 (21-agent schema), AC-18 (inject format/placement) all still pass

**Constraints**:
- Do NOT touch any of the 5 P4-deferred items (see Won't Have list).
- Do NOT modify Cycle 1's logic content. Surgical edits only.
- BA's iter-2 Python-write workaround is authorized for THIS cycle's BA-owned outputs (acceptance-criteria-20260519-211515.json + blast-radius-map.json under .claude/dev-registry/dev-20260519-211515/). Dev does NOT need to use this workaround — Dev's tool-policy is broader.
- Codex consultation INVOKED (codex_required=true); 10 findings all applied. See context-20260519-211515.json `codex_consult` for the full disposition.

---

TASK-ID: 20260519-211515
