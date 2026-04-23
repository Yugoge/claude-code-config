---
description: Create spec files for any dev workflow (/dev, /dev-overnight, or standalone reference)
---

# /spec: General-Purpose Spec Manager

You manage spec files based on the 8-section spec template. Parse `$ARGUMENTS` to determine the mode, then execute the appropriate workflow below.

**Arguments**: `$ARGUMENTS`

---

## Argument Parsing

Parse the arguments to determine the mode:

1. **Non-empty text**: Quick creation mode (inline description)
2. **Empty / no arguments**: Spec from Description mode (asks one question, then writes)

---

## Mode 1: Quick Creation (inline description)

**Trigger**: `$ARGUMENTS` is non-empty text (e.g., `/spec fix the login button styling`)

**Steps**:

1. Read the template at `~/.claude/templates/overnight-spec.md`. If missing, report error and stop.

2. Generate the output path:
   ```
   docs/dev/specs/spec-<YYYYMMDD-HHMMSS>.md
   ```
   Create `docs/dev/specs/` if it does not exist.

3. Populate the template:
   - `<issue_description>` → user's description from `$ARGUMENTS`
   - `<pipeline_index>` → `standalone`
   - `<session_id>` → `manual`
   - `<ISO-8601>` → current timestamp
   - Section 5 → user's description verbatim

4. Write the spec.

5. **Count monolith lines** (needed by spec subagent):
   ```bash
   MONOLITH_LINES=$(wc -l < docs/dev/specs/<spec-id>.md)
   ```

6. **Invoke spec subagent for agent selection + view creation + checkpoints** (final step):
   ```
   Use Agent tool with:
   - description: "Spec agent: split + checkpoints for <spec-id>"
   - prompt: "
     You are the spec subagent. Read and follow the instructions in /dev/shm/dev-workspace/dot-claude/agents/spec.md EXACTLY.
     Spec id: <spec-id>
     Monolith: docs/dev/specs/<spec-id>.md
     Monolith lines: <MONOLITH_LINES>
     Output folder: docs/dev/specs/<spec-id>/
     Project dir: <$CLAUDE_PROJECT_DIR>
     Execute Phase 0 (read spec, decide relevant agents).
     Then Phase 1 (intelligent extraction if monolith > 200 lines).
     Then Phase 2 (checkpoint generation).
     Return a JSON summary."
   ```

7. **QA validation of split quality** (final check before display):
   ```
   Use Agent tool with:
   - subagent_type: "qa"
   - description: "Validate spec split quality for <spec-id>"
   - prompt: "
     Validate the spec split at docs/dev/specs/<spec-id>/views/.
     Monolith: docs/dev/specs/<spec-id>.md

     Check these criteria:
     1. ROLE MANDATE: If the spec defines role responsibilities (look for 'role split',
        'pipeline', agent-specific duties), verify each view's Role Mandate section
        accurately reflects the spec's definition. Flag any view where the agent's
        mandate is missing or contradicts the spec.
     2. AGENT SELECTION: Are the selected agents consistent with the spec's defined
        pipeline? Flag any agent that was included but isn't in the spec's pipeline,
        or any pipeline agent that was excluded.
     3. COVERAGE: Run python3 /root/bin/spec-verify.py --monolith docs/dev/specs/<spec-id>.md --views-dir docs/dev/specs/<spec-id>/views/.
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

8. **Mark split as complete**:
   ```bash
   echo "split-complete: $(date -Iseconds)" > docs/dev/specs/<spec-id>/.split-complete
   ```
   This marker file indicates the spec has been split into per-agent views.
   The monolith retains its original .md filename for path compatibility.

9. Display confirmation:
   ```
   Spec created: <absolute path>
   Split marker: docs/dev/specs/<spec-id>/.split-complete
   Output folder: docs/dev/specs/<spec-id>/
   Checkpoints:  .claude/specs/<spec-id>/cp-state-*.json

   Sections populated:
   - Section 5 (User's Acceptance Criterion): populated from your description

   Usage:
     /dev                                   ← auto-detects this spec
     /dev --spec <path>                     ← explicit path
     /dev-command                           ← auto-detects this spec
     /dev-command --spec <path>             ← explicit path
     /dev-overnight <end-time>              ← auto-detects this spec
     /dev-overnight <end-time> --spec <path> ← explicit path
   ```

---

## Mode 2: Spec from Description (default when no args)

**Trigger**: `$ARGUMENTS` is empty

**Philosophy**: Act immediately. The agent's job is to write a spec from whatever the user provides — not to interrogate them. Ask exactly one question when args are empty. Ask one clarification question only if the input is genuinely ambiguous by specific detection rules. Otherwise write immediately.

**Background rules** (not interview ceremony):
- **Record verbatim.** User's words go into the spec exactly as spoken. No editing, no "cleaning up", no rewording.
- **Never omit.** If the user provides a 10-line answer, all 10 lines go into the spec. Do not condense.
- **Ask when confused.** If something is unclear, ambiguous, or uses unfamiliar terms — ask a follow-up immediately. Do not assume or infer.
- **No suggestions.** Do not suggest solutions, approaches, or improvements. You are recording what the user wants, not advising them.

### Step 1: Request description

Say exactly:
```
What do you want to spec?
```

Wait for user's response. Proceed to Step 2.

### Step 2: Detect vagueness (surgical rules only)

**Vague input triggers exactly ONE clarification question** if input matches ANY of:
- Contains "everything", "all", "一切", "所有" about a topic without specifics
- Single word or phrase without context (e.g., just "login", just "登录", just "auth")
- Multiple unrelated topics in one message (e.g., "the login button and the dashboard charts")

**Clarification (if triggered)**:
```
To write a useful spec, could you clarify: [one specific question about the ambiguous part]?
```
After ONE clarification answer, proceed to Step 3 regardless.

**If NOT vague** (input has enough to write): Proceed directly to Step 3.

### Step 3: Background exploration (non-blocking)

If the user's description mentions any specific file, component, feature, or technical term:
```
Agent(subagent_type="Explore", run_in_background=true):
  "Find and summarize <what user mentioned>. Report: file paths, current behavior, relevant code snippets. Thoroughness: medium."
```
Do NOT wait for exploration to finish. Proceed to Step 4 immediately.

### Step 4: Write spec file

1. Read the template at `~/.claude/templates/overnight-spec.md`. If missing, report error and stop.

2. Generate the output path:
   ```
   docs/dev/specs/spec-<YYYYMMDD-HHMMSS>.md
   ```
   Create `docs/dev/specs/` if it does not exist.

3. Populate the template:
   - `<issue_description>` → issue from Step 1/2
   - `<pipeline_index>` → `standalone`
   - `<session_id>` → `manual`
   - `<ISO-8601>` → current timestamp
   - Section 5 → user's description verbatim (and any clarification answer)
   - Section 1 → populated only if exploration results arrived and contain useful file/behavior context
   - Section 8 → populated only if user explicitly mentioned constraints, edge cases, or watch-outs

4. Write the spec. Do NOT ask for confirmation before writing.

### Step 5: Invoke spec subagent

**Count monolith lines** (needed by spec subagent):
```bash
MONOLITH_LINES=$(wc -l < docs/dev/specs/<spec-id>.md)
```

**Invoke spec subagent for agent selection + view creation + checkpoints**:
```
Use Agent tool with:
- description: "Spec agent: split + checkpoints for <spec-id>"
- prompt: "
  You are the spec subagent. Read and follow the instructions in ~/.claude/agents/spec.md EXACTLY.
  Spec id: <spec-id>
  Monolith: docs/dev/specs/<spec-id>.md
  Monolith lines: <MONOLITH_LINES>
  Output folder: docs/dev/specs/<spec-id>/
  Project dir: <$CLAUDE_PROJECT_DIR>
  Execute Phase 0 (read spec, decide relevant agents).
  Then Phase 1 (intelligent extraction if monolith > 200 lines).
  Then Phase 2 (checkpoint generation).
  Return a JSON summary."
```

### Step 6: QA validation of split quality

```
Use Agent tool with:
- subagent_type: "qa"
- description: "Validate spec split quality for <spec-id>"
- prompt: "
  Validate the spec split at docs/dev/specs/<spec-id>/views/.
  Monolith: docs/dev/specs/<spec-id>.md

  Check these criteria:
  1. ROLE MANDATE: If the spec defines role responsibilities (look for 'role split',
     'pipeline', agent-specific duties), verify each view's Role Mandate section
     accurately reflects the spec's definition. Flag any view where the agent's
     mandate is missing or contradicts the spec.
  2. AGENT SELECTION: Are the selected agents consistent with the spec's defined
     pipeline? Flag any agent that was included but isn't in the spec's pipeline,
     or any pipeline agent that was excluded.
  3. COVERAGE: Run python3 /root/bin/spec-verify.py --monolith docs/dev/specs/<spec-id>.md --views-dir docs/dev/specs/<spec-id>/views/.
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
If QA passes: proceed to Step 7.

### Step 7: Mark and display

```bash
echo "split-complete: $(date -Iseconds)" > docs/dev/specs/<spec-id>/.split-complete
```

Display confirmation:
```
Spec created: <absolute path>
Split marker: docs/dev/specs/<spec-id>/.split-complete
Output folder: docs/dev/specs/<spec-id>/

Sections populated:
- Section 5 (Acceptance Criterion): populated
- Section 1 (Before): <populated from exploration | empty>
- Section 8 (Attention Notes): <populated | empty>

Usage:
  /dev                    ← auto-detects this spec
  /dev --spec <path>      ← explicit path
  /dev-command            ← auto-detects this spec
  /dev-overnight <time>   ← auto-detects this spec
```

---

## Important Rules

- **Read the template at runtime** from `~/.claude/templates/overnight-spec.md`. Never hardcode template content.
- **Preserve template structure exactly** — only replace designated placeholders and `_Not yet populated._` markers.
- **Do not modify any existing files** except the spec file being created.
- **Create the output directory** (`docs/dev/specs/`) if it does not exist.
- **Use absolute paths** in all output messages.
- **Mode 2** is the default when no arguments are given. It asks one question, then writes immediately.
- **Output folder is created by the spec subagent** during Phase 0. The subagent decides which agents get views based on spec content. Legacy specs lacking an output folder remain valid — `/dev*` falls back gracefully.
