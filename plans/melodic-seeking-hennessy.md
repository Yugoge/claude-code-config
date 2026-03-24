# Plan: Remove Step 0 References (Migrated to Hook System)

## Context

The workflow previously required an explicit "Step 0: Initialize Workflow Checklist" that the agent had to manually mark as in_progress/completed. This has been replaced by a hook-based system (`hook-checklist-userprompt.py`) that automatically initializes the checklist when a slash command is detected. Step 0 is now dead code — the hooks handle initialization transparently, so all Step 0 references must be removed.

## Files to Modify

### 1. `/root/.claude/scripts/todo/dev.py`
- Remove the "Step 0: Initialize Workflow Checklist" entry from the todos list (line ~17)
- Decrease `blocking_count` (or equivalent) by 1 to reflect removal

### 2. `/root/.claude/scripts/todo/dev-command.py`
- Remove the "Step 0: Initialize workflow checklist" entry (line ~12)
- Decrease `blocking_count` by 1

### 3. `/root/.claude/commands/dev.md`
- Remove the entire "## Step 0: Initialize Workflow Checklist" section (~line 18-30)
- This section instructs running `dev.py` manually — now done by hook

### 4. `/root/.claude/commands/dev-command.md`
- Remove the entire "## Step 0: Initialize Workflow Checklist" section (~line 16-28)

### 5. `/root/.claude/.todos.json`
- Remove stale "Step 0: Initialize workflow checklist" entry from cached todos

## What NOT to Touch

- `/root/.claude/hooks/` — the hook system is the replacement, do not modify
- `/root/.claude/plans/lovely-sparking-goblet.md` — historical plan doc, leave as-is
- Test reports/archive files — reference only

## Verification

After changes:
1. Run `source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/dev.py` — should show todos starting from Step 1, no Step 0
2. Run `source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/dev-command.py` — same check
3. Review `dev.md` and `dev-command.md` to confirm Step 0 section is gone
4. Check `.todos.json` has no Step 0 entry
