<!-- AUTO-GENERATED VIEW for qa | source: docs/dev/specs/spec-20260520-221059.md | extracted: 2026-05-21T00:00:00Z -->

# qa view of spec-20260520-221059

**Monolith**: docs/dev/specs/spec-20260520-221059.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> **Pipeline**: ba → dev → qa

# Spec: Unresolved issues backlog from session 88dfdcea — TOP 3 cluster stranded by scope hot-swap + post-session confession

**Pipeline**: ba → dev → qa
**Session**: spec-20260520-221059
**Created**: 2026-05-20T22:10:59Z

## Verification scope (per spec Section 5)

### Layer B — verification follow-ons

1. **Artifact-loss root cause never investigated** — 5 cycle artifacts disappeared from disk mid-session and were recovered via `refs/checkpoints/master`. The orchestrator never identified WHICH process/hook/script deleted them. Likely candidates: a hook with `rm`, a cleanup script with too-wide scope, cross-session `git restore` or `git clean`. Until root cause is found, this is a defense-not-fortified-but-tested timebomb.
2. **Cross-session work falsely attributed to current cycle** — commits `28a1e85` and `97585ca` were already on disk before the current /commit; the orchestrator claimed they belonged to the 9-item retrospective but cannot prove their content matches the 9-item scope. There may be unrelated work bundled in those SHAs that landed on origin/master under this cycle's banner.
3. **AskUserQuestion empty-answer bug** — orchestrator prompted user for rating twice (post-/redev, post-/close YES) and both times received empty answer payload. Treated as "skip" per spec, but may indicate the hook/UI framework loses rating responses. Worth investigating the AskUserQuestion → orchestrator data path.
4. **Item 8 from 9-item retrospective NOT addressed** — `ACCEPTABLE-DEBT`: 23 leaked production playwright-mcp processes. User-authorized via `就地部署`, OOS-logged. Still leaking resources right now.

### Layer C — verification follow-ons

- **W1** — Spec auto-detect rule violated by orchestrator when newest spec was unrelated to current /dev request; rule should be `fail/ask` instead of silent override.
- **W2** — test-writer silent skip when complexity_tier ≥ STANDARD; dispatch gate should route STANDARD-tier bash to shellcheck+Bats+fixture OR record explicit waiver, no silent skip.
- **W4** — orchestrator Write gate (1/turn) caused completion-report writes to be subagent-delegated multiple times; gate redesign needed.
- **R7** — `CLAUDE_SESSION_ID` not exported in orchestrator shell; push token written with `session_id="unknown"`. Init+export at orchestrator-shell startup; fail uploads if missing rather than writing 'unknown'.
- **R8** — Stop-hook codex-override: when orchestrator passed `codex_required: false` to BA iter1 resumption, harness Stop-hook forced codex invocation anyway. Explicit task flags should override resume/Stop-hook defaults unless a hard-blocking hook emits visible reason + user confirmation.

### Layer D — verification of cleanup

- **D2** — Step 7 false positive: `docs/dev/specs/spec-20260518-225715.md` (mascot scoring spec) contains a "20260519-211515" historical cross-reference; the new Step 7 algorithm flags it as a non-linked continuation spec for this cycle. The algorithm is correct; the data is polluted. Ghost cycle pollution cleanup needed.
- **D6** — 15 cleanliness-inspector minor findings from cycle 20260519-211515: 7 `_ac{N}_verify.sh` files use underscore-prefix breaking `test_*` convention, 6 of them are orphaned (`_final_sweep.sh` does not invoke them), 1 permission anomaly (644 vs canonical 755). Inspector recommended rename to `test_*` OR archive after cycle closes.
- **D7** — Silent quota-wall handling: orchestrator absorbed at least 5 quota cuts (`BA iter1 → cut → resume`, `QA final-verification → cut → resume`, push-analyst rate-limit, dev cycle agent → cut, /close style-inspector → cut) without escalation. User had no visibility into when subagent reasoning quality may have degraded.

### Layer E — process verification gaps

- **E1** — Orchestrator's missing "shippability cross-check" reflex at every stage (not just an automated gate). Beyond R1's tool implementation, the orchestrator never paused to ask "will this actually ship via git?" at QA/close/commit. R1 fixes the gate; this fix is about orchestrator MENTAL MODEL. Even after R1 lands, orchestrator should also internalize the check as a pre-/commit reflex.
- **E3** — Score-system ceiling=100 truncates positive deltas. dev hit 100 ceiling, subsequent +6 / +15 events silently capped. Net signal lost. Score-system needs either remove ceiling, log uncapped values, or surface "would have been +N but ceiling-capped" in the event log (R9 may or may not cover).
- **E4** — Codex invocation count + cost not tracked. Across this session codex was invoked ~15-20+ times via Skill(codex). Each is a separate GPT-5.5 API call. No accounting anywhere. Affects cost-aware policy decisions (when to invoke codex vs when to skip).
- **E8** — L1.5 hook ENOSPC fallback untested. Counter file write would fail under genuine /tmp ENOSPC; hook designed non-blocking but the ENOSPC fallback path was never exercised. R5a covers the redesign; this is the testing gap.
- **E9** — `.git/lost-found` / `git fsck --unreachable` blobs never investigated as part of artifact-loss forensics. The subagent recovered via `refs/checkpoints/master` but didn't search lost-found. May contain additional copies of historically-lost work.
- **E11** — QA scoring imbalance for messenger-vs-author cases. QA net -6 this cycle when QA was messenger of inspector finding (not QA's own analysis failure). The schedule treats "CLOSE: NO because QA dissented" identically to "CLOSE: NO because inspector caught issue post-QA". A "QA-caught-vs-QA-missed" distinction is missing.
- **E12** — The "scope hot-swap" mid-cycle is itself unprecedented and unrecorded. requirement doc was rewritten mid-/redev — was it user intent, tool accident, or session-compaction artifact? Process didn't record WHY scope changed or WHO did it. Future cycles need a "scope-change event log" to prevent silent scope diff.
- **E13** — Orchestrator claims-vs-reality drift. Multiple "this is done" claims turned out false in retrospect: "all 6 cycle artifacts verified" before they vanished; "inspector reports written" before they were found missing; "subagent reported success" before the write was silently blocked. Subagent-claim-verification gap (orchestrator should re-check claimed deliverables on disk before accepting subagent reports as ground truth).
- **E14** — Inspector dispatch authority gap during /close debate. close.md restricts inspector dispatch to /close-orchestrator itself, not QA-internal. If QA debate concludes "we need to re-run an inspector after the fix" (which happened this cycle), QA cannot dispatch — only the next outer orchestrator can. Process inflexibility.

### Layer F — testing-coverage gaps (knowing-vs-verifying)

- **F1** — 4-layer prevention cycle's empirical effectiveness is not formally captured. We saw `/var/log/tmp-cleanup.log` show `freed=445900K, freed_total=448MiB` from real cron runs — strong evidence the prevention works. But no test/regression artifact records "verified PASS in production" with timestamps. R3's sandbox harness wouldn't have caught this, but a "production effectiveness log" would.
- **F2** — The Standard 6 violation at commit.md:130 was caught by style-inspector — proving the inspector works. But there's no test confirming that style-inspector WILL catch newly-introduced CJK in command files going forward. Self-deployment of the 9-item retrospective fixes was successful but unwitnessed by a regression suite.
- **F3** — The single-process exec pattern (item 1 fix) was used to push 4d9f9f5 — proving the sentinel gate works. But no test verifies the gate self-aborts when sentinel is MISSING/STALE/FAIL/mismatched. The negative cases are untested in production.
- **F4** — The new push-analyst TTL 180s (item 4) was applied this session — but no measurement confirms 180s is empirically sufficient. Cold-path subagent dispatch latency varies; the TTL may still be too tight on slow hosts.

### Layer G — cycle-cleanup work (multiple parallel cycles need closure)

- **G1** — Cycle `d1e94e`: artifacts on disk include {ticket, context, dev-report, qa-report, completion, close-report-d1e94e-prior} but no close-report-d1e94e.md (deleted). State ambiguous — was it closed? rolled back? lost?
- **G2** — Cycle `75463e-DH`: D+H allowlist consolidation work. Ticket + context untracked on disk. Likely the originator of the `hooks/lib/allowlist.py` consolidation that ended up in our cycle 211515 work. Did it formally close?
- **G3** — Cycle `20260520-085647-d1722b`: inspector reports + close-report all present untracked. Looks like a recently-completed cycle whose artifacts never got committed.
- **G4** — Outer-repo `/root/docs/dev/specs/spec-20260520-051938.md`: untracked spec in the OUTER repo, no companion cycle artifacts visible. Orphaned spec.
- **G5** — `acceptance-criteria-20260519-211515.json` on disk is stale D+H content from a parallel cycle that polluted this task-id slot. Either delete or rename to the right cycle.
- **G6** — `prompt-inspector-report-20260519-211515-redev9items.json` is a sibling duplicate of `prompt-inspector-report-20260519-211515.json` (write-guard workaround). Deduplicate.
- **G7** — `style-inspector-report-20260519-211515-recheck.json` and `prompt-inspector-report-20260519-211515-recheck.json` exist (visible in /push working-tree listing) — extra inspector runs whose origin is unclear. Investigate or delete.

### Layer J — verification of production-bug fixes

- **J4** — The 22 dirty working-tree files include `docs/dev/INDEX.md` and `.claude/specs/spec-20260518-225715/cp-state-{dev,qa}.json`. The INDEX modification means future docs/dev/ lookups via index are stale. The cp-state JSONs are checkpoint state from this session; if a future /dev cycle relies on SPEC_ID `spec-20260518-225715`, it would NOT see this session's checkpoint progress.

### Layer L — orchestrator's silent decisions during execution

- **L1** — Multiple codex `out_of_scope` rejections never surfaced to user. Codex flagged at least 4 adjacent attack vectors during 9-item cycle QA (codex #1 "Bash self-authoring sentinel" was rejected as adjacent attack vector outside threat model). Each rejection is a potential issue the orchestrator unilaterally dismissed under Rule 3/4. List of all codex_out_of_scope rejections across this session warrants surfacing.
- **L2** — Codex CLI session IDs (`019e4739-3dd8-7581-abaa-12a0355a0a5c`, etc.) noted in artifacts but no ledger. Future "trace which codex consultation produced what finding" requires manual grep through `/var/tmp/codex-outputs/`. Codex-consult-ledger script would help.
- **L3** — `refs/checkpoints/master` mechanism itself is unmonitored. We don't know how often it commits, what triggers it, whether it's healthy. The mechanism saved this cycle but its own SRE story is invisible. Health check + write-rate audit needed.
- **L4** — The orchestrator chose Branch 4 (Workflow Integrity FAIL) at /close Round 1 partly on style-inspector evidence. But "Standard 6 critical at commit.md:130" is debatable severity — was that ACTUALLY critical, or did style-inspector self-upgrade ADVISORY→CRITICAL based on strict-literal reading that may have been overzealous? The Round 1 NO verdict consumed orchestrator + dev + ba + qa scores (-10/-5/-12). Worth a calibration check on style-inspector severity escalation logic.

### Layer O — subagent-surfaced findings the orchestrator deprioritized

- **O1** — cleanliness-inspector noted pre-existing baseline dirt: `policies/tool-policy.v1.json.bak.1778564751` backup file shouldn't be tracked, `projects/*.jsonl.bak*` transcript backups, mixed Python hook permissions across broader `hooks/` directory. All filtered out as "not this diff" but real cleanliness debt.
- **O2** — prompt-inspector emitted 4 advisory observations below severity floor: `commands/push.md` TTL rationale ~10 lines (could be trimmed), `agents/changelog-analyst.md` "Two independent rules" duplicate-rule block ~14 lines, `agents/qa.md` "structural ordering is REQUIRED" mechanism-story ~5 lines, `commands/dev.md` + `commands/close.md` R3 TodoWrite reminders restated 3× each. None individually blocking; collectively the verbose-doc anti-pattern.
- **O3** — push-analyst always emits `warn` verdict because "master is publication branch". This warning fires on EVERY /push to master, becoming noise. The check should distinguish "master push is normal for this repo" vs "be careful with master in general".
- **O4** — The recovery subagent EXPLICITLY skipped `find .git/lost-found -type f` ("not needed; checkpoint refs sufficed"). There could be OTHER lost objects in lost-found from earlier sessions never recovered. Unaudited lost work.

### Layer P — implicit assumptions the orchestrator never validated

- **P3** — git operations assumed atomic. They're not — stage/commit/push-gate-write happen in sequence with race windows.
- **P4** — codex-skill auth/config assumed stable mid-session. codex CLI has its own state (cached auth tokens at `/root/.codex/`). Token expiry mid-session would cause silent codex failures.
- **P5** — The user-prompt-submit hook injection that bakes SESSION_ID into the /push docstring assumed the literal UUID is acceptable for orchestrator consumption. It IS (the orchestrator parses it as data) but the hook is now session-specific by accident.

