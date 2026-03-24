# Plan: CLAUDE.md + INDEX.md Auto-Sync System

## Context

Documentation across projects frequently drifts from actual code state — command counts become wrong, agent lists go stale, INDEX.md files miss new entries. This causes AI to hallucinate based on outdated context. The fix: a PostToolUse hook that auto-patches documentation whenever structural files change, using HTML comment markers to delimit auto-generated sections.

Design principles:
- **Fractal docs**: root map (CLAUDE.md) → module inventory (INDEX.md) → file head
- **Hook enforcement**: engineering constraint, not prompt instruction
- **Quantified thresholds**: exact counts, not "some commands"

## Architecture: Single Hook + Marker System

```
Write/Edit triggers
    → posttool-doc-sync.py (stdin JSON → file_path)
    → Fast path filter: is file in watched dir?
        → NO: exit 0 (< 1ms)
        → YES: regen INDEX.md + patch CLAUDE.md markers
```

## Implementation Steps

### Step 1: Create `posttool-doc-sync.py` (~200 lines)

**File:** `/root/.claude/hooks/posttool-doc-sync.py`

**Logic:**
1. Parse stdin JSON, extract `tool_input.file_path`
2. Skip if file is INDEX.md/CLAUDE.md (prevent recursion)
3. Check if path matches watched dirs: `.claude/{commands,agents,hooks,skills,scripts}/`
4. If match → regen INDEX.md for that directory
5. If match → patch CLAUDE.md auto-sections (counts, lists)
6. Always exit 0 (never block workflow)

**INDEX.md regeneration:**
- List all files (excluding INDEX.md, README.md)
- Extract first heading from each .md file as description
- Compare against existing INDEX.md file list — skip rewrite if unchanged
- Write with timestamp

**CLAUDE.md section patching:**
- Find `<!-- AUTO:{id} -->` ... `<!-- /AUTO:{id} -->` markers
- Replace content between markers with freshly generated data
- If no markers present → no-op (opt-in model)

**Supported marker IDs:**

| Marker | Source | Scope |
|--------|--------|-------|
| `docker-services` | Parse `deploy/docker-compose.yml` | Global only |
| `systemd-services` | `systemctl list-unit-files` | Global only |
| `command-list` | Scan `.claude/commands/*.md` | Per-project |
| `agent-list` | Scan `.claude/agents/*.md` | Per-project |
| `skill-list` | Scan `.claude/skills/*/` | Per-project |
| `last-updated` | `date` | All |

**Performance:** < 350ms worst case, < 10ms for non-matching paths.

### Step 2: Register in global settings.json

Add to existing `Write|Edit|NotebookEdit` PostToolUse matcher at `/root/.claude/settings.json`:

```json
{
  "type": "command",
  "command": "python3 \"$HOME/.claude/hooks/posttool-doc-sync.py\"",
  "stdin_json": true,
  "on_error": "ignore"
}
```

### Step 3: Add markers to global CLAUDE.md

**File:** `/root/.claude/CLAUDE.md`

Wrap existing dynamic sections with marker comments:
- Lines ~207-220 (Docker table): `<!-- AUTO:docker-services -->` / `<!-- /AUTO:docker-services -->`
- Lines ~223-231 (Systemd table): `<!-- AUTO:systemd-services -->` / `<!-- /AUTO:systemd-services -->`
- Line 4 (last updated): `<!-- AUTO:last-updated -->` / `<!-- /AUTO:last-updated -->`

### Step 4: Add markers to project CLAUDE.md files

- `/root/multi-asset-portfolio/CLAUDE.md` — command-list, agent-list, skill-list
- `/root/knowledge-system/.claude/CLAUDE.md` — command-list, agent-list
- `/root/knowledge-system-jade/.claude/CLAUDE.md` — same as above

### Step 5: Create `/doc-sync` slash command for manual full sweep

**File:** `/root/.claude/commands/doc-sync.md`

Scans all known project roots, regenerates all INDEX.md files, patches all CLAUDE.md markers. The "full rebuild" equivalent of what the hook does incrementally.

## Key Files

| File | Action |
|------|--------|
| `/root/.claude/hooks/posttool-doc-sync.py` | CREATE — main hook |
| `/root/.claude/settings.json` | EDIT — add hook to PostToolUse matcher |
| `/root/.claude/CLAUDE.md` | EDIT — add AUTO markers |
| `/root/multi-asset-portfolio/CLAUDE.md` | EDIT — add AUTO markers |
| `/root/knowledge-system/.claude/CLAUDE.md` | EDIT — add AUTO markers |
| `/root/knowledge-system-jade/.claude/CLAUDE.md` | EDIT — add AUTO markers |
| `/root/.claude/commands/doc-sync.md` | CREATE — manual sweep command |

## Reuse

- **Pattern from** `posttool-todo-tracker.py`: stdin JSON parsing, exit-0-always, Path handling
- **Supersedes** `generate-folder-index.sh`: Python version produces compatible INDEX.md format
- **`replace_section()` algo**: find start/end markers, replace between them

## Safety

- Markers are opt-in: no markers = no auto-edit
- CLAUDE.md/INDEX.md paths are excluded from triggering (no recursion)
- All functions wrapped in try/except → exit 0
- `on_error: "ignore"` in registration

## Verification

1. Create a test file: `touch ~/.claude/commands/test-doc-sync.md`
2. Verify INDEX.md regenerated with new entry
3. Verify CLAUDE.md counts updated (if markers present)
4. Delete test file, verify INDEX.md updated again
5. Check performance: `time python3 ~/.claude/hooks/posttool-doc-sync.py < test-input.json`
