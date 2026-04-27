---
description: Wrapper - ask QA agent to debate with codex and return CLOSE YES/NO verdict
disable-model-invocation: true
---

# /close

True wrapper. Three steps total:
1. Load input (spec from `$ARGUMENTS` or from the calling conversation's context).
2. Invoke the QA subagent ONCE with a debate prompt. QA runs the multi-round debate with codex INTERNALLY (using the Skill tool) and returns a single verdict line.
3. Print whatever verdict line QA returned.

The orchestration of rounds, the calls to codex, the evaluation of agreement, and the writing of the transcript all live INSIDE QAs invocation. /close itself does not call codex, does not manage rounds, and does not decide the verdict.

## Invocation

```
/close 20260424-074346                       # timestamp token -> docs/dev/ba-spec-<ts>.md + qa-report-<ts>.json
/close docs/dev/ba-spec-20260424.md          # explicit path
/close 20260424-074346 --force               # forced close, skip debate, audit-logged (escape hatch — see Step 0)
/close 20260424-074346 --force --reason "<text>"   # forced close with rationale recorded in audit
/close --force 20260424-074346               # equivalent — flag position is flexible
```

When invoked mid-conversation without an argument, the orchestrator identifies the current dev cycle's spec from conversation context (it just ran /dev in the same session) and embeds those paths directly into Step 2's QA prompt. No filesystem scan, no default-to-newest.

<!-- Cross-reference: BA spec /root/docs/dev/ba-spec-20260426-redev8.md § AC-CLOSE-FORCE-1..6 govern --force / --reason behavior. -->


## Workflow

Load preloaded todo list:
```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/close.py
```

### Step 0 (optional): --force flag short-circuit

If `$ARGUMENTS` contains the literal token `--force` (in any position), this short-circuits the entire debate path. **The model itself cannot trigger this** — `disable-model-invocation: true` (frontmatter line 3) prevents `SlashCommand`-based self-invocation regardless of arguments. Only a human invoking via the slash UI can trigger `--force`.

Argument parsing order (orchestrator parses at the slash-command layer):

```
/close <task-id> --force [--reason "<text>"]
/close --force <task-id> [--reason "<text>"]
/close <task-id> --force --reason "<text>"
```

Procedure when `--force` is present:

1. **Strip `--force` from `$ARGUMENTS`**. If `--reason "<text>"` follows, capture `<text>` (everything between the matched quotes) as `$REASON`. If absent, set `$REASON="no reason provided"`.
2. **Resolve the task-id** from the remaining argument using the same Step 1 rules below (explicit path → derive from basename; timestamp → use directly; no argument → orchestrator infers from session context). The task-id resolution rules are reused identically; do NOT branch the resolution logic.
3. **Skip Step 2 entirely** — no QA subagent invocation, no Skill(codex) call, no Workflow Integrity Dimension evaluation, no multi-round debate.
4. **Write the forced close-report** to `docs/dev/close-report-<task-id>.md` with this exact structure:

   ```
   # Close Debate Report (FORCED)
   Task-id: <task-id>
   Mode: --force (user override)
   Closed at: <ISO-8601 timestamp>
   Reason: <$REASON value, or "no reason provided">

   **Verdict**: **CLOSE: YES — FORCED by user override**

   No multi-round debate occurred. The user explicitly invoked /close with
   --force, accepting full responsibility for any defects this verdict masks.

   ## Forced Override Audit
   - Timestamp: <ISO-8601>
   - Task-id: <task-id>
   - Invoker: human user (model cannot self-invoke /close; disable-model-invocation: true)
   - Workflow Integrity Dimension: ALL bullets OVERRIDDEN — not evaluated
     1. Downstream consumability: OVERRIDDEN
     2. task-id chain consistency: OVERRIDDEN
     3. Pre-existing-defect rule: OVERRIDDEN
     4. Self-deployability: OVERRIDDEN
   - Rationale (from invoker): <$REASON value>
   - User explicitly accepts the risk of closing without debate.

   ---
   CLOSE: YES (FORCED)
   ```

   This file MUST be written even if the task-id has no upstream BA spec / context / dev-report (per AC-CLOSE-FORCE-6). The close-report is itself the audit trail; absence of upstream artifacts becomes visible in the report and is intentional.

5. **Append audit log entry** to `~/.claude/logs/close-overrides.log` (best-effort):

   ```bash
   mkdir -p ~/.claude/logs
   echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) task=<task-id> mode=force reason=\"<$REASON>\"" >> ~/.claude/logs/close-overrides.log
   ```

   If the append fails (permissions, missing dir despite mkdir, etc.), the close-report write still succeeds. The audit log is a best-effort cross-task ledger; the close-report (per-task artifact) is the authoritative record.

6. **Print the final stdout line** (this is the line consumers grep for):

   ```
   CLOSE: YES — FORCED
   ```

   The close-report's own final line remains `CLOSE: YES (FORCED)` per the template above (AC-CLOSE-FORCE-1 specifies the report's bottom line in that form). The two forms are intentional: the **stdout signal** uses the em-dash form (`CLOSE: YES — FORCED`) for downstream `/commit` / `/push` consumers; the **close-report final line** uses the parenthesized form (`CLOSE: YES (FORCED)`) so existing `grep "^CLOSE: YES$"` patterns also catch the prefix.

   Stop. Do NOT proceed to Step 1 / Step 2 / Step 3.

**When to use** (escape hatch — strongly discouraged for routine use):
- Codex hits its usage limit and Round 2 cannot complete (see redev7 close-debate stall).
- Workflow Integrity Dimension bullet flags a known-acceptable artifact (e.g., parallel-dev cycle pre-F-AGGREGATE).
- Operator has read all dissent and explicitly accepts the risk of shipping NOW.

**What it preserves**:
- `disable-model-invocation: true` — model cannot self-invoke /close (with or without --force). Only human via SlashCommand.
- Close-report artifact (every override is auditable).
- Audit log line (cross-task ledger of all overrides).

**What it skips**:
- Multi-round QA+codex debate (entire Step 2).
- Workflow Integrity Dimension evaluation (all four bullets recorded as `OVERRIDDEN`).

Every forced override is auditable and traceable. Routine use defeats the purpose of /close as a quality gate.

### Step 1: Load input

Resolve the **task-id** for the report filename. The task-id is the SAME identifier used by the source `/dev` cycle (e.g. `20260425-145411` or `redev3-p1p2-20260426`) — NOT a fresh `date +%Y%m%d-%H%M%S` at /close invocation time. Using a fresh timestamp would break /commit's PRIMARY-path lookup, which requires `close-report-<task-id>.md` and `dev-report-<task-id>.json` under the SAME `<task-id>`.

Resolve the spec to evaluate (in priority order):
- If `$ARGUMENTS` is an explicit path (ends in `.md`/`.json` or contains `/`): use that path. Verify it exists; fail clearly if not. Derive the task-id by stripping `ba-spec-` prefix and `.md`/`.json` suffix from the basename (e.g. `docs/dev/ba-spec-X.md` → task-id `X`).
- Elif `$ARGUMENTS` matches a timestamp pattern (e.g. `20260424-103044`): use `docs/dev/ba-spec-${ARGUMENTS}.md` and `docs/dev/qa-report-${ARGUMENTS}.json`. Verify both exist. The task-id IS `$ARGUMENTS` directly (timestamp form is a valid task-id; this preserves backwards compatibility for `/close <ts>` invocations).
- Else (no argument): the orchestrator invoking /close MUST already know this conversation's dev artifacts from context (it just ran /dev in the same session). It embeds those paths directly into Step 2's QA prompt and resolves the task-id from the active dev cycle's artifacts. There is NO filesystem scan and NO default-to-newest. If the orchestrator cannot identify the spec from context, exit with: `No spec identified. Either run /close within a conversation that just completed /dev, or provide an explicit path/timestamp.`

If no task-id can be derived (no argument, no /dev context, no parseable filename), /close MUST exit with the same error message above. /close MUST NOT default to `date +%Y%m%d-%H%M%S` for the close-report filename — that would silently break the task-id chain.

Bind the resolved value:
```bash
TASK_ID="<resolved task-id from rules above>"   # e.g. "$ARGUMENTS" when timestamp form, or derived from path basename
```

Also optionally note companion files if they exist at the same task-id: `context-<task-id>.json`, `dev-report-<task-id>.json`.

### Step 2: Invoke QA subagent with debate prompt

Use the Agent tool with `subagent_type: qa` ONCE. The entire debate happens inside this single subagent call. Pass this prompt (substitute paths and $TS):

```
FIRST ACTION: if a dev-registry sentinel for this session exists at /root/.claude/dev-registry/<SESSION_ID>/qa.json, read it to register.

You are the QA gatekeeper evaluating whether a completed development can be closed. You will run a MULTI-ROUND INTERNAL DEBATE with OpenAI Codex (via the Skill tool) yourself. The caller will NOT orchestrate rounds; you own the loop.

Input artifacts (read them first):
- BA spec:     <BA_SPEC path or "none">
- QA report:   <QA_REPORT path or "none">
- Companions:  <context-<ts>.json / dev-report-<ts>.json if present, else omit>

Debate protocol (all runs INSIDE you):

Round 1:
  1a. Form your initial assessment (YES/NO) on whether the dev can close. Consider:
      - Are all acceptance criteria measurably met (evidence, not code review)?
      - Is the root cause addressed and the fix correct & complete?
      - Regression risks? Scope drift? Missed edge cases?

      WORKFLOW INTEGRITY DIMENSION (mandatory — evaluate ALL four bullets explicitly; report a per-bullet PASS / FAIL / N/A-with-reason in the transcript; ANY FAIL forces CLOSE: NO regardless of AC coverage):
        1. **Downstream consumability** — Can the artifacts under evaluation be consumed by downstream commands (`/commit`, `/push`, `/merge`) without manual patching of timestamps, names, or schemas? Concretely: does `dev-report-<task-id>.json` exist with the SAME `<task-id>` as this close cycle? Does `close-report-<task-id>.md` end with `CLOSE: YES`? If a human would have to rename, copy, or hand-edit any artifact to make `/commit` succeed, this bullet is FAIL.
        2. **task-id chain consistency** — Are predecessor artifacts (BA spec → context → dev-report → completion → qa-report → close-report) ALL present under the SAME `<task-id>`? Mismatched task-ids across the chain → FAIL.
        3. **Pre-existing-defect rule** — If a Round-1 critique surfaces a "pre-existing architectural defect" or similar, the debate MUST resolve as follows:
             (a) if THIS cycle's BA spec CLAIMS to address the defect → the defect IS in scope and must be evaluated on its merits;
             (b) if THIS cycle's BA spec EXPLICITLY documents the defect as a known non-goal (Section 6 / Out-of-Scope, by name) → out-of-scope is a valid walkback; bullet PASSES;
             (c) otherwise → the defect IS in-scope; the "pre-existing / out-of-scope" walkback is FORBIDDEN; verdict MUST be NO. This bullet FAILS unless (a) is satisfied with passing evidence or (b) is satisfied with explicit BA-spec text.
        4. **Self-deployability** — Can the changes be committed and shipped via the project's own commit/push toolchain (`/commit`, `/push`, `/merge`) without out-of-band patching? Evaluate as the AND of these sub-items:
             (i) **/commit consumability** (PASS/FAIL) — `/commit` accepts the cycle's artifacts (dev-report, qa-report, completion) without orchestrator-side jq or Edit patches to fix schema. FAIL if any manual schema patch was required.
             (ii) **Push permission** (PASS/FAIL) — the orchestrator's git identity has write access to the target remote(s). FAIL if push was blocked by remote permissions or required a human to push from a different identity.
             (iii) **No commit-channel bypass** (PASS/FAIL) — no manual `git commit` outside agent context, no `CLAUDE_PROJECT_DIR` override to bypass repo-rooted hook gates, no `auto-bulk:` pattern abuse to smuggle changes past `pretool-git-privilege-guard.py`. FAIL if any of these bypass channels was used.
             (iv) **User-only physical filesystem actions** (N/A-with-reason — NEVER FAIL) — any sub-item that would require the user to perform a physical filesystem action the orchestrator structurally cannot perform itself is evaluated as N/A-with-reason, NOT FAIL. The canonical example is the user touching `.hook-refactor-allow` to authorize a hook-tree edit: human-in-the-loop is intentional anti-fabrication protection per Trap 11; orchestrator-creatable sentinels would defeat the protection's threat model. The N/A reason MUST cite Trap 11 verbatim. This clause covers ONLY user-only physical filesystem actions; it does NOT cover the bypasses listed in sub-item (iii), which remain FAIL.
           Bullet 4 is PASS when (i), (ii), and (iii) are each PASS (or N/A-with-reason where structurally inapplicable per (iv)). Any FAIL in (i)–(iii) is Bullet 4 FAIL.

  1b. Invoke the Skill tool with skill=codex. Pass codex a prompt that includes:
      - The same input artifact paths
      - Your Round-1 position and rationale
      - Instruction: "Challenge adversarially. Look for missed AC, evidence gaps, regression risk, overlooked edge cases. Reply with exactly one line `CODEX: YES` or `CODEX: NO` followed by 3-8 sentences of rationale."
  1c. Parse codexs response. If parsing ambiguous, treat as NO.

Round 2 (skip if Round 1 ended with both QA=YES and CODEX=YES):
  2a. Re-assess your position after reading codexs Round-1 challenge. If you still say YES, strengthen justification; if codex surfaced a real issue, update to NO.
  2b. Invoke Skill(codex) again with your updated position + codexs prior challenge + artifact paths. Ask codex to either confirm or press further, replying again with `CODEX: YES` / `CODEX: NO` + rationale.

Round 3 (skip if earlier unanimous YES):
  3a. Final reassessment.
  3b. Final Skill(codex) call with full history.

Verdict rule (UNANIMOUS CONSENT):
- CLOSE: YES only if after your final active round BOTH your position AND codexs position are YES AND all four Workflow Integrity Dimension bullets evaluate to PASS (or N/A-with-reason; never FAIL).
- Any NO, ambiguity, tool error, parse failure, or disagreement at the end -> CLOSE: NO.
- Any Workflow Integrity Dimension bullet failing -> CLOSE: NO regardless of AC coverage status, with the failing bullet named in the dissent line.

Transcript file: write the full debate to `docs/dev/close-report-<task-id>.md` (substitute `<task-id>` with the value resolved in Step 1 — e.g. the source `/dev` cycle's task-id; do NOT use a fresh `date +%Y%m%d-%H%M%S` here, that would break /commit's PRIMARY-path lookup) with this structure:
  # Close Debate Report
  Task-id, Input files, Rounds run, Verdict.
  Workflow Integrity Dimension: explicit per-bullet status (1. Downstream consumability: PASS/FAIL/N/A; 2. task-id chain consistency: PASS/FAIL/N/A; 3. Pre-existing-defect rule: PASS/FAIL/N/A; 4. Self-deployability: PASS/FAIL/N/A) — with one-sentence reason for each FAIL or N/A.
  For each round: [QA] position + rationale; [Codex] position + rationale.
  At bottom: final verdict line.

Overwrite policy: if `docs/dev/close-report-<task-id>.md` already exists with a `CLOSE:` line in it (a prior closure attempt for the same task-id), do NOT silently overwrite — append a fresh debate as a new section dated by ISO timestamp, OR (if your tooling cannot append cleanly) treat the prior closure as authoritative and do not re-close.

Return value: print to stdout exactly ONE of these lines as the final line of your response:
  CLOSE: YES
  CLOSE: NO - <one-sentence reason naming the dissenting party and their objection>
```

### Step 3: Print the QA verdict

Take the final line QA returned (`CLOSE: YES` or `CLOSE: NO - ...`) and echo it to stdout as the last line of /close.

## Constraints

- /close does NOT call Skill(codex). QA does, internally.
- /close does NOT manage rounds. QA does, internally.
- /close does NOT evaluate verdict. QA does, internally.
- QA is invoked EXACTLY ONCE (non-force path) or ZERO times (forced path).
- Default to CLOSE: NO on any error, ambiguity, or tool unavailability — EXCEPT when `--force` is explicitly passed by a human user, in which case CLOSE: YES (FORCED) is the result regardless of upstream artifact state (Step 0 short-circuit).
- `disable-model-invocation: true` (frontmatter) means the model cannot self-invoke /close via SlashCommand — this applies equally to the forced path. Only a human can trigger `--force`.
