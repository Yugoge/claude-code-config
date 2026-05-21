<!-- AUTO-GENERATED VIEW for ba | source: docs/dev/specs/spec-20260520-221059.md | extracted: 2026-05-21T00:00:00Z -->

# ba view of spec-20260520-221059

**Monolith**: docs/dev/specs/spec-20260520-221059.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> **Pipeline**: ba → dev → qa

# Spec: Unresolved issues backlog from session 88dfdcea — TOP 3 cluster stranded by scope hot-swap + post-session confession

**Pipeline**: ba → dev → qa
**Session**: spec-20260520-221059
**Created**: 2026-05-20T22:10:59Z

## Section 5: User's Acceptance Criterion

> 将你说的问题全部保存为新的spec

User's directive: save everything the orchestrator just enumerated as the comprehensive unresolved-issues backlog. The backlog spans three layers — the originally-promised work that got displaced by scope hot-swap, the items the orchestrator surfaced under self-confession when the user asked "are you sure nothing else is unrecorded?", and the always-known deferred items. The verbatim enumeration follows:

### Layer A — 17-item meta-assessment of cycle 20260519-161035 (tmpfs prevention), TOP 3 cluster (8 items) — **stranded by scope hot-swap**

When the user said `修复全部` after the 17-item meta-assessment, they meant these 8 items (the TOP 3 cluster grouped by QA+codex). Mid-cycle the requirement doc was rewritten to a different 9-item retrospective; these 8 items got displaced and **none of them shipped**.


### Layer B — orchestrator's post-session self-confession (5 items the orchestrator initially downplayed)

When the user asked "确定没有别的没做的没有被你记录?", the orchestrator surfaced:


### Layer C — 17-item meta-assessment of cycle 20260519-161035, the OTHER 9 always-known deferred items

These were explicitly listed as deferred in the user-requirement document at session midpoint; none addressed.


### Layer D — minor residual debt from THIS session's own deliverables and cross-cycle pollution


### 5.2: 用户反馈"就这么点？你给我发了这么多！"— 补充遗漏

> 就这么点？你给我发了这么多！

User points out that the original 4 layers (Layer A/B/C/D, 29 items) under-represents the breadth of issues raised across the full conversation. Below is a deeper sweep of things mentioned in passing, hinted at, or surfaced as side-observations but never given an explicit ID slot:

### Layer E — orchestrator-process gaps (meta-level, beyond specific tool fixes)

- **E1** — Orchestrator's missing "shippability cross-check" reflex at every stage (not just an automated gate). Beyond R1's tool implementation, the orchestrator never paused to ask "will this actually ship via git?" at QA/close/commit. R1 fixes the gate; this fix is about orchestrator MENTAL MODEL. Even after R1 lands, orchestrator should also internalize the check as a pre-/commit reflex.
- **E2** — Subagent "wrote report but didn't" silent-failure pattern. Multiple instances where inspector subagents reported "Report written" but no file appeared on disk (cleanliness + prompt during cycle 211515 close, before artifact recovery). Different from write-guard blocking: subagents CLAIMED success. Possible causes: tool-policy write-prefix gap, hook intercepting silently, or subagent fabrication. Needs root-cause investigation + a "subagent claim verification" check (orchestrator validates claimed deliverables before proceeding).
- **E3** — Score-system ceiling=100 truncates positive deltas. dev hit 100 ceiling, subsequent +6 / +15 events silently capped. Net signal lost. Score-system needs either remove ceiling, log uncapped values, or surface "would have been +N but ceiling-capped" in the event log (R9 may or may not cover).
- **E4** — Codex invocation count + cost not tracked. Across this session codex was invoked ~15-20+ times via Skill(codex). Each is a separate GPT-5.5 API call. No accounting anywhere. Affects cost-aware policy decisions (when to invoke codex vs when to skip).
- **E5** — This very spec output is at risk: `docs/dev/specs/spec-20260520-221059.md` lives on tmpfs (`/dev/shm/...`) under a `docs/` subtree with historical gitignore complications. Need to verify (a) it'll actually persist past next reboot, (b) it ships via git.
- **E6** — Single-/commit-grant-per-orchestrator-dispatch limit. changelog-analyst surfaced this: the guard unlinks grant after first commit, so multi-commit cycles (feature + orphan + nested repo) require either (a) /commit wrapper writes N grants up-front, or (b) contract explicit "one commit per dispatch". Real gap, blocks the orphan-capture pattern in single /commit invocations.
- **E7** — No hook enforces R9 reversal-citation rule. agents/changelog-analyst.md got the rule (item 9 from 9-item retrospective landed) but there's no commit-message-validate hook that fails commits without "Reverses <SHA>:" citation when needed. The rule is documentation-only; no teeth.
- **E8** — L1.5 hook ENOSPC fallback untested. Counter file write would fail under genuine /tmp ENOSPC; hook designed non-blocking but the ENOSPC fallback path was never exercised. R5a covers the redesign; this is the testing gap.
- **E9** — `.git/lost-found` / `git fsck --unreachable` blobs never investigated as part of artifact-loss forensics. The subagent recovered via `refs/checkpoints/master` but didn't search lost-found. May contain additional copies of historically-lost work.
- **E10** — Session learnings are non-durable. This spec file is the only persistent record of these self-assessments. If file is lost (tmpfs cleared, gitignore matched, ghost cycle pollution), the entire reasoning chain across this session is lost. Need a more durable "session learnings log" architecture.
- **E11** — QA scoring imbalance for messenger-vs-author cases. QA net -6 this cycle when QA was messenger of inspector finding (not QA's own analysis failure). The schedule treats "CLOSE: NO because QA dissented" identically to "CLOSE: NO because inspector caught issue post-QA". A "QA-caught-vs-QA-missed" distinction is missing.
- **E12** — The "scope hot-swap" mid-cycle is itself unprecedented and unrecorded. requirement doc was rewritten mid-/redev — was it user intent, tool accident, or session-compaction artifact? Process didn't record WHY scope changed or WHO did it. Future cycles need a "scope-change event log" to prevent silent scope diff.
- **E13** — Orchestrator claims-vs-reality drift. Multiple "this is done" claims turned out false in retrospect: "all 6 cycle artifacts verified" before they vanished; "inspector reports written" before they were found missing; "subagent reported success" before the write was silently blocked. Subagent-claim-verification gap (orchestrator should re-check claimed deliverables on disk before accepting subagent reports as ground truth).
- **E14** — Inspector dispatch authority gap during /close debate. close.md restricts inspector dispatch to /close-orchestrator itself, not QA-internal. If QA debate concludes "we need to re-run an inspector after the fix" (which happened this cycle), QA cannot dispatch — only the next outer orchestrator can. Process inflexibility.
- **E15** — TodoWrite canonical-validation ceremony cost. Every step transition requires a separate TodoWrite call due to "one completion per call" hook rule. Multiple wasted tool calls per cycle just for state-machine bookkeeping. Either widen the rule (allow batched transitions) or eliminate the per-call requirement.
- **E16** — Conversation transcript not persisted to disk by /spec or anywhere else. The user-orchestrator dialogue across this session lives only in the REPL. If session ends, the reasoning chain is lost. /spec should optionally snapshot key turns into a session-companion file alongside the spec.

### Layer H — knowledge the user explicitly might value

- **H1** — Codex's value vs cost. Across this session codex caught REAL bugs that would have shipped broken (find -prune action placement, `du -sh --max-depth=1` GNU bug, flock subshell exit propagation, AC4 circular falsification, regex parenthetical-qualifier drift, several Standard-6 / out-of-scope catches at close-debate). The cost is real but the value is concrete. A formal "codex outcomes ledger" would help cost-justify continued use vs alternatives.
- **H2** — The cycle 161035 4-layer prevention IS working empirically: /tmp at 36% (vs 85% baseline pre-cycle); cron runs producing real `freed=` data. Effectiveness verified, just not formally recorded.
- **H3** — `refs/checkpoints/master` auto-commit mechanism (per CLAUDE.md) saved this cycle. Without it, 5 artifacts would have been permanently lost. The mechanism is doing real work; recognition + monitoring + documentation strengthening warranted.

### Layer I — disclaimers (the orchestrator's residual uncertainty)

- **I1** — Across multiple context compactions in this session, the orchestrator may have lost memory of early-session asks or subagent-report follow-ons. Items I/J/K... may exist that simply aren't recoverable from current context. The user is invited to add any forgotten items they remember.
- **I2** — The session SessionStart and resume hooks fired multiple times (suggesting at least 4-5 context window resumes). Each resume may have dropped state. Persistent ledger of "what was discussed before each resume" doesn't exist.

### 5.3: 用户再次追问"确定没有更多了？"— 第三轮深挖

> 确定没有更多了？

User pushes for another exhaustive sweep. Below are items pulled from deeper recesses — bugs, gaps, and observations the orchestrator noticed during execution but never elevated to user-facing surface.

### Layer K — workflow conflicts the orchestrator silently navigated

- **K1** — The original 8-item TOP cluster (Layer A) IS from cycle 161035 meta-assessment. The 9-item retrospective scope (cycle 211515) carried the user's binding directive `禁止加载任何非本cycle的内容` referring to NOT bundling 161035 work. **Finishing Layer A's 8 items requires reversing or scoping that directive.** This is a workflow conflict the user needs to explicitly resolve before the 8 items can ship. Future /dev or /redev addressing Layer A must re-authorize loading 161035 meta-assessment content.
- **K2** — Commits authored across multiple agents/sessions landed on origin/master under this cycle's banner. Specifically `28a1e85 feat(hooks): allowlist consolidation + push-sentinel + AC verify suite` and `97585ca docs(dev): workflow artifact backlog from 20260107 -> 20260520 cycles` were already on disk before THIS session's /commit. **The orchestrator has no visibility into who authored those, what was bundled, or whether their contents matched the 9-item retrospective scope.** Audit needed.
- **K3** — Push to origin did NOT include the 22 dirty files. If a future session rebases origin/master, dirty files become candidates for merge conflicts or loss. Should those files be committed (under what cycle?), reverted, or stashed?
- **K4** — `/do` consent flag at `/tmp/claude-orchestrator-consent-<session-id>.flag` is meant to expire at session end. But session resumes (which fired multiple times this session per SessionStart hook) may not clear the flag. Consent may persist across logical session boundaries. Needs verification.

### Layer M — preferences and memory that ought to be durable

- **M1** — User preferences observed across the session but not persisted anywhere: prefers Chinese with mixed English; values orchestrator decisiveness over excessive clarification; wants honesty about gaps (asked "are you sure" twice in a row); accepts terse direct answers. None of this is recorded in CLAUDE.md or anywhere durable.
- **M2** — Session-level reasoning chain (the 21+ user-message conversation arc) is NOT persisted to disk. /spec captured the TOP-LEVEL ask but the iterative refinement reasoning is REPL-only. Next session orchestrator has no record of HOW we got here.
- **M3** — Multiple "ghost cycle" task-id slot collisions are now known: `20260519-211515` had 3 scopes; `spec-20260518-225715` mascot scoring also adopted the same slot for D+H. **How many MORE task-id slots have undiscovered ghost pollution?** No systematic survey done.
- **M4** — The 10-item retrospective from cycle 175339 (source of the 9-item shipped scope) — the orchestrator never verified `qa-output-retrospective-classification-20260519-175339.json` ACTUALLY contains 10 items. Could be more. Could be miscategorized. Trust-but-verify never applied to the retrospective source.

### Layer N — what I really am not sure about

- **N1** — The user might not remember asking specific things (per their own admission "我已经忘记整个session我的需求是什么"). Cross-referencing user_message_log against orchestrator_promised_actions would surface the truth. No such cross-check ran.
- **N2** — The orchestrator may have made implicit promises in side conversations ("I'll keep that in mind", "let me check", etc.) that weren't actioned. No follow-up tracking exists.
- **N3** — The conversation may have included context-compaction summaries that lost subtle requirements. Each SessionStart hook firing this session was a compaction event; what was summarized away?

### 5.4: 第四轮"还有"— 更深的角度

> 还有

User signals "keep digging". Below are items pulled from yet-deeper angles — subagent-surfaced findings I deprioritized, implicit assumptions, hook/process artifacts, and execution side-effects the orchestrator never elevated.

### Layer S — orchestrator-only-rule erosion

- **S1** — The orchestrator-only rule says "delegate real work to subagents". This session, I directly ran ~50+ Bash commands, ~20+ jq queries, multiple Read/Edit/Glob calls. The orchestrator did substantive work, not just dispatch. The rule is being silently weakened by execution pressure.
- **S2** — Section 5 of THIS spec is now 100+ items. The /spec rule says Section 5 holds "verbatim user requirement". User's verbatim is "save everything" + "more" + "still more" + "more"; the 100+ items are orchestrator-generated content meant to honor that intent but technically violate the verbatim rule. Spec template's intent vs spec content reality has drifted.
- **S3** — `/spec` Step 6 (Finalize) will dispatch the spec subagent to split this monolith into agent views. With 100+ items across 19 layers (A-S), the split agent faces a complex extraction problem. Split-QA may iterate 3 rounds and still produce uneven views. The "best-effort proceeds with split-qa-unresolved.json" path is likely.

### Layer T — interaction patterns the orchestrator never recorded

- **T1** — The user invoked `/do 修复` once. /do unlocks direct operations session-wide but the orchestrator used it only ONCE (for the commit.md:130 Edit). Could have used it more (e.g., for the 22 dirty files cleanup). Underused authorization.
- **T2** — Auto-memory system at `/root/.claude/projects/-dev-shm-dev-workspace-dot-claude/memory/` is mentioned in system prompt but I wrote NOTHING there this session. User preferences M1, session lessons E10, ghost cycle pattern M3 — all candidates for memory.
- **T3** — `/memory`, `/clean`, `/merge` commands exist but never invoked. /clean would have surfaced dirty files earlier. /memory would have recorded preferences.
- **T4** — Two AskUserQuestion prompts returned empty answers. Could mean user clicked something that didn't transmit (data loss bug) OR clicked an option I didn't enumerate (orchestrator coverage gap) OR genuinely skipped. The empty-payload pattern was never disambiguated.

### Layer U — meta-observations on this very accumulation

- **U1** — Each "are you sure" sweep finds new items because the search space (everything mentioned across the session) is unbounded. Pattern suggests no natural ceiling — only diminishing returns. At some point a confidence threshold ("I'm sure I've captured the top 95%") is the natural stopping point.
- **U2** — The orchestrator's "remembering" is limited by context compactions. SessionStart hooks fired ~4-5 times this session; each is a compaction event. Items mentioned BEFORE a compaction may have been silently summarized away.
- **U3** — This spec file IS the durable record of all of the above. If THIS spec is lost (gitignore, ghost pollution, reboot, /spec misconfig), this entire reasoning cascade is gone. Recursive concern: the artifact preserving the "fragility of artifacts" lessons is itself fragile.

## Source-of-truth references

- 17-item meta-assessment (Layer A + C source): `docs/dev/meta-assessment-20260519-161035.json`
- 9-item retrospective scope (replaced Layer A mid-cycle): `docs/dev/qa-output-retrospective-classification-20260519-175339.json`
- The 4-layer prevention cycle (Layer B's `in_scope_minor` source): `docs/dev/qa-report-20260519-161035.json` codex_consult section
- This session's transcript: present as full conversation history, not yet persisted to disk

## Scope and constraints inherited (binding)

- DO NOT modify shipped artifacts already on `origin/master` (commits `6cd997b`, `34210cc`, `8d74e83`, `d988d4a`, `6d28883`, `28a1e85`, `23184c9`, `97585ca`, `4d9f9f5`)
- DO NOT modify frozen continuation spec `docs/dev/specs/spec-20260520-044700.md`
- Future cycles addressing these issues MUST land deliverables at non-gitignored paths (do not repeat the L3 mistake)
- All new scripts use `#!/usr/bin/env bash` or `#!/usr/bin/env python3`; chmod +x
- Lifecycle log location (when R9 lands) MUST be `logs/lifecycle.jsonl` (in-repo; add `.gitignore` exception if `logs/` is currently ignored)
