# BA Specification: 3-Cluster Harness Fixes (Shippability Gate / Real-Fixture Verification / Event-Sourced Lifecycle Log)

**Request ID**: 20260519-211515
**Created**: 2026-05-20T11:30:00Z
**Tier**: STANDARD
**Risk**: high (shared infrastructure: modifies score-update.sh + commands/close.md + commands/commit.md + commands/dev.md + agents/qa.md + .gitignore)
**Task-id**: 20260519-211515
**Note on prior content**: this file was previously occupied by a stale D+H bugfix BA spec from a parallel cycle (Cycle 2 of spec-20260518-225715). That cycle's task-id collided with this one. The D+H content has been superseded by the harness work described below, which is the authoritative BA spec for task-id 20260519-211515 per the user requirement document at `docs/dev/user-requirement-dev-20260519-211515.md`.

## Goal

Land all 13 acceptance criteria (AC1-AC13) from `docs/dev/user-requirement-dev-20260519-211515.md` by delivering three concrete harnesses that prevent the prior cycle (task-id 20260519-161035) failure pattern: dev shipped artifacts that were gitignored (`docs/reference/tmp-cleanup-convention.md`), out-of-repo (`/usr/local/sbin/tmp-cleanup.sh`), and persistent-on-ephemeral (`/tmp/claude-pressure-warn-<token>`); `/close` said YES; the cycle "completed" leaving the deliverable broken.

## Context

Prior cycle 20260519-161035 (4-layer tmpfs prevention) shipped successfully on paper but produced a meta-assessment (17 systemic issues) documenting that the close gate is blind to (R1) gitignored artifacts, (R2) out-of-repo system paths without install manifest, (R5a) persistence on ephemeral mounts, (R3) destructive-only-as-dry-run, (R4) threshold-tests-as-mocks, (W3) silent quota walls, (W5) silent agent resumption, (R9) un-audited score writes. User selected "修复全部" — fix all 3 TOP clusters (8 of 17 issues); the remaining 9 are deferred (Out-of-Scope Observations).

## Setup / Environment

- **applicability**: N/A
- **reason**: non-UI — agent-prompt edit + bash/python script creation + .gitignore edit + settings.json (optional permission entries); cycle does not produce (1) rendered UI changes, (2) browser interaction, (3) Playwright invocation, (4) screenshot evidence, or (5) any change to user-triggered code paths (pipeline steps, API endpoints). All targets are dev/QA harness infrastructure invoked by `/close`, `/commit`, and `/dev` orchestration, never by an end-user UI surface.

## Evidence (Contract A)

- **Observed**: User cited 3 TOP clusters from `docs/dev/meta-assessment-20260519-161035.json` (R1+R2+R5a / R3+R4 / W3+W5+R9); 13 ACs in `user-requirement-dev-20260519-211515.md`.
- **Measured**:
  - `dev-report-20260519-161035.json:13` lists `docs/reference/tmp-cleanup-convention.md` in `files_created`. Verified gitignored: `.gitignore:51 docs/*` matches (the `!docs/dev/` exception at :52 does NOT cover `docs/reference/`).
  - `dev-report-20260519-161035.json:10` lists `/usr/local/sbin/tmp-cleanup.sh` in `files_modified`. Path is outside `git rev-parse --show-toplevel` (= `/dev/shm/dev-workspace/dot-claude`); no install manifest exists at `scripts/install/`.
  - `hooks/userprompt-tmpfs-pressure.sh` rationale (dev-report:40) references counter at `/tmp/claude-pressure-warn-<token>` — `/tmp` is ephemeral tmpfs; no ENOSPC fallback.
  - `scripts/score-update.sh:147` reads `agents[agent]["score"]` directly without compare-against-prev under the flock; concurrent invocations sharing pre-state can both write — lost-update race possible.
  - `.gitignore:46` contains `logs/` (matches `logs/lifecycle.jsonl` AND `.claude/logs/lifecycle.jsonl` because gitignore patterns without a leading `/` match at any depth). Verified: `git check-ignore -v logs/lifecycle.jsonl` → `.gitignore:46:logs/`.
- **Expected**:
  - `/close` (and `/commit` PRIMARY path as belt-and-suspenders) MUST fail-closed when `dev.files_created` / `files_modified` / `persistent_state_files` contains a gitignored path, out-of-repo path, or ephemeral-mount path without explicit waiver.
  - Destructive and pressure scripts MUST be verifiable via REAL sandboxed effects (mount-namespace remap of `/tmp`, `/dev/shm`, etc.) — not `--dry-run` or PATH-shim mocks.
  - Score changes MUST be observable via append-only audit log; concurrent writes MUST race-detect (CAS), one wins, one fails with `CAS_CONFLICT`.
  - Lifecycle log at `logs/lifecycle.jsonl` (in-repo runtime path; see Reference Source for gitignore-exception rationale and the user-text-vs-repo-layout mapping) MUST be git-trackable.
- **Gap**: 8 issues × no enforcement today × prior cycle shipped broken state to origin/master.

## Scope (Contract B)

- **Search pattern**: `score-update.sh`, `files_created`, `files_modified`, `/tmp/claude-`, `logs/`, `dry-run` (across project repo)
- **Search scope**: `/dev/shm/dev-workspace/dot-claude/**`
- **User reported (8 in-scope issues)**: R1, R2, R5a, R3, R4, W3, W5, R9 (cluster grouping per user requirement § Scope)
- **Additional found via grep**: none — all systemic-deferred issues are explicitly out of scope per user requirement § "Out of scope (deferred)"
- **All occurrences** (key file:line citations the dev must touch):
  - `.gitignore:46` (logs exception)
  - `commands/close.md:181-205` (Step 1 inspector dispatch — gate wiring point at NEW Step 1.5)
  - `commands/commit.md` (PRIMARY-path gate invocation — codex C1 belt-and-suspenders)
  - `commands/dev.md` (resumption + quota-wall call-site templates)
  - `agents/qa.md:895+` (Step 11 documentation + `requires_fixture_verification` honor)
  - `scripts/score-update.sh` (CAS + lifecycle log emission)

## Reference Source (Contract C)

- **Tier**: tier_2_verified (in-repo files inspected this session)
- **Source**:
  - `docs/dev/user-requirement-dev-20260519-211515.md` (verbatim user binding text)
  - `docs/dev/meta-assessment-20260519-161035.json` (canonical 17-row classification, codex-reviewed in prior cycle)
  - `docs/dev/dev-report-20260519-161035.json` (prior cycle artifact list with concrete file:line offenders)
  - `.gitignore` (verified by `git check-ignore -v`)
- **Location**: paths above, all within `/dev/shm/dev-workspace/dot-claude`
- **Copy allowed**: yes (paths, line numbers, AC text) — tier_2 inputs the dev may directly cite
- **Dev constraint**: the literal AC text in the user requirement document is binding. Do NOT paraphrase AC1-AC13 in commit messages or report wording; quote verbatim when referenced.

### Multi-authority conflict (resolved)

User requirement § Constraints says lifecycle log "MUST be `.claude/logs/lifecycle.jsonl` (in-repo, portable)". The repo physical root for this project IS `/dev/shm/dev-workspace/dot-claude` (the user reaches it via the `/root/.claude → /dev/shm/dev-workspace/dot-claude` symlink), so the in-repo runtime path is `logs/lifecycle.jsonl` — the leading `.claude/` is part of the user's mental path mapping, not the in-repo directory prefix. Reconciliation: the helper writes to `logs/lifecycle.jsonl` (the repo-root path), AND the `.gitignore` exception is added at that path. Dev MUST document this in the helper script header so future readers understand the user-text-vs-repo-layout mapping. Both `logs/lifecycle.jsonl` (this repo) and `.claude/logs/lifecycle.jsonl` (the user's mental path) refer to the SAME file on disk via the symlink.

## Prior Attempts (Contract D)

- **Triggered**: yes
- **Trigger source**: prior cycle 20260519-161035 shipped broken state; this cycle is the explicit remediation (NOT a retry of the same fix — a NEW harness layer to prevent recurrence)

### Attempts
- Attempt 1 — `docs/dev/ticket-20260519-161035.md` + the 4-layer-tmpfs commit chain
  - Proposed: 4-layer tmpfs pressure prevention (SessionStart banner + UserPromptSubmit pressure hook + tmp-cleanup cron + docs)
  - Changed: created 2 hooks, modified settings.json, modified `/usr/local/sbin/tmp-cleanup.sh`, created `docs/reference/tmp-cleanup-convention.md` (gitignored)
  - Outcome: shipped to origin/master with R1, R2, R5a all invisible to QA/close gates
  - Failure category: wrong_scope (prior cycle scoped the work as "implement tmpfs prevention" without scoping the harness side: "ensure shipped artifacts are actually shippable")
  - Target layer: L5 (infrastructure — runtime hooks + cron + system files)

### Novelty Check
- **This attempt's layer**: L5 (infrastructure — but at the DEV/QA HARNESS layer, not the runtime hook layer)
- **Differs from all priors**: yes — prior cycle implemented runtime-prevention hooks; this cycle implements meta-harness-prevention that audits dev outputs. The two layers are orthogonal; this cycle's deliverables COULD have caught the prior cycle's R1/R2/R5a issues if they had existed in the prior cycle.
- **Rationale**: NOT a re-attempt of tmpfs prevention. It is the systemic backfill that makes future cycles unable to ship the same class of broken artifacts. The novelty is at the close-gate / commit-gate layer (audit dev outputs before commit), not the runtime layer.

## Requirements (MoSCoW)

### Must Have

**Cluster 1 — Shippability gate (AC1-AC5)**:

- **M1**: `scripts/shippability-gate.py` (new, Python 3, chmod +x) — reads `docs/dev/dev-report-<task-id>.json`, runs three checks:
  - **Gitignore check**: every entry in `dev.files_created` and `dev.files_modified` → `git check-ignore -v --no-index <path>` (codex C10: `--no-index` is required so tracked-but-ignored paths are detected). Any hit → fail UNLESS `dev_report.gitignore_waiver[<path>]` exists with a non-empty `rationale` string.
  - **System-path check**: every entry → `realpath` to canonicalize (codex C11: symlink resolution e.g. `/root/.claude/...` ↔ `/dev/shm/dev-workspace/dot-claude/...`), then check if outside `git rev-parse --show-toplevel`. Hit → fail UNLESS `dev_report.system_file_waiver[<path>].install_manifest` references an existing file at `scripts/install/<deliverable>-install.sh` OR the waiver carries `host_local: true` with rationale.
  - **Ephemeral-mount check**: every entry in `dev.files_created`, `dev.files_modified`, AND the NEW `dev.persistent_state_files[]` field (codex C12 — required for paths described in script rationale, not just files explicitly created) → reject if path starts with `/tmp/`, `/dev/shm/`, `/run/`, OR if `realpath` resolves to a tmpfs mount. Hit → fail UNLESS `dev_report.ephemeral_state_waiver[<path>].enospc_fallback_path` is a non-ephemeral path. Also: grep every shipped script source for hardcoded ephemeral paths and emit WARNINGS (not hard-fails) for grep hits not declared in `persistent_state_files[]`.
- **M2**: Gate writes verdict JSON to `docs/dev/shippability-gate-<task-id>.json` (path IS shippable: `!docs/dev/` exception at `.gitignore:52`). Exit codes: 0 = PASS, 1 = FAIL (any cluster), 2 = INVALID_INPUT.
- **M3**: Gate invoked from **`commands/close.md` Step 1.5** (NEW step, inserted between current Step 1 and Step 2). Failure forces `CLOSE: NO - shippability_gate_failed: <reason>` regardless of QA/codex verdict.
- **M4**: **Belt-and-suspenders wiring in `commands/commit.md`** (codex C1): the PRIMARY (non-force, non-bulk) `/commit` path invokes the gate as a pre-commit check. Force/bulk paths remain audited overrides.

**Cluster 2 — Real-fixture harness (AC6-AC8)**:

- **M5**: `scripts/sandbox-destructive.sh` (new, bash, chmod +x) — uses `unshare -m` mount namespace + bind-mounts to remap `/tmp`, `/var/tmp`, `/var/log`, `/dev/shm` to sandboxed directories (codex C3: unmodified target scripts hardcode these paths), then invokes the destructive script under test WITHOUT `--dry-run`. Synthetic workspace at `mktemp -d -p /var/lib/claude-sandbox` (codex C5: scratch MUST lie outside `git rev-parse --show-toplevel`). Cleanup via `trap 'rm -rf "$SANDBOX_ROOT"' EXIT`.
- **M6**: `scripts/sandbox-pressure.sh` (new, bash, chmod +x) — uses `unshare -m` + tmpfs bind-mount with `size=<bytes>` to create a REAL >75%-full mount, then invokes the threshold hook under test with real `df`/`du` (not PATH-shim).
- **M7**: `scripts/sandbox-common.sh` (new, bash, sourced library, chmod 644) — shared helper: namespace-capability check (`unshare -m -- true` smoke test; if fail → exit `capability_unavailable=2`, NOT PASS — codex C4), sandbox-root resolution, repo-root assertion (refuses any scratch path inside `git rev-parse --show-toplevel` — codex C5), trap cleanup helper.
- **M8**: `agents/qa.md` Step 11 modification: documents the two harnesses + introduces BA-spec field `requires_fixture_verification: {harness: "destructive" | "pressure", target_script: "<path>", expected_delete: [...], expected_survive: [...], mount: "<mount>", pressure: <percent>}`. QA honors the field as a hard gate.

**Cluster 3 — Lifecycle log + CAS (AC9-AC13)**:

- **M9**: `scripts/lifecycle-log.sh` (new, bash, chmod +x) — accepts `--event <type>` (one of `score_update`, `quota_wall`, `resumption`, plus pass-through for future event types), `--payload <json-string>`, optional `--task-id <id>`, optional `--dev-session-id <id>`. Appends one JSONL line per invocation with shape `{ts, dev_session_id, event_type, agent, payload}` to `logs/lifecycle.jsonl`. Atomic single-write via O_APPEND on a single line (POSIX guarantees atomicity for PIPE_BUF-sized writes; one JSONL line < 4096 bytes by construction). Validates `--payload` is valid JSON before writing.
- **M10**: `scripts/score-update.sh` modified — adds optional `--expected-prev-score <int>` flag (codex C6: optional, NOT required — preserves backward compat). CAS logic:
  - Supplied: under flock, read current score; if != supplied → exit 3 (`CAS_CONFLICT`); else update + log.
  - Omitted: under flock, read+compare+write happens within a single flock turn, so lost-update is structurally impossible. AC11's CAS_CONFLICT exit code is observable when both test callers pass `--expected-prev-score` with the same value: flock serializes them; the second's expected won't match the first's just-written value.
  - After every successful update, invoke `bash scripts/lifecycle-log.sh --event score_update --payload '{...}'` to append the lifecycle entry. The existing `agents[agent].history[]` in `agent-scores.json` is preserved (backward compat). Score-of-truth remains `agent-scores.json`; the lifecycle log is the audit trail (codex C7 reconciliation — see Out-of-Scope Observations).
- **M11**: **`.gitignore` modification**: add narrow negation right after the `logs/` line at `:46`:
  ```
  logs/
  !/logs/
  !/logs/lifecycle.jsonl
  ```
  (codex C8: narrow exception scoped to the literal file at repo root's `logs/`, not the whole `logs/` tree.) Inline-document the rationale.
- **M12**: **Minimal orchestrator wiring** (codex C9 — AC12/AC13 require real call sites, not just helper-demo):
  - `commands/dev.md` resumption section: when orchestrator dispatches a fresh agent intended to resume cut work, add a one-line call-site template: `bash scripts/lifecycle-log.sh --event resumption --payload '{"prior_agent_id":"...","new_agent_id":"...","recovery_notes":"..."}'` BEFORE the Agent dispatch.
  - `commands/dev.md` quota-wall section: add documentation + one-line call-site template: `bash scripts/lifecycle-log.sh --event quota_wall --payload '{"agent_role":"...","agent_id":"...","tool_uses_at_cut":N,"partial_artifacts":[...]}'` to be inserted when orchestrator detects a quota-wall mid-cycle. Full detection logic is OUT of scope; the documented call template + a synthetic-event test in AC12 satisfies the AC.

### Should Have

- **S1**: `scripts/install/tmp-cleanup-install.sh` (new) — install manifest for the prior cycle's `/usr/local/sbin/tmp-cleanup.sh` so the R2 waiver demonstration in AC2 has a real example to point at, AND the prior cycle's deliverable becomes properly reproducible from this repo.

### Could Have

- **C1-could**: `scripts/rotate-lifecycle-log.sh` (manual-invocation rotation when >10MB). Defer to followup cycle.

### Won't Have (Non-Goals)

- Full orchestrator quota-wall DETECTION wiring (only call-site templates + documentation)
- Auto log rotation (manual only)
- Changes to existing 4-layer tmpfs prevention runtime hooks (`session-tmpfs-banner.sh`, `userprompt-tmpfs-pressure.sh`, `tmp-cleanup.sh`) — user requirement § Constraints explicitly forbids
- The 9 deferred systemic items (W1, W2, W4, R5b-d, R6, R7, R8) — user-acknowledged deferrals
- Forcing `/close --force` and `/commit --force/--bulk` to honor the gate (codex C1+C2 — documented as audited overrides)

## Requirements Decomposition

| ID | Source phrase (verbatim from user) | Classification | Acceptance criterion |
|----|------------------------------------|----------------|----------------------|
| R1 | "修复全部" | user-need | (parent — decomposed into R2-R14) |
| R2 | "(R1) Every entry in `dev.files_created` / `dev.files_modified` is diffed against `.gitignore`. Gitignore match → flag `unshippable_via_git`; close gate critical-fail UNLESS dev-report has `gitignore_waiver` with rationale." | user-need | AC1 (M1+M2+M3) |
| R3 | "(R2) Any path matching system locations ... requires EITHER (a) an in-repo install manifest ... OR (b) `system_file_waiver` field" | user-need | AC2 (M1+M2+M3) |
| R4 | "(R5a) Persistent-state file under ephemeral mounts ... must be flagged unless paired with an ENOSPC fallback path" | user-need | AC3 (M1+M2+M3) |
| R5 | "Deliverable shape: a Python check script under `scripts/`, invoked during QA Step 11 final-verification OR during /close (between inspectors and QA-debate; pick ONE, document)" | user-need | AC5 (M3 — picked `/close`; codex C1 added `/commit` belt-and-suspenders as M4) |
| R6 | "(R3) For destructive scheduled jobs: sandbox harness ... runs the script non-dry-run, asserts correct deletes" | user-need | AC6 (M5+M7) |
| R7 | "(R4) For threshold-conditional behaviors: pressure simulator that creates a real >threshold condition" | user-need | AC7 (M6+M7) |
| R8 | "Deliverable shape: reusable scripts under `scripts/` plus invocation pattern documented in `agents/qa.md`" | user-need | AC8 (M8) |
| R9 | "(W3) Quota-wall events ... record {ts, dev_session_id, agent_role, agent_id, tool_uses_at_cut, partial_artifacts}" | user-need | AC12 (M9+M12 quota-wall) |
| R10 | "(W5) Resumption events ... log {ts, dev_session_id, prior_agent_id, new_agent_id, recovery_notes}" | user-need | AC13 (M9+M12 resumption) |
| R11 | "(R9) Score-update transitions: replace direct score writes with append-only log entries ... Reads use latest entry; writes use Compare-And-Swap on prev_score" | user-need | AC9+AC10+AC11 (M9+M10+M11) — codex C7 reconciliation: scores.json authoritative; log is the append-only audit trail; CAS is real under flock |
| R12 | "Deliverable shape: logging module writing to `.claude/logs/lifecycle.jsonl` (in-repo, NOT /tmp). Modify `score-update.sh` to use the log; orchestrator + QA surface recent events." | user-need | AC9+AC10 (M9+M10+M11) with multi-authority conflict resolution above |
| R13 | "All deliverables live at git-tracked paths" | user-need | implicit precondition (verified by gate dogfooding itself on this cycle's dev-report) |
| R14 | "Scripts: bash or python3; chmod +x ... existing score-update.sh callers must continue working unchanged ... No new daemons" | user-need | implicit cross-cutting constraint honored by M9-M12 (optional `--expected-prev-score` per codex C6) |

## Edge Cases & Risks

- **Risk 1 — Gate dogfooding**: the gate's OWN output (verdict JSON) MUST itself be shippable. Resolution: write to `docs/dev/shippability-gate-<task-id>.json` (covered by `!docs/dev/` exception at `.gitignore:52`). Verified shippable.
- **Risk 2 — Symlink resolution false-negatives**: `/root/.claude/...` resolves to `/dev/shm/dev-workspace/dot-claude/...` via symlink. Gate's "outside repo toplevel" check MUST canonicalize via `realpath` BEFORE comparing (codex C11).
- **Risk 3 — `persistent_state_files[]` not in current dev-report contract**: codex C12 — prior cycle's `/tmp/claude-pressure-warn-<token>` was only described in script rationale, not added to `files_created`. The gate REQUIRES dev-reports to include a `persistent_state_files[]` array (new contract field) AND additionally greps the source of every shipped script for hardcoded ephemeral paths as a secondary check.
- **Risk 4 — `unshare -m` capability missing**: sandbox harness MUST detect at start and exit `capability_unavailable=2` (NOT PASS) per codex C4. QA treats this as "test could not run".
- **Risk 5 — Repo-root scratch dir**: this project repo IS `.claude/` (user-mental-path level). Sandbox-common.sh refuses any scratch path inside `git rev-parse --show-toplevel` (codex C5). Primary scratch: `/var/lib/claude-sandbox/`; if mkdir fails, exit `capability_unavailable=2`. No silent fallback to repo-internal scratch.
- **Risk 6 — `/close --force` / `/commit --force/--bulk` bypass**: codex C1 — short-circuit before inspectors / commit-gate. Documented as "audited override". NOT mitigated this cycle.
- **Risk 7 — CAS race semantics on omitted flag**: codex C6 — when callers omit `--expected-prev-score`, the read-then-write happens inside the same flock acquisition, so a single caller's view is consistent. AC11 ("concurrent invocation race → one succeeds, the other fails with CAS-conflict") is observably verifiable by passing BOTH callers the same `--expected-prev-score` value in the test fixture; flock orders them, the second's expected won't match.
- **Risk 8 — Lifecycle log path divergence**: user requirement says `.claude/logs/lifecycle.jsonl`; repo runtime path is `logs/lifecycle.jsonl`. Resolved per Reference Source section. Helper writes ONLY to `logs/lifecycle.jsonl`. Document in `scripts/lifecycle-log.sh` header.
- **Risk 9 — Gate must allow itself to ship**: the dev's own new + modified files MUST themselves pass all three gate checks. Pre-flight verification: dev MUST run the gate against its own `dev-report-20260519-211515.json` BEFORE handing off to QA. Self-dogfood is required.

## Out-of-Scope Observations

(One row per user-acknowledged deferral. None block this cycle; all recorded for cross-cycle ledger visibility per spec-20260503-091826 Section 5.4 rule 1.)

| ts | file:line | observation | security_relevant |
|----|-----------|-------------|-------------------|
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (W1) | Orchestrator set spec_path=null despite eligible spec on disk — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (W2) | test-writer skipped for STANDARD bash hooks — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (W4) | Completion report written via subagent because Write gate consumed — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (R5b) | Long-session non-saturated counter cleanup — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (R5c) | settings.json 15s timeout vs L1.5 worst-case ~16s — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (R5d) | -mtime +N doc precision (72-96h) — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (R6) | Orphan commit 34210cc bundles 68 unrelated files — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (R7) | CLAUDE_SESSION_ID not exported — user-deferred. | false |
| 2026-05-20T11:30Z | docs/dev/meta-assessment-20260519-161035.json (R8) | codex_required=false override by Stop-hook — user-deferred. | false |
| 2026-05-20T11:30Z | commands/close.md (force-override) + commands/commit.md (force/bulk) | `/close --force` and `/commit --force/--bulk` bypass the shippability gate (codex C1). Documented as audited override. Future cycle to evaluate. | false |
| 2026-05-20T11:30Z | scripts/score-update.sh (canonical reader) | Codex C7: User requirement says "Reads use latest entry; writes use CAS". `score-inject.sh` and other readers consume `agent-scores.json` directly. Reconciled: scores.json authoritative-for-reads; lifecycle log is audit-trail-only. AC9/AC10/AC11 satisfied. If user later wants log-as-source-of-truth, projection script in separate cycle. | false |

## Acceptance Criteria

These map 1:1 to user-requirement AC1-AC13. Executable JSON form at `docs/dev/acceptance-criteria-20260519-211515.json` (BA Step 10).

### AC1: Shippability gate detects gitignored entries
- GIVEN fixture `tests/fixtures/dev-report-ac1.json` listing `docs/reference/test.md` in `dev.files_created` AND no `gitignore_waiver`
- WHEN `python3 scripts/shippability-gate.py --dev-report <fixture>` runs
- THEN exit code = 1; stdout JSON includes `{"verdict":"fail","reason":"unshippable_via_git","paths":["docs/reference/test.md"]}`; gate-verdict JSON written to `docs/dev/shippability-gate-ac1.json`

### AC2: Shippability gate detects out-of-repo system paths
- GIVEN fixture listing `/usr/local/sbin/foo.sh` in `dev.files_modified` AND no `system_file_waiver`
- WHEN gate runs
- THEN exit code = 1; reason includes `out_of_repo`; paths include `/usr/local/sbin/foo.sh`

### AC3: Shippability gate detects ephemeral persistence
- GIVEN fixture listing `/tmp/claude-pressure-warn-abc` in `dev.persistent_state_files` AND no `ephemeral_state_waiver.enospc_fallback_path`
- WHEN gate runs
- THEN exit code = 1; reason includes `ephemeral_persistence`

### AC4: Gate would have caught the prior cycle's defects
- GIVEN `tests/fixtures/dev-report-20260519-161035-augmented.json` = the prior cycle's dev-report with `persistent_state_files: ["/tmp/claude-pressure-warn-<token>"]` added (augmentation is part of this AC's fixture)
- WHEN gate runs
- THEN exit code = 1; all three reasons fire (`unshippable_via_git` for `docs/reference/tmp-cleanup-convention.md`, `out_of_repo` for `/usr/local/sbin/tmp-cleanup.sh`, `ephemeral_persistence` for `/tmp/claude-pressure-warn-*`). Confirms the gate would have blocked the prior cycle's close.

### AC5: Gate wiring is automatic in /close
- GIVEN `commands/close.md` post-modification
- WHEN grepped for `shippability-gate` invocation
- THEN exactly one invocation site between current Step 1 and Step 2 sections; verdict failure propagates to `CLOSE: NO - shippability_gate_failed: <reason>`

### AC6: Destructive sandbox harness exercises real script
- GIVEN `scripts/sandbox-destructive.sh --target /usr/local/sbin/tmp-cleanup.sh --expected-delete '*.tmp' --expected-survive '.last-cleanup'`
- WHEN run on a system with `unshare -m` capability
- THEN harness creates synthetic files in sandboxed `/tmp` (via mount-namespace bind-mount), invokes the script NON-dry-run, asserts the `*.tmp` files were deleted and `.last-cleanup` preserved; exit code = 0 on pass, 1 on assertion failure, 2 on `capability_unavailable`

### AC7: Pressure sandbox harness manufactures real >75% mount
- GIVEN `scripts/sandbox-pressure.sh --target hooks/userprompt-tmpfs-pressure.sh --mount /tmp --pressure 80`
- WHEN run
- THEN harness mounts a bounded tmpfs, fills to 80%, invokes the hook with REAL `df`/`du`; asserts a `WARN` line emitted in hook output; exit code = 0 on pass

### AC8: agents/qa.md references both harnesses + honors flag
- GIVEN `agents/qa.md` post-modification
- WHEN grepped for `sandbox-destructive.sh`, `sandbox-pressure.sh`, `requires_fixture_verification`
- THEN all three strings present; Step 11 documentation shows the QA invocation pattern for the flag

### AC9: Lifecycle log writes valid JSONL
- GIVEN `bash scripts/lifecycle-log.sh --event score_update --payload '{"agent":"dev","prev":50,"new":58}'`
- WHEN invoked
- THEN `logs/lifecycle.jsonl` exists, the last line parses as JSON with keys `{ts, dev_session_id, event_type, agent, payload}`

### AC10: score-update.sh emits lifecycle entry
- GIVEN existing invocation `score-update.sh --agent dev --event qa_first_pass`
- WHEN invoked
- THEN `logs/lifecycle.jsonl` has a NEW line with `event_type=score_update` and payload `{agent, event, prev_score, new_score, delta, reason}`

### AC11: score-update.sh CAS detects races
- GIVEN two parallel invocations `score-update.sh --agent dev --event qa_first_pass --expected-prev-score 50 & score-update.sh --agent dev --event qa_first_pass --expected-prev-score 50 &; wait`
- WHEN both run concurrently
- THEN exactly one returns exit code 0; the other returns exit code 3 (`CAS_CONFLICT`); only one new lifecycle log entry for the successful winner; `agent-scores.json` reflects single increment

### AC12: orchestrator quota-wall event
- GIVEN `bash scripts/lifecycle-log.sh --event quota_wall --payload '{"agent_role":"qa","agent_id":"qa-1","tool_uses_at_cut":18,"partial_artifacts":["docs/dev/qa-partial.json"]}'`
- WHEN invoked as documented in `commands/dev.md` (call-site template, not auto-detection)
- THEN `logs/lifecycle.jsonl` has a line with `event_type=quota_wall` and full payload; `commands/dev.md` grep finds the documented call site

### AC13: orchestrator resumption event
- GIVEN `bash scripts/lifecycle-log.sh --event resumption --payload '{"prior_agent_id":"qa-1","new_agent_id":"qa-2","recovery_notes":"resuming after quota cut"}'`
- WHEN invoked as documented in `commands/dev.md` resumption section
- THEN `logs/lifecycle.jsonl` has a line with `event_type=resumption`; `commands/dev.md` grep finds the documented call site

## Technical Hints

**Files to create (6 must + 1 should = 7)**:
- `scripts/shippability-gate.py` (Python 3, chmod +x) [M1]
- `scripts/sandbox-destructive.sh` (bash, chmod +x) [M5]
- `scripts/sandbox-pressure.sh` (bash, chmod +x) [M6]
- `scripts/sandbox-common.sh` (bash, sourced lib, chmod 644) [M7]
- `scripts/lifecycle-log.sh` (bash, chmod +x) [M9]
- `scripts/install/tmp-cleanup-install.sh` (bash, chmod +x) [S1]

**Files to modify (6)**:
- `scripts/score-update.sh` (add `--expected-prev-score`, CAS inside flock, lifecycle-log invocation after success) [M10]
- `commands/close.md` (insert Step 1.5 shippability-gate invocation) [M3]
- `commands/commit.md` (PRIMARY-path gate invocation) [M4]
- `commands/dev.md` (insert call-site templates for quota_wall and resumption) [M12]
- `agents/qa.md` (Step 11 documentation: `requires_fixture_verification` consumption + sandbox harness patterns) [M8]
- `.gitignore` (add `!/logs/` and `!/logs/lifecycle.jsonl` exceptions after `:46`) [M11]

**Related patterns**:
- `scripts/score-update.sh` already uses bash+inline-python+flock — extend that pattern for CAS
- `commands/close.md` Step 1 already uses orchestrator Agent dispatch — Step 1.5 uses a direct Bash invocation (lighter; gate is deterministic, no LLM call needed)
- `agents/qa.md` Step 11 already invokes external scripts — add the two sandbox scripts to that pattern

**Constraints**:
- Existing `score-update.sh` callers (no `--expected-prev-score`) MUST keep working unchanged — backward-compat binding
- `commands/close.md` Step 1 inspector dispatch MUST NOT change shape — gate runs AFTER inspectors complete, BEFORE QA debate dispatch
- Gate's own output JSON MUST land in `docs/dev/` (the only verified-shippable docs/ subtree per `.gitignore:52`)
- `unshare -m` is Linux-only; if QA runs on macOS or in a no-namespace container, sandbox harnesses MUST emit `capability_unavailable=2`, never silent-PASS
- New scripts may need permissions in `settings.json` allowlist if invoked as `Bash` calls from dispatch contexts — codex C13 minor finding
- `realpath` (coreutils) used for symlink resolution
- `git check-ignore --no-index` flag required so the gate detects paths that are not (yet) tracked but ARE ignored — codex C10

**Self-dogfood requirement**: dev MUST run `python3 scripts/shippability-gate.py --dev-report docs/dev/dev-report-20260519-211515.json` against THIS cycle's own dev-report BEFORE handing to QA. The dev-report MUST list all 7 new + 6 modified files under `files_created`/`files_modified`, MUST list empty `persistent_state_files: []`, MUST require no waiver fields (because all 13 files are in-repo, none on ephemeral mounts, none gitignored after the `.gitignore` exception lands). Self-dogfood PASS is a precondition for QA invocation.

## Codex Adversarial Consultation Summary

Codex (gpt-5.5, xhigh reasoning) consulted on three architecture decisions + 5 questions. Returned 13 findings: 12 `in_scope_real_bug` (all applied), 1 `in_scope_minor` (applied as dev hint). 0 OBSERVATION_ONLY, 0 nitpick, 0 rejected. Detailed disposition in `context-20260519-211515.json` § `codex_consult.findings[]`.
