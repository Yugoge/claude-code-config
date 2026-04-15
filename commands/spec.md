---
description: Create, validate, and list spec files for any dev workflow (/dev, /dev-overnight, or standalone reference)
---

# /spec: General-Purpose Spec Manager

You manage spec files based on the 8-section spec template. Parse `$ARGUMENTS` to determine the mode, then execute the appropriate workflow below.

**Arguments**: `$ARGUMENTS`

---

## Argument Parsing

Parse the arguments to determine the mode:

1. **`--validate <path>`**: Validation mode
2. **`--list`**: List mode
3. **Non-empty text** (no flags): Quick creation mode (inline description)
4. **Empty / no arguments**: **Interview mode** (recommended for complex issues)

---

## Mode 1: Quick Creation (inline description)

**Trigger**: `$ARGUMENTS` contains text that is NOT a flag (e.g., `/spec fix the login button styling`)

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

4. Write the spec and display confirmation:
   ```
   Spec created: <absolute path>

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

## Mode 2: Interview Mode

**Trigger**: `$ARGUMENTS` is empty

**Philosophy**: You are an interviewer. Your job is to ask questions, listen, and record. NEVER summarize, paraphrase, or omit anything the user says. Record their words verbatim. If you don't understand something, ask immediately — don't guess or fill in blanks.

### Interview Rules (MANDATORY)

1. **One question at a time.** Never ask multiple questions in one message.
2. **Record verbatim.** User's words go into the spec exactly as spoken. No editing, no "cleaning up", no rewording.
3. **Never omit.** If the user provides a 10-line answer, all 10 lines go into the spec. Do not condense.
4. **Ask when confused.** If something is unclear, ambiguous, or uses unfamiliar terms — ask a follow-up immediately. Do not assume or infer.
5. **Background exploration.** When the user mentions a file, component, feature, or technical term, immediately dispatch an Explore agent in the background to gather context. Do NOT wait for the exploration to finish before asking the next question — keep the interview flowing.
6. **No suggestions.** Do not suggest solutions, approaches, or improvements. You are recording what the user wants, not advising them.
7. **Confirm before writing.** After all questions are answered, show the user a complete preview of the spec content (Sections 1 and 5) and ask for confirmation before writing the file.

### Interview Flow

**Step 1: Open**

Say exactly:
```
Starting spec interview. I'll ask questions one at a time to build a complete spec.

What's the issue or feature you want to specify?
```

**Step 2: Deep-dive on the problem**

After the user describes the issue:

- If the user mentions specific files, components, or code areas → dispatch an Explore agent in the background:
  ```
  Agent(subagent_type="Explore", run_in_background=true):
    "Find and summarize <what the user mentioned>. Report: file paths, current behavior, relevant code snippets. Thoroughness: medium."
  ```
- Ask the next question:
  ```
  What does the current behavior look like? (What's happening now that shouldn't be, or what's missing?)
  ```

**Step 3: Acceptance criteria**

```
What does "done" look like? How will you know this is fixed/complete?
```

Record the answer verbatim into Section 5. If the answer is vague (e.g., "it should work"), push back:
```
Can you be more specific? For example: what should the user see, what values should appear, what behavior should change?
```

**Step 4: Context and constraints (optional)**

```
Anything else I should know? Constraints, edge cases, things to watch out for, related issues? (Say "no" to skip)
```

If the user says "no" or equivalent, skip. Otherwise record into Section 8 (Attention Notes).

**Step 5: Incorporate exploration results**

If any background Explore agents have returned results by now:
- Review findings silently
- If the findings reveal relevant context (e.g., the file the user mentioned is at a specific path, or there's related code), incorporate file paths and factual context into Section 1 (Before)
- If the findings raise new questions (e.g., the component the user mentioned doesn't exist, or the behavior differs from what the user described), ask the user about the discrepancy immediately:
  ```
  I looked at <what you mentioned> and found <factual observation>. Does this match your understanding, or is there something I'm missing?
  ```

**Step 6: Preview and confirm**

Present the complete spec preview to the user:
```
Here's the spec I'll create:

**Issue**: <issue description>

**Section 1 (Before)**:
<content or "empty — will be populated by BA">

**Section 5 (Acceptance Criterion)**:
<verbatim user content>

**Section 8 (Attention Notes)**:
<content or "empty">

Write this spec? (yes/no)
```

Wait for user confirmation.

**Step 7: Write the spec**

1. Read the template at `~/.claude/templates/overnight-spec.md`. If missing, report error and stop.
2. Generate the output path: `docs/dev/specs/spec-<YYYYMMDD-HHMMSS>.md`
3. Create `docs/dev/specs/` if needed.
4. Populate:
   - `<issue_description>` → issue from Step 1
   - `<pipeline_index>` → `standalone`
   - `<session_id>` → `manual`
   - `<ISO-8601>` → current timestamp
   - Section 1 → Before state (if provided + exploration findings)
   - Section 5 → Acceptance criterion verbatim
   - Section 8 → Attention notes (if provided)
5. Write the file and display:
   ```
   Spec created: <absolute path>

   Sections populated:
   - Section 1 (Before): <populated or empty>
   - Section 5 (Acceptance Criterion): populated
   - Section 8 (Attention Notes): <populated or empty>

   Usage:
     /dev                                   ← auto-detects this spec
     /dev --spec <path>                     ← explicit path
     /dev-command                           ← auto-detects this spec
     /dev-command --spec <path>             ← explicit path
     /dev-overnight <end-time>              ← auto-detects this spec
     /dev-overnight <end-time> --spec <path> ← explicit path
   ```

---

## Mode 3: Validate Spec

**Trigger**: `$ARGUMENTS` starts with `--validate`

**Steps**:

1. Extract the file path from `$ARGUMENTS` (the token after `--validate`).

2. Read the file. If it does not exist, report an error and stop.

3. Check for all 8 sections by looking for these headings:
   - `## Section 1: Before`
   - `## Section 2: What Was Attempted`
   - `## Section 3: What Was Changed`
   - `## Section 4: Current State`
   - `## Section 5: User's Acceptance Criterion`
   - `## Section 6: Why Not Met`
   - `## Section 7: What Must Be Done`
   - `## Section 8: Attention Notes`

4. For each section, determine if it is:
   - **Populated**: contains content other than `_Not yet populated._` or HTML comments
   - **Empty**: contains only `_Not yet populated._` or HTML comments

5. Display a validation report:
   ```
   Spec validation: <path>

   Structure: [VALID|INVALID] (N/8 sections found)

   Section status:
     1. Before:                    [populated|empty]
     2. What Was Attempted:        [populated|empty]
     3. What Was Changed:          [populated|empty]
     4. Current State:             [populated|empty]
     5. Acceptance Criterion:      [populated|empty]
     6. Why Not Met:               [populated|empty]
     7. What Must Be Done:         [populated|empty]
     8. Attention Notes:           [populated|empty]

   Header fields:
     Issue: <extracted from # heading>
     Pipeline: <value>
     Session: <value>
     Created: <value>

   Ready for /dev: [YES|NO] (requires Section 5 populated)
   ```

---

## Mode 4: List Specs

**Trigger**: `$ARGUMENTS` starts with `--list`

**Steps**:

1. Check if `docs/dev/specs/` directory exists. If not, report "No specs directory found. Create one with /spec <description>." and stop.

2. List all `.md` files in `docs/dev/specs/`.

3. For each file, extract:
   - Filename
   - Issue description (from `# Spec: ...` heading)
   - Created date (from `**Created**:` field)
   - Whether Section 5 is populated

4. Display as a table:
   ```
   Spec files in docs/dev/specs/:

   | File | Issue | Created | Section 5 |
   |------|-------|---------|-----------|
   | spec-20260412-140000.md | fix the login button | 2026-04-12T14:00:00 | populated |

   Total: N spec files
   Most recent: <path>  ← /dev will auto-detect this
   ```

---

## Important Rules

- **Read the template at runtime** from `~/.claude/templates/overnight-spec.md`. Never hardcode template content.
- **Preserve template structure exactly** — only replace designated placeholders and `_Not yet populated._` markers.
- **Do not modify any existing files** except the spec file being created.
- **Create the output directory** (`docs/dev/specs/`) if it does not exist.
- **Use absolute paths** in all output messages.
- **Interview mode is the default** when no arguments are given. It produces higher quality specs than inline mode.
