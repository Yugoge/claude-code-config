---
description: Create spec files for any dev workflow (/dev, /dev-overnight, or standalone reference)
---

# /spec: General-Purpose Spec Manager

You manage spec files. `$ARGUMENTS` may be empty or hold the user's first requirement — either way, act immediately.

---

## Spec Creation Mode

**Philosophy**: Act immediately on whatever the user provides. Ask a clarification ONLY when the input is genuinely impossible to turn into a Section 5 skeleton. After writing the first spec, stay in a multi-turn loop and append any follow-up requirements to the SAME file. Exit on natural-conclusion strong signals only.

### Step 1: Parse $ARGUMENTS

- **Non-empty non-flag text**: treat as the first requirement. Skip to Step 3.
- **Empty**: ask ONCE — "What do you want to spec?" — and wait for the user's response. Use the response as the first requirement.

Do NOT ask multiple framing questions. No "deep-dive", no "acceptance criteria" interview, no preview-and-confirm gate.

### Step 2: Clarify if truly unclear (max 3 rounds)

Adapted from `/dev` BA clarification pattern (dev.md Step 4 loop, max 3 rounds, default is to proceed).

**Trigger this step ONLY when** Section 5 cannot be sketched at all — no topic, no feature, no issue identifiable, no actionable phrase. Examples of genuinely unclear input: "help", "fix it", "something's wrong", bare emoji.

**If not triggered**: skip to Step 3.

**If triggered**:
1. Ask ONE targeted question at a time. Wait for user response.
2. Re-evaluate: can Section 5 now be sketched? If yes, proceed to Step 3.
3. Repeat max 3 rounds. After the 3rd answer, proceed regardless — write the spec with whatever Section 5 content you can extract plus an `_Assumption_` note.

### Step 3: Write first spec + dispatch background Explore

1. Read the template at `~/.claude/templates/overnight-spec.md`. If missing, report error and stop.

2. Generate the output path:
   ```
   docs/dev/specs/spec-<YYYYMMDD-HHMMSS>.md
   ```
   Create `docs/dev/specs/` if it does not exist. Store this path as `spec_path` for reuse in Step 4. A fresh `/spec` invocation in a new session creates a new timestamped file; within-session follow-ups append to the same file.

3. Populate the template:
   - `<issue_description>` → short summary of the user's requirement
   - `<pipeline_index>` → `standalone`
   - `<session_id>` → `manual`
   - `<ISO-8601>` → current timestamp
   - Section 5 → user's requirement verbatim
   - All other sections → `_Not yet populated._`

4. Write the spec.

5. **Background exploration (non-blocking)**: when the user mentions specific files, components, features, or technical terms, immediately dispatch an Explore agent in the background:
   ```
   Agent(
     subagent_type="Explore",
     run_in_background=true,
     description="Spec background exploration",
     prompt="Find and summarize <what the user mentioned>. Report: file paths, current behavior, relevant code snippets. Thoroughness: medium."
   )
   ```
   Findings integrate when they arrive (see Step 4). Discrepancies may surface as a single targeted question but do NOT gate the loop.

6. Acknowledge briefly: `Spec written at <spec_path>. Send more requirements to append; say thanks/谢谢 when done.`

**Do NOT** run split / checkpoints / QA yet. Finalize happens exactly once in Step 6.

### Step 4: Multi-turn accumulation loop

Copied from `ask.md` Step 6 (multi-turn dialogue loop architecture). One `/spec` invocation spans multiple user messages; each message lands in the SAME `spec_path`.

After Step 3, wait for the next user message and branch:

- **Strong natural-conclusion signal** (Step 5 list) → proceed to Step 6 (Finalize).
- **Another requirement** → append to `spec_path` under Section 5 as a new sub-section:
  ```
  ### 5.N: <brief title extracted from the message>
  <verbatim requirement text>
  ```
  `N` increments from 2 (the first requirement populates Section 5; subsequent requirements become 5.2, 5.3, …). Then loop back to wait.
- **Exploration findings arrive** → integrate into Section 1 (Before) silently. If a finding contradicts the user's description, surface one targeted question ("I looked at X and found Y — does that match?") then loop back. Never gate the loop on exploration.
- **Mid-loop vague input** → apply Step 2 logic (max 3 rounds) to that single message before appending, then loop back.

Maintain `turn_count` internally (not user-visible), increment after each user response. No hard turn cap — termination is signal-driven.

### Step 5: Natural-conclusion detection

Copied verbatim from `ask.md` Step 8 (lines 495-510).

**Strong signals** (trigger finalize):
- Gratitude: "thanks", "thank you", "appreciate it"
- Satisfaction: "perfect", "got it", "i understand now", "that's helpful"
- Confirmation: "makes sense", "clear now", "all good"
- Topic closure: "that answers my question"
- Chinese equivalents: "谢谢", "好的", "明白了", "完美", "清楚了", "就这样", "好了", "写吧"

**Weak signals** (continue loop, do NOT finalize):
- User asks a clarifying question
- User says "interesting" (might want more)
- User provides partial understanding

Only proceed to Step 6 when a STRONG signal fires.

### Step 6: Finalize (exactly once)

1. **Count monolith lines**:
   ```bash
   MONOLITH_LINES=$(wc -l < <spec_path>)
   ```

2. **Invoke spec subagent for agent selection + view creation + checkpoints**:
   ```
   Use Agent tool with:
   - description: "Spec agent: split + checkpoints for <spec-id>"
   - prompt: "
     You are the spec subagent. Read and follow the instructions in /dev/shm/dev-workspace/dot-claude/agents/spec.md EXACTLY.
     Spec id: <spec-id>
     Monolith: <spec_path>
     Monolith lines: <MONOLITH_LINES>
     Output folder: docs/dev/specs/<spec-id>/
     Project dir: <$CLAUDE_PROJECT_DIR>
     Execute Phase 0 (read spec, decide relevant agents).
     Then Phase 1 (intelligent extraction if monolith > 200 lines).
     Then Phase 2 (checkpoint generation).
     Return a JSON summary."
   ```

3. **QA validation of split quality**:
   ```
   Use Agent tool with:
   - subagent_type: "qa"
   - description: "Validate spec split quality for <spec-id>"
   - prompt: "
     Validate the spec split at docs/dev/specs/<spec-id>/views/.
     Monolith: <spec_path>

     Check these criteria:
     1. ROLE MANDATE: If the spec defines role responsibilities (look for 'role split',
        'pipeline', agent-specific duties), verify each view's Role Mandate section
        accurately reflects the spec's definition. Flag any view where the agent's
        mandate is missing or contradicts the spec.
     2. AGENT SELECTION: Are the selected agents consistent with the spec's defined
        pipeline? Flag any agent that was included but isn't in the spec's pipeline,
        or any pipeline agent that was excluded.
     3. COVERAGE: Run python3 /root/bin/spec-verify.py --monolith <spec_path> --views-dir docs/dev/specs/<spec-id>/views/.
        Report the result.
     4. CONTENT RELEVANCE: Spot-check 3 random content blocks in each view.
        Is the content relevant to that agent's role?
     5. FUNCTIONAL COMPLETENESS: For each agent view, verify it contains enough
        information for that agent to do its job WITHOUT reading the monolith.
        - ui-specialist: Has design briefs, visual language rules, motion specs?
        - ba: Has requirements, acceptance criteria, constraints?
        - dev: Has implementation constraints, file paths, deployment steps?
        - qa: Has acceptance criteria, verification procedures, test patterns?
        Flag any view that is missing critical content that would force the agent
        to fall back to the monolith (defeating the purpose of the split).

     Return JSON: {verdict: pass|fail, issues: [...], summary: '...'}
     "
   ```

   If QA fails: report issues to user, ask whether to re-split or proceed.
   If QA passes: proceed to mark and display.

4. **Mark split as complete**:
   ```bash
   echo "split-complete: $(date -Iseconds)" > docs/dev/specs/<spec-id>/.split-complete
   ```

### Step 7: Display result

```
Spec created: <absolute path>
Split marker: docs/dev/specs/<spec-id>/.split-complete
Output folder: docs/dev/specs/<spec-id>/
Checkpoints:  .claude/specs/<spec-id>/cp-state-*.json

Sections populated:
- Section 5 (User's Acceptance Criterion): populated (N requirements accumulated)
- Section 1 (Before): <populated from Explore findings, or empty>

Usage:
  /dev                                   ← auto-detects this spec
  /dev --spec <path>                     ← explicit path
  /dev-command                           ← auto-detects this spec
  /dev-command --spec <path>             ← explicit path
  /dev-overnight <end-time>              ← auto-detects this spec
  /dev-overnight <end-time> --spec <path> ← explicit path
```

---

## Important Rules

- **Read the template at runtime** from `~/.claude/templates/overnight-spec.md`. Never hardcode template content.
- **Preserve template structure exactly** — only replace designated placeholders and `_Not yet populated._` markers.
- **Do not modify any existing files** except the spec file being created.
- **Create the output directory** (`docs/dev/specs/`) if it does not exist.
- **Use absolute paths** in all output messages.
- **Spec Creation Mode is the only mode.** It acts immediately on whatever the user provides, accumulates multiple requirements into one file per session, and finalizes only on a natural-conclusion strong signal.
- **Output folder is created by the spec subagent** during Phase 0. The subagent decides which agents get views based on spec content. Legacy specs lacking an output folder remain valid — `/dev*` falls back gracefully.
- **Todo script**: `/root/.claude/scripts/todo/spec.py` (symlinked to `/dev/shm/dev-workspace/dot-claude/scripts/todo/spec.py` — same inode) exposes the 7-step Spec Creation Mode todo list with `blocking_count = 3` (Steps 1-3 must complete before Claude can stop; Steps 4-7 are session-duration).
