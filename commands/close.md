---
description: Wrapper - ask QA agent to debate with codex and return CLOSE YES/NO verdict
---

# /close

True wrapper. Three steps total:
1. Load input (spec from `$ARGUMENTS` or from the calling conversation's context).
2. Invoke the QA subagent ONCE with a debate prompt. QA runs the multi-round debate with codex INTERNALLY (using the Skill tool) and returns a single verdict line.
3. Print whatever verdict line QA returned.

The orchestration of rounds, the calls to codex, the evaluation of agreement, and the writing of the transcript all live INSIDE QAs invocation. /close itself does not call codex, does not manage rounds, and does not decide the verdict.

## Invocation

```
/close 20260424-074346               # timestamp token -> docs/dev/ba-spec-<ts>.md + qa-report-<ts>.json
/close docs/dev/ba-spec-20260424.md  # explicit path
```

When invoked mid-conversation without an argument, the orchestrator identifies the current dev cycle's spec from conversation context (it just ran /dev in the same session) and embeds those paths directly into Step 2's QA prompt. No filesystem scan, no default-to-newest.

## Workflow

Load preloaded todo list:
```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/close.py
```

### Step 1: Load input

Compute a timestamp for the report filename:
```bash
TS=$(date +%Y%m%d-%H%M%S)
```

Resolve the spec to evaluate (in priority order):
- If `$ARGUMENTS` is an explicit path (ends in `.md`/`.json` or contains `/`): use that path. Verify it exists; fail clearly if not.
- Elif `$ARGUMENTS` matches a timestamp pattern (e.g. `20260424-103044`): use `docs/dev/ba-spec-${ARGUMENTS}.md` and `docs/dev/qa-report-${ARGUMENTS}.json`. Verify both exist.
- Else (no argument): the orchestrator invoking /close MUST already know this conversation's dev artifacts from context (it just ran /dev in the same session). It embeds those paths directly into Step 2's QA prompt. There is NO filesystem scan and NO default-to-newest. If the orchestrator cannot identify the spec from context, exit with: `No spec identified. Either run /close within a conversation that just completed /dev, or provide an explicit path/timestamp.`

Also optionally note companion files if they exist at the same timestamp: `context-<ts>.json`, `dev-report-<ts>.json`.

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
- CLOSE: YES only if after your final active round BOTH your position AND codexs position are YES.
- Any NO, ambiguity, tool error, parse failure, or disagreement at the end -> CLOSE: NO.

Transcript file: write the full debate to `docs/dev/close-report-<TS>.md` with this structure:
  # Close Debate Report
  Timestamp, Input files, Rounds run, Verdict.
  For each round: [QA] position + rationale; [Codex] position + rationale.
  At bottom: final verdict line.

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
- QA is invoked EXACTLY ONCE.
- Default to CLOSE: NO on any error, ambiguity, or tool unavailability.
