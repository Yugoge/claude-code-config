---
description: Orchestrate a multi-round QA-vs-Codex debate to evaluate whether a development can be closed (unanimous-consent verdict)
argument-hint: "[spec-path-or-timestamp] (optional — auto-detects newest top-level docs/dev/ba-spec-*.md or qa-report-*.json if omitted)"
allowed-tools: [Bash, Read, Glob, Grep, Agent, Skill, TodoWrite, Write]
---

# /close — Multi-Agent Debate Closure Gate

Evaluate whether a specific development effort can be closed by orchestrating a structured multi-round debate between the QA agent (primary gatekeeper) and OpenAI Codex (adversarial challenger). Uses unanimous-consent verdict: `CLOSE: YES` only when BOTH parties agree YES; any disagreement → `CLOSE: NO`.

---

## Philosophy

QA alone may be too lenient. A second independent opinion from Codex (gpt-5.4, xhigh reasoning) provides an adversarial challenge to QA's assessment. A multi-round debate (max 3 rounds) lets each side refine their position based on the other's arguments. Unanimous consent ensures conservative closure — when in doubt, do NOT close.

---

## Invocation Examples

```
/close                               — auto-detect newest BA spec / QA report at top-level docs/dev/
/close 20260424-074346               — use the spec/report with this timestamp
/close docs/dev/ba-spec-20260424.md  — use this explicit file path
```

---

## Workflow

**CRITICAL**: Use TodoWrite to track workflow phases. Load preloaded todo list with:
```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/close.py
```

Mark each step `in_progress` before starting, `completed` immediately after.

### Step 1: Load Input Context

Capture a single timestamp for the entire run (used for the report filename):
```bash
TS=$(date +%Y%m%d-%H%M%S)
echo "$TS"
```

Determine the debate input:

1. If `$ARGUMENTS` is non-empty:
   - If it looks like a path (contains `/` or ends with `.md`/`.json`) — validate file exists with `test -f "$ARGUMENTS"`; if not, print `Error: path not found: $ARGUMENTS` and exit.
   - Otherwise treat it as a timestamp token (e.g. `20260424-074346`) — search for `docs/dev/ba-spec-${ARGUMENTS}.md` then `docs/dev/qa-report-${ARGUMENTS}.json` at the top-level; fail clearly if neither exists.
2. If `$ARGUMENTS` is empty — auto-detect the newest file at TOP-LEVEL `docs/dev/` matching either glob:
   ```bash
   # IMPORTANT: -maxdepth 1 — must NOT descend into docs/dev/specs/ (that belongs to /spec command)
   INPUT=$(find docs/dev -maxdepth 1 -type f \( -name 'qa-report-*.json' -o -name 'ba-spec-*.md' \) -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n1 | cut -d' ' -f2-)
   ```
   If `INPUT` is empty, print `No ba-spec or qa-report found in docs/dev/. Provide a path: /close <path>` and exit.

Also attempt to find the matching pair (same timestamp) so both BA spec and QA report can be referenced if available. The companion files (`context-<ts>.json`, `dev-report-<ts>.json`) are helpful additional context if they exist — include their paths in the agent prompts.

### Step 2: Early-Exit Check (Pre-Flight)

Validate the input file is readable and non-empty. If invalid or empty, exit with a clear error.

### Step 3-8: Multi-Round Debate (max 3 rounds)

Loop up to 3 times. In each round:

**QA turn (first each round)** — use the **Agent** tool with `subagent_type: qa`:

Prompt template:
```
You are the QA gatekeeper in a closure debate for development: <input file path>.

[Round N / QA turn]

Relevant artifacts (read them yourself — do not ask for inlined content):
- <ba_spec_path>
- <qa_report_path if exists>
- <context_json_path if exists>
- <dev_report_path if exists>

<If round > 1:>
Prior Codex challenge (from Round N-1):
<codex_prior_output>

TASK: Assess whether this development is ready to close. Consider:
- Are all acceptance criteria met?
- Is the fix correct and complete?
- Are there regression risks?
- Did QA verify via evidence (not just code review)?

Reply with a single explicit line `QA: YES` or `QA: NO` followed by your reasoning (3-8 sentences).
```

Capture QA's full response. Parse the first occurrence of `QA: YES` or `QA: NO` (case-insensitive, word-boundary). If neither found, treat as `NO` (conservative).

**Codex turn (second each round)** — use the **Skill** tool with `skill: codex`:

Prompt template:
```
You are an adversarial code reviewer challenging the QA gatekeeper's closure assessment for development: <input file path>.

[Round N / Codex turn]

QA position (Round N):
<qa_current_output>

<If round > 1:>
Your prior challenge (Round N-1):
<codex_prior_output>
QA prior position (Round N-1):
<qa_prior_output>

Relevant artifacts:
- <ba_spec_path>
- <qa_report_path if exists>

TASK: Challenge or confirm QA's assessment. Look for:
- Missed acceptance criteria
- Incorrect root cause reasoning
- Evidence gaps (code review without live verification)
- Edge cases not considered
- Regression risks

Reply with a single explicit line `CODEX: YES` or `CODEX: NO` followed by your reasoning (3-8 sentences).
```

Capture Codex's full response. Parse the first occurrence of `CODEX: YES` or `CODEX: NO` (case-insensitive, word-boundary). If the Skill tool errors or returns nothing usable, record `Codex unavailable` and treat as `NO`.

**Early exit**: After both QA and Codex have replied in any round, if `qa_position == YES` AND `codex_position == YES`, exit the loop immediately and label the transcript `[Early Consensus at Round N]`.

### Step 9: Evaluate Verdict

Only the **final active round** determines the verdict:
- If `qa_final == YES` AND `codex_final == YES` → `CLOSE: YES`
- Otherwise → `CLOSE: NO — <dissenting party(ies) and reason>`

Construct `<reason>` by naming which party said NO (or `both`) and summarising their stated objection in one sentence.

### Step 10: Write Report and Print Verdict

Create `docs/dev/close-report-$TS.md` containing:

```markdown
# Close Debate Report

**Timestamp**: <TS>
**Input**: <input_file_path>
**Companion artifacts**: <list of detected related files>
**Rounds run**: <N>
**Verdict**: CLOSE: YES  |  CLOSE: NO — <reason>

---

## Round 1

### [Round 1 / QA]
<full QA response>

**Position**: YES | NO

### [Round 1 / Codex]
<full Codex response>

**Position**: YES | NO

<repeat for each round run>

<If early consensus:>
## [Early Consensus at Round N]
Both parties agreed YES; debate ended early.

---

## Final Verdict

CLOSE: YES
— or —
CLOSE: NO — <reason>
```

Print the full transcript to console with `[Round N / QA]` and `[Round N / Codex]` headers. On the final console line, print **exactly** one of:

```
CLOSE: YES
CLOSE: NO — <reason>
```

---

## Rules & Constraints

- **Unanimous consent**: any single `NO` (or ambiguous/errored response) in the final round → `CLOSE: NO`
- **Max 3 rounds** — hard limit
- **QA first each round**, Codex second
- **Early exit only on round-1 (or later) unanimous YES**
- **Codex must be invoked via the Skill tool** (`skill: codex`) — NEVER directly shell out to `codex exec`
- **QA must be invoked via the Agent tool** (`subagent_type: qa`)
- **Do not fabricate YES** to achieve closure — if parsing is ambiguous, default to NO
- **No hardcoded absolute paths** in the command logic — use relative paths from the current working directory and env-derived paths where possible

## Error Handling

- **No input found + no argument** → informative exit before any agent call
- **Argument path does not exist** → informative exit
- **QA subagent fails / returns no output** → record `QA error: <message>` in transcript, treat as `NO`
- **Codex unavailable (binary missing, API key unset, Skill returns error)** → record `Codex unavailable` in transcript, treat as `NO`
- **Ambiguous YES/NO parsing** → include full response verbatim; treat as `NO`

---

**Output files**:
- `docs/dev/close-report-<timestamp>.md` — full labeled transcript + verdict
- Stdout — identical transcript plus final one-line verdict
