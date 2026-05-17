---
description: "Regenerate all INDEX.md files and patch CLAUDE.md auto-sections"
disable-model-invocation: true
---

# /doc-sync — Full Documentation Synchronization

Run a full sweep of the documentation auto-sync system across the current project.

## What It Does

1. **Regenerate INDEX.md** for all `.claude/` subdirectories (commands, agents, hooks, skills, scripts)
2. **Patch CLAUDE.md** auto-generated sections (delimited by `<!-- AUTO:{id} -->` markers)
3. Report what changed

## Steps

1. Scan `.claude/commands/`, `.claude/agents/`, `.claude/hooks/`, `.claude/skills/`, `.claude/scripts/`
2. For each directory that exists: regenerate its INDEX.md with current file inventory
3. Read the project's CLAUDE.md and update all `<!-- AUTO:... -->` sections:
   - `command-list` — enumerate commands
   - `agent-list` — enumerate agents
   - `skill-list` — enumerate skill directories
   - `claude-inventory` — count all categories
   - `docker-services` — parse docker-compose.yml (global only)
   - `systemd-services` — query systemctl for services listed in `<project>/.claude/doc-sync.json` (never patched into the global `~/.claude/CLAUDE.md`)
   - `last-updated` — set today's date
4. Report changes made
5. After reviewing: if satisfied with the updated files, commit them (`git add` the changed INDEX.md and CLAUDE.md files, then `git commit`) and run `/push` to publish to remote

## Usage

```
/doc-sync
```

No arguments needed. Operates on the current project directory.

## How Markers Work

CLAUDE.md sections are opt-in. To make a section auto-updatable, wrap it:

```markdown
<!-- AUTO:command-list -->
(this content will be auto-replaced)
<!-- /AUTO:command-list -->
```

Sections without markers are never touched.

## Project Config: `.claude/doc-sync.json`

Infrastructure AUTO blocks (`systemd-services`) read their source list from a project-local config. Example `<project>/.claude/doc-sync.json`:

```json
{
  "systemd_services": ["my-daemon", "my-worker"]
}
```

When missing or empty: the `systemd-services` block is left unchanged. The global `~/.claude/CLAUDE.md` is guarded — `systemd-services` and `docker-services` AUTO blocks are never patched there, even if a config exists.
