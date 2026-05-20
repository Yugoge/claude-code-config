# User Requirement — dev-20260519-211515

## Verbatim user final selection

> 修复全部 (selected from options: "TOP 1 / TOP 1+3 / 三个全做 / 看报告")

User chose "fix all 3 TOP categories" after reviewing a 17-row meta-assessment of systemic issues from the prior cycle (task-id 20260519-161035, the 4-layer tmpfs prevention). Meta-assessment was produced by QA+codex; report at `docs/dev/meta-assessment-20260519-161035.json`.

## Scope (binding) — 8 of 17 systemic issues, grouped into 3 deliverables

### Cluster 1 — Shippability gate (issues R1 + R2 + R5a)

Add a QA-side post-cycle check that verifies dev outputs are actually **shippable**:
- (R1) Every entry in `dev.files_created` / `dev.files_modified` is diffed against `.gitignore`. Gitignore match → flag `unshippable_via_git`; close gate critical-fail UNLESS dev-report has `gitignore_waiver` with rationale.
- (R2) Any path matching system locations (`/usr/local/`, `/etc/`, `/opt/`, `/var/`, paths outside `git rev-parse --show-toplevel`) requires EITHER (a) an in-repo install manifest like `scripts/install/<deliverable>-install.sh`, OR (b) `system_file_waiver` field in dev-report.
- (R5a) Persistent-state file under ephemeral mounts (`/tmp/`, `/dev/shm/`, `/run/`) must be flagged unless paired with an ENOSPC fallback path; tmpfs-as-persistence is rejected.

Deliverable shape: a Python check script under `scripts/`, invoked during QA Step 11 final-verification OR during /close (between inspectors and QA-debate; pick ONE, document).

### Cluster 2 — Real-fixture verification harness (issues R3 + R4)

Replace `--dry-run`-only verification and PATH-shim mocking with sandboxed real-effect tests:
- (R3) For destructive scheduled jobs: sandbox harness that creates synthetic files at target paths in an isolated workspace, runs the script non-dry-run, asserts correct deletes + preserved hard-exclusions.
- (R4) For threshold-conditional behaviors: pressure simulator that creates a real >threshold condition (e.g., bounded tmpfs mount or controlled scratch dir) and captures actual hook output under real (not mocked) conditions.

Deliverable shape: reusable scripts under `scripts/` plus invocation pattern documented in `agents/qa.md`.

### Cluster 3 — Event-sourced lifecycle log (issues W3 + W5 + R9)

Append-only event log for agent lifecycle events:
- (W3) Quota-wall events: when a subagent is cut by API quota, record {ts, dev_session_id, agent_role, agent_id, tool_uses_at_cut, partial_artifacts}.
- (W5) Resumption events: when orchestrator re-dispatches a fresh agent to resume cut work, log {ts, dev_session_id, prior_agent_id, new_agent_id, recovery_notes}.
- (R9) Score-update transitions: replace direct score writes with append-only log entries {ts, agent, event, prev_score, new_score, delta, actor, reason}. Reads use latest entry; writes use Compare-And-Swap on prev_score (mismatch → fail).

Deliverable shape: logging module writing to `.claude/logs/lifecycle.jsonl` (in-repo, NOT /tmp). Modify `score-update.sh` to use the log; orchestrator + QA surface recent events.

## Acceptance criteria

### Cluster 1 — Shippability gate
- AC1: Gate fails closed when a `dev.files_created` entry is gitignore-matched AND no `gitignore_waiver` field. Verifiable: fixture dev-report with `docs/test.md` (matched by gitignore:66) → fail with reason citing the gitignored path.
- AC2: Gate fails closed when a `dev.files_modified` entry is outside `git rev-parse --show-toplevel` AND no `system_file_waiver`. Verifiable: fixture referencing `/usr/local/sbin/foo.sh` → fail.
- AC3: Gate fails closed for ephemeral-mount persistence file without ENOSPC fallback. Verifiable: fixture referencing `/tmp/claude-pressure-warn-*` → fail or pass-with-explicit-ack.
- AC4: Gate passes silently when all files in-repo + not gitignored. Verifiable: re-applied to prior cycle 20260519-161035, this gate would have FAILED — confirms detection of L3+L2+R5a defects we missed.
- AC5: Gate wiring requires no manual orchestrator action — invoked via QA Step 11 OR close.md hook (chosen path documented).

### Cluster 2 — Real-fixture harness
- AC6: Sandbox harness, given destructive script + expected-survive + expected-delete lists, runs non-dry-run against synthetic fixtures and reports pass/fail. Verifiable: harness against `/usr/local/sbin/tmp-cleanup.sh` with synthetic /tmp content; assert correct deletes + preserved hard-exclusions.
- AC7: Pressure-simulation harness manufactures a real >75% mount condition and captures actual hook output. Verifiable: simulate /tmp >75%, invoke `hooks/userprompt-tmpfs-pressure.sh`, assert real warning + top-5 du block from non-mocked du.
- AC8: Both harnesses referenced from `agents/qa.md`; BA-spec carries `requires_fixture_verification: true` flag that QA honors.

### Cluster 3 — Lifecycle log
- AC9: Append-only log at `.claude/logs/lifecycle.jsonl` records {ts, dev_session_id, event_type, agent, payload}. Verifiable: synthetic event → grep log.
- AC10: `score-update.sh` writes a lifecycle entry on every score change with {ts, agent, event, prev_score, new_score, delta, reason}. Verifiable: invoke → assert entry written.
- AC11: `score-update.sh` uses Compare-And-Swap on prev_score: concurrent invocation race → one succeeds, the other fails with CAS-conflict. Verifiable: two concurrent calls → assert exactly one wins.
- AC12: Orchestrator writes `quota_wall` lifecycle entry when a subagent dispatch hits known quota-wall error. Verifiable: synthetic quota-wall → assert entry.
- AC13: Orchestrator writes `resumption` lifecycle entry when dispatching a fresh agent intended to resume cut work. Verifiable: synthetic resumption → assert entry.

## Constraints (binding)

- All deliverables live at git-tracked paths (do NOT repeat the R1 gitignore mistake — none under `docs/`)
- Scripts: `#!/usr/bin/env bash` or `#!/usr/bin/env python3`; chmod +x
- Lifecycle log location MUST be `.claude/logs/lifecycle.jsonl` (in-repo, portable)
- Existing working hooks/scripts from prior cycle (session-tmpfs-banner.sh, userprompt-tmpfs-pressure.sh, tmp-cleanup.sh) MUST NOT change behavior — only `score-update.sh` + orchestrator dispatch flow change
- `~/.claude/scripts/score-update.sh` callers must continue working unchanged (CAS + log are transparent additions)
- No new daemons / Prometheus / monitoring stacks — additive only

## Out of scope (deferred)

- W1 (spec auto-detect override)
- W2 (test-writer skipped for STANDARD bash)
- W4 (orchestrator Write gate)
- R5b (long-session counter reset)
- R5c (timeout 15s→20s)
- R5d (mtime doc precision)
- R6 (orphan commit prevention)
- R7 (CLAUDE_SESSION_ID export)
- R8 (Stop-hook codex override)

## Source of truth

`docs/dev/meta-assessment-20260519-161035.json` — canonical 17-row classification. BA MUST read it.