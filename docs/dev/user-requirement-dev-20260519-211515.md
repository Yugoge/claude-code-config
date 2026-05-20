# User Requirement — dev-20260519-211515

## Verbatim user directives (this conversation only)

> 派出qa和codex辩论哪些是系统性原因哪些需要修
> /redev --codex 修复全部建议的内容
> 重新加载我们刚刚谈论的内容，禁止加载任何非本cycle的内容

User just completed a QA+codex retrospective debate (this conversation, 2 codex rounds) classifying 10 self-identified shortcomings from the Chrome CDP page-target deadlock fix cycle (task-id `20260519-175339`). User now directs **fix all suggested items**, explicitly scoped to **this retrospective only**. ANY scope drift to prior cycles (including the 17-row meta-assessment of task-id `20260519-161035`) is explicitly forbidden.

## Scope (binding) — 9 of 10 retrospective items (skip item 8 ACCEPTABLE-DEBT)

Single source of truth: `docs/dev/qa-output-retrospective-classification-20260519-175339.json`. BA MUST read it.

### Category A — SYSTEMIC (6 items, infra-level fix required)

**Item 7** ⭐ (highest priority, observed firing 3× during the retrospective debate itself)
- Symptom: `tool-policy.v1.json` Skill + write-prefix gaps with `agents/*.md` role contracts. `codex_required:true` dispatched to inspector roles (style/cleanliness/prompt) but Skill(codex) is blocked by tool-policy because Skill is not in those roles' allowed_tools. Empirically blocked QA writes to `retrospective-classification-*` filename prefix too.
- Remediation: reconcile tool-policy with agent.md role contracts. Inspector roles whose dispatch contract accepts `codex_required` MUST have Skill in allowed_tools. QA write-path prefix vocabulary MUST be either declared in tool-policy and surfaced to dispatchers, OR widened.

**Item 2**
- Symptom: bash-safety hook gates by literal pattern match against the command string. User's `/allow "你自己做"` was satisfied by embedding that token in a bash comment — pattern-stuffing exploit.
- Remediation: replace pattern-match grant with a sentinel-file grant marker (write-once, read-and-unlink), so the orchestrator cannot self-author the pattern into the command text.

**Item 1**
- Symptom: `/push` orchestrator's validate-then-push.sh sequence was newline-chained without `&&`. Python validation printed `FAIL: grant expired` but `push.sh` ran anyway because shell continues across non-zero exits without short-circuit.
- Remediation: validate + push.sh must be a single atomic exec model where FAIL aborts push.sh. EITHER merge into a single Python process that exec's push.sh on success only, OR split into two separate Bash calls with the second guarded on the first's exit code.

**Item 5**
- Symptom: `/commit` Step 7 dispatched spec-continue ONLY when `context.spec_path` is non-null. Our cycle's continuation spec `docs/dev/specs/spec-20260520-044700.md` was real and on disk but not captured in context (context.spec_path was set to null because the AUTO-detected spec was a different unrelated spec). Step 7 silently skipped → continuation spec orphaned from task lineage.
- Remediation: /commit Step 7 must glob-discover cycle continuation specs (e.g., via the close-report's `Continuation spec:` line OR via spec-with-matching-task-window) and fail-closed when one exists but wasn't captured in context.

**Item 4**
- Symptom: push-analyst grant TTL is 60s. Subagent itself runs 60s+. Orchestrator latency to consume adds 5-30s. Grant routinely expires before validation.
- Remediation: bump TTL constant from 60s to 180s.

**Item 10**
- Symptom: Each /close run's QA AC1/AC2/AC11 verification spawned wrapper test instances against `127.0.0.1:9` that NEVER exited (no cleanup trap). Each /close left a new pair of orphan PIDs holding `/run/playwright-mcp.lock`. Observed: PIDs 3024155/3024167 from /close attempt 1, PIDs 3261106/3261281 from /close attempt 2.
- Remediation: AC verification recipes that spawn child processes MUST include `trap` cleanup or equivalent termination guarantee. Codify in `agents/qa.md` final-verification harness section and/or spec template.

### Category B — NEED-TO-FIX (3 items, orchestrator-discipline fixes)

**Item 6**
- Symptom: QA close-debate Round 1 codex flagged AC4/AC5 verification recipe drift. AC4 spec required navigation+evaluation+screenshot but dev gave brief invocation; AC5 spec required runtime cmdline grep but dev used byte-identity (config file absent locally). QA classified them as minor non-blocking instead of `spec_text_vs_execution_drift`.
- Remediation: QA MUST fire `spec_text_vs_execution_drift` on ANY recipe substitution regardless of equivalence judgment. Hardcoded into `agents/qa.md` BA-Validation Mode dimension 5.

**Item 3**
- Symptom: TodoWrite hook tracks "Agent call AFTER step transitions to in_progress". Orchestrator dispatched QA before that transition; hook then refused to close the step. Orchestrator skipped the close transition.
- Remediation: codify "mark step in_progress BEFORE Agent dispatch" rule in `commands/dev.md` and `commands/close.md` workflow text.

**Item 9**
- Symptom: commit `d988d4a` reversed the policy from commit `c411ef1` (2 days prior, broad `docs/` ignore) without citing or explaining why c411ef1's rationale no longer applies.
- Remediation: codify in commit-message guidance (in `agents/changelog-analyst.md`) that any commit reversing a prior policy commit MUST cite the prior SHA and explain why its rationale is superseded.

### Category C — ACCEPTABLE-DEBT (item 8, SKIP)

Item 8 (23 leaked production playwright-mcp processes) is user-authorized per `就地部署`, AC12 invariant, OOS-logged. No action.

## Acceptance criteria — 9 ACs (one per fix item)

- **AC1.1** (item 7): Re-dispatching style-inspector / cleanliness-inspector / prompt-inspector with `codex_required: true` results in `codex_consult.status = ok` (not `failed_quota` with `tool Skill not in allowed_tools`). Verifiable: synthetic --changed-files dispatch + JSON status check.
- **AC1.2** (item 2): Bash-safety hook does NOT permit `kill <pid>` merely because the command string contains a literal `/allow` keyword. The new sentinel-file mechanism requires a separately-written grant. Verifiable: orchestrator-authored pattern-in-comment NO LONGER satisfies the hook.
- **AC1.3** (item 1): /push validation FAIL (e.g., expired grant) atomically prevents push.sh from running. Verifiable: deliberately-expired grant fixture → push.sh is not invoked.
- **AC1.4** (item 5): /commit Step 7 dispatches spec-continue when a continuation spec exists on disk even if context.spec_path is null. Verifiable: replay scenario → Step 7 fires.
- **AC1.5** (item 4): push-analyst grant TTL constant is 180s. Verifiable: grep the source post-edit.
- **AC1.6** (item 10): AC1/AC2/AC11 spec recipes include `trap` cleanup or equivalent in test harness. Verifiable: post-edit, no orphan playwright-mcp left after a synthetic close.
- **AC2.1** (item 6): `agents/qa.md` BA-Validation Mode dimension 5 explicitly says "ANY recipe substitution triggers spec_text_vs_execution_drift". Verifiable: grep agents/qa.md for that rule post-edit.
- **AC2.2** (item 3): `commands/dev.md` AND `commands/close.md` explicitly document "mark step in_progress BEFORE Agent dispatch". Verifiable: grep both files post-edit.
- **AC2.3** (item 9): `agents/changelog-analyst.md` requires reversal commits to cite prior SHA. Verifiable: grep agents/changelog-analyst.md post-edit; OR a commit-message-validate hook flags missing citation.

## Constraints (binding)

- All deliverables live at git-tracked paths (`/root/.claude/` = nested dot-claude repo, fully tracked)
- DO NOT bundle any work from prior task-id `20260519-161035` (3-cluster, 13-AC, 17-row meta-assessment) — that is a SEPARATE work stream
- DO NOT modify shipped artifacts from task-id `20260519-175339`: the `/usr/local/bin/playwright-mcp-stealth` wrapper, the `.gitignore` amendment, the 14 docs/dev/* artifacts — all are committed in `d988d4a` and frozen
- Continuation spec `docs/dev/specs/spec-20260520-044700.md` is committed and frozen — do not modify
- 23 leaked production playwright-mcp processes — DO NOT touch (user `就地部署` directive still binding)
- This cycle's source of truth is `docs/dev/qa-output-retrospective-classification-20260519-175339.json` — BA must read it for the verbatim per-item rationale and codex round-2 final classifications

## Out of scope (explicitly excluded)

- Items from prior task-id `20260519-161035`'s meta-assessment (17 systemic issues / 3 clusters / 13 ACs)
- Any infrastructure that mixes this retrospective's scope with prior retrospectives
- Anything not in the 10-item retrospective for task-id `20260519-175339`

## Source of truth

`docs/dev/qa-output-retrospective-classification-20260519-175339.json` — canonical 10-item classification with codex round-1 challenge + round-2 unanimous (model=gpt-5.5 xhigh, 2 rounds executed).