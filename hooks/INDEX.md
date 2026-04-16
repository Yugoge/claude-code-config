# hooks

*Last updated: 2026-04-16T08:16:58Z*
**Total entries**: 74
**Convention**: kebab

## Tree
```
hooks/
├── doc_sync/
│   ├── `claude.py` - CLAUDE.md auto-creation and patching.
│   ├── `docker.py` - Parse docker-compose.yml and generate markdown table.
│   ├── `extract.py` - Extract description from various file types.
│   ├── `main.py` - Main entry point for doc-sync hook.
│   ├── `patch.py` - Patch CLAUDE.md dynamic sections using AUTO markers.
│   ├── `regen_index.py` - Regenerate INDEX.md for a directory.
│   ├── `regen_readme.py` - Regenerate README.md for a directory.
│   ├── `systemd.py` - Query systemctl for known services and generate markdown table.
│   └── `tree.py` - Build directory trees for INDEX.md.
├── git-hooks/
│   ├── `post-commit-auto-push` - unknown file
│   └── `pre-commit` - unknown file
├── lib/
│   ├── `checkpoint-core.sh` - ============================================================================
│   └── `todo_canonical.py` - Shared canonical todo validation utilities
├── `audit-slashcommand.sh` - audit-slashcommand.sh
├── `auto-commit.sh` - ============================================================================
├── `checkpoint.sh` - checkpoint.sh - Manual /checkpoint command
├── `ensure-git-repo.sh` - ============================================================================
├── `fswatch-manager.sh` - fswatch-manager.sh - Manage git-fswatch instances
├── `git-fswatch.sh` - git-fswatch.sh - Comprehensive Git file watcher using fswatch
├── `git-fswatch@.service` - service file
├── `hook-todo-injection.py` - Global PreToolUse Hook: Todo Injection for Slash Commands
├── `install-auto-sync.sh` - install-auto-sync.sh - Quick installer for auto-sync features
├── `install-git-hooks.sh` - install-git-hooks.sh - Install pre-commit hooks into git repositories
├── `install-protection-all.sh` - install-protection-all.sh - Automatically install protection for all git repos
├── `install.sh` - ============================================================================
├── `post-commit-warn.sh` - post-commit-warn.sh - Warn about untracked files after commit
├── `post_tool_use.sh` - PostToolUse Hook - Code quality hints after file modifications
├── `posttool-command-frontmatter-validate.py` - PostToolUse Hook: Validate .claude/commands/*.md frontmatter structure
├── `posttool-doc-sync.py` - PostToolUse Hook: Auto-sync INDEX.md and CLAUDE.md when structural files change
├── `posttool-git-checkpoint.sh` - posttool-git-checkpoint.sh - PostToolUse checkpoint trigger
├── `posttool-git-warn.sh` - post-commit-warn.sh - Warn about untracked files after commit
├── `posttool-overnight-file-check.py` - PostToolUse:Agent Hook: Verify overnight subagent output files exist
├── `posttool-overnight-loop.py` - PostToolUse:TodoWrite Hook: Overnight Loop Detection
├── `posttool-subagent-track.py` - PostToolUse:Agent Hook: Track subagent invocations in workflow bookmark
├── `posttool-todo-count.py` - PostToolUse Hook: Enforce canonical todo count immediately after TodoWrite
├── `posttool-todo-sequence.py` - PostToolUse Hook: Enforce one-step-at-a-time progression in workflow checklists
├── `posttool-todo-tracker.py` - PostToolUse Hook: Output checklist progress after every TodoWrite call
├── `pre-commit-check.sh` - pre-commit-check.sh - Detect untracked files before commit
├── `pre_slashcommand_validate.sh` - pre_slashcommand_validate.sh
├── `pre_tool_use_safety.sh` - PreToolUse Safety Hook - Warn before dangerous operations
├── `pretool-bash-safety.sh` - PreToolUse Safety Hook - Warn or block before dangerous operations
├── `pretool-block-enterworktree.sh` - PreToolUse hook: Block EnterWorktree tool
├── `pretool-block-production-files.sh` - PreToolUse hook: Block Write/Edit to production paths from dev environment
├── `pretool-block-production.sh` - PreToolUse hook: Block Playwright navigation to production URLs
├── `pretool-docker-build-guard.sh` - Hook: PreToolUse:Bash
├── `pretool-orchestrator-gate.py` - PreToolUse Hook: Orchestrator Gate
├── `pretool-overnight-hook-guard.py` - PreToolUse Hook: Overnight session file modification guard
├── `pretool-quality-gate.py` - PreToolUse Hook: Quality gate for Write/Edit operations
├── `pretool-read-size-guard.py` - PreToolUse Hook: Read Size Guard
├── `pretool-subagent-enforce.py` - PreToolUse Hook: Enforce subagent invocation at designated workflow steps
├── `pretool-todo-validate.py` - PreToolUse Hook: Validate TodoWrite input BEFORE execution
├── `pretool-workflow-gate.py` - PreToolUse Hook: Require TodoWrite/TodoRead acknowledgment before other tools
├── `pretool-worktree-guard.sh` - PreToolUse hook: Detect stale agent worktrees before ANY tool call
├── `pretool-write-guard.sh` - PreToolUse Hook - Block Write tool from overwriting existing files
├── `project-settings-template.json` - json config
├── `prompt-workflow.py` - UserPromptSubmit Hook: Checklist Injection for Slash Commands
├── `protection-status.sh` - protection-status.sh - Display protection status for all git repositories
├── `pull.sh` - pull.sh - Executable version of /pull command
├── `push.sh` - push.sh - Executable version of /push command
├── `QUICKSTART.md` - 🚀 Quick Start Guide
├── `README-TODO-INJECTION.md` - Global Todo Injection Hook
├── `session-git-init.sh` - ============================================================================
├── `session-info.sh` - s-info.sh — SessionStart: display environment info + tool quick reference
├── `session_start.sh` - SessionStart Hook - Display working environment info
├── `smart-checkpoint.sh` - smart-checkpoint.sh - DEPRECATED, scheduled for deletion
├── `start-fswatch-all.sh` - start-fswatch-all.sh - Start fswatch monitoring for all important repositories
├── `stop-git-commit.sh` - ============================================================================
├── `stop-overnight-timelock.py` - Stop Hook: Block conversation termination until overnight end-time
├── `stop-workflow-enforce.py` - Stop Hook: Enforce workflow structural integrity before allowing Claude to stop
├── `subagent-stop-diff-check.sh` - SubagentStop hook: flag large diffs without minimum-diff justification
└── `userprompt-doc-sync-check.py` - UserPromptSubmit Hook: Periodic file deletion detection for doc-sync
```

---
*Auto-generated by doc-sync hook.*