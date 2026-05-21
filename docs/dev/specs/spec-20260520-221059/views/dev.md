<!-- AUTO-GENERATED VIEW for dev | source: docs/dev/specs/spec-20260520-221059.md | extracted: 2026-05-21T00:00:00Z -->

# dev view of spec-20260520-221059

**Monolith**: docs/dev/specs/spec-20260520-221059.md
**Extraction**: content-block level (no section-level mapping)

---

# Spec: Unresolved issues backlog from session 88dfdcea — TOP 3 cluster stranded by scope hot-swap + post-session confession

**Pipeline**: ba → dev → qa
**Session**: spec-20260520-221059
**Created**: 2026-05-20T22:10:59Z

## Implementation scope (per spec Section 5)

### Layer A — implementation items (harness/hook/gate)

- **R1** — Shippability gate: every entry in `dev-report.dev.files_modified`/`files_created` must be diffed against `.gitignore`. Gitignore match → critical fail UNLESS dev-report has `gitignore_waiver`. This is the gate that would have caught `docs/reference/tmp-cleanup-convention.md` being gitignored (the L3 doc that AC8 passed but won't ship via git).
- **R2** — System-file install-manifest gate: any path matching `/usr/local/`, `/etc/`, `/opt/`, `/var/`, or outside `git rev-parse --show-toplevel` requires either an in-repo install manifest (`scripts/install/<deliverable>-install.sh`) OR explicit `system_file_waiver`. This is what would have caught `/usr/local/sbin/tmp-cleanup.sh` being single-host-only.
- **R5a** — Counter file ephemeral-mount protection: persistent-state files under `/tmp/`, `/dev/shm/`, `/run/` flagged unless paired with ENOSPC fallback. Catches the L1.5 counter file living on the very mount it's supposed to protect.
- **R3** — Real-fixture destructive sandbox harness: replaces `--dry-run`-only verification with synthetic-file sandbox + non-dry-run script invocation + assertion of correct deletes + preserved hard-exclusions.
- **R4** — Pressure-simulation harness: manufactures real `>75%` mount condition (not PATH-shim mock-df), captures actual hook output under real condition. PATH-shim allowed at unit-level only; AC verification of threshold behaviors requires real fixture.
- **W3** — Quota-wall event log: when subagent dispatch is cut by API quota, orchestrator records `{ts, dev_session_id, agent_role, agent_id, tool_uses_at_cut, partial_artifacts}` to lifecycle log. This session had at least 5 such silent cuts, none escalated.
- **W5** — Agent-resumption event log: when orchestrator dispatches a fresh agent to resume cut work, record `{ts, dev_session_id, prior_agent_id, new_agent_id, recovery_notes}`. Currently all resumptions are silent.
- **R9** — Score-update CAS + lifecycle log: replace direct score writes with append-only log entries `{ts, agent, event, prev_score, new_score, delta, actor, reason}`. Reads use latest entry; writes use Compare-And-Swap on prev_score. User observed score drift `dev 81→73` between events with no event-log explanation.

### Layer B implementation items

5. **Codex QA-stage in_scope_minor follow-ons from 4-layer prevention** — counter file on /tmp ENOSPC fallback (related to R5a above), long-session non-saturated counter sweep reset (the L2 cleanup wipes counter mtime), L1.5 worst-case ~16s exceeds settings 15s timeout, `-mtime +N` documentation precision (>3d actually means 72-96h depending on cron landing).

### Layer C — deferred implementation items

- **W1** — Spec auto-detect rule violated by orchestrator when newest spec was unrelated to current /dev request; rule should be `fail/ask` instead of silent override.
- **W2** — test-writer silent skip when complexity_tier ≥ STANDARD; dispatch gate should route STANDARD-tier bash to shellcheck+Bats+fixture OR record explicit waiver, no silent skip.
- **W4** — orchestrator Write gate (1/turn) caused completion-report writes to be subagent-delegated multiple times; gate redesign needed.
- **R5b** — long-session (>7d) non-saturated counter (`n<3`) gets cleaned by Layer-2 sweep → rate-limit silently resets. TTL-based sweep with explicit reset-event semantics needed.
- **R5c** — L1.5 ~16s worst-case vs settings.json hook-level 15s timeout. Bump to 20s OR trim L1.5 budget to ≤12s. (Marked one-off in meta-assessment but real.)
- **R5d** — `-mtime +N` documentation precision: convention doc says ">3d" but GNU find semantics mean strictly more than N full 24h periods. Update tmp-cleanup-convention.md to "older than N×24h, granularity 24h" + add boundary test.
- **R6** — orphan commit `34210cc` (and now patterns of similar dumps) pollute history with cross-subsystem mega-commits. /dev preflight should block or baseline dirty/orphaned pre-cycle state; baseline ref recorded in final report.
- **R7** — `CLAUDE_SESSION_ID` not exported in orchestrator shell; push token written with `session_id="unknown"`. Init+export at orchestrator-shell startup; fail uploads if missing rather than writing 'unknown'.
- **R8** — Stop-hook codex-override: when orchestrator passed `codex_required: false` to BA iter1 resumption, harness Stop-hook forced codex invocation anyway. Explicit task flags should override resume/Stop-hook defaults unless a hard-blocking hook emits visible reason + user confirmation.

### Layer D — cleanup tasks

- **D3** — `docs/reference/tmp-cleanup-convention.md` (L3 deliverable from cycle 161035) is still gitignored. AC8 verified existence on local disk; fresh clones get nothing. Add a `.gitignore` exception OR move file to a non-ignored path.
- **D4** — `/tmp/update-FgI2V5.md` and `/tmp/update-wflOHq.md` lingering temp `/spec-continue --temp` files. They have no consumers after their respective /commit runs; will be swept by tmp-cleanup at >7d but currently occupying tmpfs.
- **D5** — Duplicate sibling file `docs/dev/prompt-inspector-report-20260519-211515-redev9items.json` left over from the write-guard workaround pattern (write to sibling → cp over canonical). Should be deduplicated.

### Layer E — hook/process implementation gaps

- **E2** — Subagent "wrote report but didn't" silent-failure pattern. Multiple instances where inspector subagents reported "Report written" but no file appeared on disk (cleanliness + prompt during cycle 211515 close, before artifact recovery). Different from write-guard blocking: subagents CLAIMED success. Possible causes: tool-policy write-prefix gap, hook intercepting silently, or subagent fabrication. Needs root-cause investigation + a "subagent claim verification" check (orchestrator validates claimed deliverables before proceeding).
- **E6** — Single-/commit-grant-per-orchestrator-dispatch limit. changelog-analyst surfaced this: the guard unlinks grant after first commit, so multi-commit cycles (feature + orphan + nested repo) require either (a) /commit wrapper writes N grants up-front, or (b) contract explicit "one commit per dispatch". Real gap, blocks the orphan-capture pattern in single /commit invocations.
- **E7** — No hook enforces R9 reversal-citation rule. agents/changelog-analyst.md got the rule (item 9 from 9-item retrospective landed) but there's no commit-message-validate hook that fails commits without "Reverses <SHA>:" citation when needed. The rule is documentation-only; no teeth.
- **E15** — TodoWrite canonical-validation ceremony cost. Every step transition requires a separate TodoWrite call due to "one completion per call" hook rule. Multiple wasted tool calls per cycle just for state-machine bookkeeping. Either widen the rule (allow batched transitions) or eliminate the per-call requirement.

### Layer J — known-but-uncommunicated production bugs

- **J1** — `refs/checkpoints/master` is now CORRUPTED. The subagent that recovered the 5 lost artifacts noted: the latest checkpoint commit `f63b1a7` captured 92-byte stderr-redirect stub files from a failed first restoration attempt. The corrupted state is still in the checkpoint ref. Future recoveries from this ref will retrieve garbage for these paths. Needs cleanup or rewind.
- **J2** — `/push` command spec hardcodes `SESSION_ID="88dfdcea-706b-457f-b6c1-07bd1dac0b8f"` (this session's UUID). It was baked in via UserPromptSubmit hook injection at /push invocation. If session changes (next /push in another session), the spec literal is wrong. Real bug: the spec body should reference an env var, not a literal UUID.
- **J3** — L2 cleanup script `/usr/local/sbin/tmp-cleanup.sh` is in NO repo. If host filesystem is wiped or reinstalled, 12KB of cleanup logic vanishes. R2's install-manifest IS the fix, but the urgent failure mode is real today. The script needs a mirror in-repo at `scripts/install/` even before R2's automated gate lands.
- **J5** — `hooks/tests/__pycache__/` files appear in `git status` output. Python bytecode shouldn't be tracked. Check `.gitignore` for `__pycache__/` exclusion.
- **J6** — Score-update ceiling=100 silently caps deltas (E3 above) AND it caps MULTIPLE TIMES PER CYCLE. dev hit 100 ceiling, then took penalties bringing it down, then rose back to 100, capped again. Each capping is a separately-lost positive signal. The schedule needs to track an "uncapped delta" running total or remove the ceiling.

### Layer O — codex/subagent-surfaced fixes

- **O5** — codex during 9-item retrospective dev stage flagged: F4 (mktemp in /tmp during /tmp cleanup), F5 (dry-run truncation at 200 candidates). These were applied during dev. But codex F1 (blocking flock under contention) was applied as `flock -x -w 1` — meaning under heavy contention the L1.5 hook now SKIPS rather than waits. Is "skip when contended" the right behavior? Untested under contention.

### Layer Q — hook/policy/config system gaps

- **Q1** — orchestrator-gate's "consecutive same-tool" counting logic is brittle. After multiple TodoWrite calls, when does the streak reset? Tested implicitly multiple times this session.
- **Q2** — pretool-write-guard blocks overwrites SILENTLY (no stderr message to subagent). Subagents claim "Report written" because their internal logic completed; the disk state lies. Related to E2 (silent-failure pattern) but specifically a guard-design choice.
- **Q3** — The bash-safety hook patterns are NOT documented user-visibly. When a Bash command blocks, the message says "BLOCKED: rm is forbidden" but doesn't enumerate all forbidden patterns. Operator has to read source to know what's allowed.
- **Q5** — CLAUDE.md was modified this cycle but no consistency test ran. Cross-references to file paths/sections may now be broken. Linter for CLAUDE.md consistency would help.

### Layer R — execution side-effects + housekeeping debt

- **R1ext** — `/var/tmp/codex-outputs/` accumulates files from every codex invocation. Total disk used? Not measured. Cleanup policy? Unknown. Could grow unboundedly.
- **R2ext** — `/tmp/agentic-commit/` accumulates push grants, commit grants, manifests, sentinel files, audit logs. Multiple sub-directories. No retention policy beyond tmp-cleanup.sh sweep at >7d.
- **R3ext** — `/root/.codex/memories/` mentioned by codex skill (workspace-write sandbox). Was anything written there this session? Not surveyed.
- **R4ext** — `/root/.claude/projects/-dev-shm-dev-workspace-dot-claude/<session-uuid>/tool-results/` files persist across the session. These contain large tool outputs (the recovery subagent's transcript, the meta-assessment QA outputs, etc.). Size and retention untracked.
- **R5ext** — Multiple Bash env vars I manually exported leak to child processes: `CLAUDE_SESSION_ID`, `CLAUDE_PUSH_REQUEST_ID`, `CLAUDE_PROJECT_DIR`. None persist beyond subshell but could be observed by hooks running in those subshells.

