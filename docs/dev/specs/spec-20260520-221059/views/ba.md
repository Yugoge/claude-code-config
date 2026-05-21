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
