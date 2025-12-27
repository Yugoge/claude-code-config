# Git Hooks - Pre-Commit Tracking Solution

This directory contains templates for git hooks that ensure all files are tracked before commits.

## Overview

The pre-commit hook system detects untracked files before commits and provides three behavioral modes:
- **Warn Mode** (default): Displays warnings but allows commits
- **Block Mode**: Prevents commits if untracked files exist
- **Auto-Stage Mode**: Automatically stages all files before commit

## Installation

### Install in Current Repository

```bash
~/.claude/hooks/install-git-hooks.sh
```

### Install in Specific Repository

```bash
~/.claude/hooks/install-git-hooks.sh /path/to/repository
```

The installer will:
1. Verify the target is a git repository
2. Backup any existing pre-commit hook
3. Copy the hook template to `.git/hooks/pre-commit`
4. Make the hook executable

## Configuration

Configure behavior via environment variables in `~/.claude/settings.json`:

```json
{
  "env": {
    "GIT_AUTO_STAGE_ALL": "0",      // Auto-stage all files (0=off, 1=on)
    "GIT_BLOCK_ON_UNTRACKED": "0",  // Block commits (0=off, 1=on)
    "GIT_WARN_UNTRACKED": "1"       // Show warnings (0=off, 1=on)
  }
}
```

### Configuration Presets

#### Passive Mode (Default - Recommended)
```json
{
  "env": {
    "GIT_AUTO_STAGE_ALL": "0",
    "GIT_BLOCK_ON_UNTRACKED": "0",
    "GIT_WARN_UNTRACKED": "1"
  }
}
```
Shows warnings but doesn't auto-stage or block. Best for manual control.

#### Active Mode
```json
{
  "env": {
    "GIT_AUTO_STAGE_ALL": "1",
    "GIT_BLOCK_ON_UNTRACKED": "0",
    "GIT_WARN_UNTRACKED": "1"
  }
}
```
Automatically stages all files before commits. Maximum convenience.

#### Strict Mode
```json
{
  "env": {
    "GIT_AUTO_STAGE_ALL": "0",
    "GIT_BLOCK_ON_UNTRACKED": "1",
    "GIT_WARN_UNTRACKED": "1"
  }
}
```
Blocks commits with untracked files. Forces explicit staging. Maximum safety.

#### Silent Mode
```json
{
  "env": {
    "GIT_AUTO_STAGE_ALL": "0",
    "GIT_BLOCK_ON_UNTRACKED": "0",
    "GIT_WARN_UNTRACKED": "0"
  }
}
```
No warnings or auto-staging. Minimal intervention.

## How It Works

### Pre-Commit Hook Flow

```
git commit
    ↓
Pre-commit hook executes
    ↓
Check for untracked files (respecting .gitignore)
    ↓
    ├─ No untracked files → Allow commit
    │
    ├─ Auto-Stage Mode (GIT_AUTO_STAGE_ALL=1)
    │   ↓
    │   Run: git add .
    │   ↓
    │   Allow commit with all files
    │
    ├─ Block Mode (GIT_BLOCK_ON_UNTRACKED=1)
    │   ↓
    │   Display untracked files
    │   ↓
    │   Block commit (exit 1)
    │
    └─ Warn Mode (default)
        ↓
        Display untracked files
        ↓
        Allow commit without those files
```

## Bypassing the Hook

In cases where you need to commit without the hook running:

```bash
git commit --no-verify -m "Your commit message"
```

**Use sparingly** - bypassing defeats the purpose of the safety check.

## Troubleshooting

### Hook Not Running

**Check if hook is installed:**
```bash
ls -la .git/hooks/pre-commit
```

**Check if hook is executable:**
```bash
[ -x .git/hooks/pre-commit ] && echo "Executable" || echo "Not executable"
```

**Make executable if needed:**
```bash
chmod +x .git/hooks/pre-commit
```

### Hook Blocking Wanted Commits

**Option 1: Add to .gitignore**
```bash
echo 'filename' >> .gitignore
```

**Option 2: Bypass once**
```bash
git commit --no-verify
```

**Option 3: Change mode**
Edit `~/.claude/settings.json` and set `GIT_BLOCK_ON_UNTRACKED` to `"0"`.

### Hook Not Detecting Files

**Verify git status:**
```bash
git status --porcelain
git ls-files --others --exclude-standard
```

**Check .gitignore:**
- Files in `.gitignore` are correctly excluded from detection
- Verify the file isn't accidentally ignored

### Colors Not Displaying

The hook uses ANSI color codes. If colors aren't displaying:
- Ensure your terminal supports colors
- Check `TERM` environment variable: `echo $TERM`
- Claude Code terminal supports colors by default

## Uninstallation

To remove the hook:

```bash
rm .git/hooks/pre-commit
```

If a backup was created during installation, restore it:

```bash
mv .git/hooks/pre-commit.backup.YYYYMMDD_HHMMSS .git/hooks/pre-commit
```

## Files

- **pre-commit** - Hook template installed to `.git/hooks/pre-commit`
- **~/.claude/hooks/pre-commit-check.sh** - Core detection logic
- **~/.claude/hooks/install-git-hooks.sh** - Installation script
- **README.md** - This documentation

## Related Components

This pre-commit hook is part of a comprehensive git tracking solution that includes:
- **Post-commit warnings** - Alerts after commits if untracked files remain
- **/pull command** - Safe git pull with stash management
- **/push command** - Validated push with auto-staging option

See the main documentation: `~/.claude/docs/git-tracking-solution-plan.md`

## Support

For issues or questions:
1. Check this README troubleshooting section
2. Review the full plan: `~/.claude/docs/git-tracking-solution-plan.md`
3. Test manually: `~/.claude/hooks/pre-commit-check.sh`
