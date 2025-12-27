# Project Settings Template Guide

This guide explains how to configure Claude Code for new projects using the recommended template.

## Quick Start

### For New Projects

```bash
# Create .claude directory
mkdir -p /path/to/your-project/.claude

# Copy template
cp ~/.claude/templates/settings.json.template /path/to/your-project/.claude/settings.json

# Customize for your project (optional)
nano /path/to/your-project/.claude/settings.json
```

### For Existing Projects

```bash
# Backup existing settings
cp /path/to/your-project/.claude/settings.json /path/to/your-project/.claude/settings.json.backup

# Add SlashCommand permission if missing
# Edit the file and add "SlashCommand" to the "allow" array
```

---

## Template Features

### ✅ Pre-configured Permissions

The template includes:

#### **Allow List** (Auto-approved tools)
- **Core Tools**: `Read`, `Glob`, `Grep`, `WebSearch`, `SlashCommand`
- **Git Operations**: `git status`, `git log`, `git diff`, `git add`, `git commit`
- **Language Runtimes**: `python`, `python3`, `node`, `npm`, `yarn`, `pnpm`, `pip`
- **File Operations**: `ls`, `find`, `mkdir`, `touch`, `cat`, `head`, `tail`, `wc`, `tree`, `cp`, `mv`

#### **Deny List** (Blocked operations)
- **Destructive Commands**: `rm -rf /`, `sudo`, `shutdown`
- **Sensitive Files**: `.env`, `credentials`, `secrets`, `passwords`
- **Force Operations**: `git push --force`, `git push -f`

#### **Ask List** (Require user approval)
- **Remote Operations**: `git push`
- **Package Installation**: `pip install`, `npm install`, `yarn install`
- **Dangerous Deletions**: `rm -rf`
- **Config Edits**: `.claude/**`, `package.json`, `requirements.txt`

### ✅ Smart Checkpoint Hook

Automatically creates git checkpoints after file edits:
- Triggers on `Write`, `Edit`, `NotebookEdit`
- Uses `smart-checkpoint.sh` for automatic commits
- Configurable threshold (default: 10 changes)

---

## Customization Guide

### Adding Project-Specific Permissions

#### Example 1: Python Data Science Project

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "WebSearch",
      "SlashCommand",
      "Bash(jupyter:*)",
      "Bash(pytest:*)",
      "Write(notebooks/**)",
      "Write(data/output/**)",
      "Edit(src/**/*.py)"
    ],
    "deny": [
      "Write(data/raw/**)",
      "Edit(data/raw/**)"
    ],
    "ask": [
      "Write(*.ipynb)",
      "Edit(*.ipynb)"
    ]
  }
}
```

**Rationale**:
- Allow writing to processed data, not raw data
- Ask before modifying notebooks (version control)
- Auto-approve pytest execution

---

#### Example 2: Node.js Web Project

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "WebSearch",
      "SlashCommand",
      "Bash(npm run lint:*)",
      "Bash(npm run test:*)",
      "Bash(npm run build:*)",
      "Write(src/**)",
      "Write(tests/**)",
      "Edit(src/**/*.ts)",
      "Edit(tests/**/*.test.ts)"
    ],
    "deny": [
      "Write(dist/**)",
      "Write(node_modules/**)"
    ],
    "ask": [
      "Write(package.json)",
      "Edit(package.json)",
      "Write(tsconfig.json)",
      "Bash(npm install:*)"
    ]
  }
}
```

**Rationale**:
- Auto-approve scripts (`npm run`)
- Protect build artifacts and dependencies
- Require approval for config changes

---

#### Example 3: Go Project

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "WebSearch",
      "SlashCommand",
      "Bash(go:*)",
      "Bash(gofmt:*)",
      "Bash(golint:*)",
      "Write(cmd/**)",
      "Write(internal/**)",
      "Write(pkg/**)",
      "Edit(**/*.go)"
    ],
    "deny": [
      "Write(vendor/**)",
      "Bash(go get:*)"
    ],
    "ask": [
      "Write(go.mod)",
      "Edit(go.mod)",
      "Write(go.sum)"
    ]
  }
}
```

---

### Adding Custom Hooks

#### PreToolUse Hook (Safety Check)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash\\(rm.*\\)",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/pre_tool_use_safety.sh",
            "on_error": "block"
          }
        ]
      }
    ]
  }
}
```

#### PostToolUse Hook (Testing)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write\\(src/.*\\.py\\)|Edit\\(src/.*\\.py\\)",
        "hooks": [
          {
            "type": "command",
            "command": "python -m pytest tests/ -x",
            "on_error": "warn"
          }
        ]
      }
    ]
  }
}
```

#### SessionStart Hook (Project Initialization)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Project: My App | Branch: $(git branch --show-current)'",
            "on_error": "ignore"
          }
        ]
      }
    ]
  }
}
```

---

## Environment Variables

Add project-specific environment variables:

```json
{
  "env": {
    "PROJECT_NAME": "my-app",
    "GIT_AUTO_STAGE_ALL": "0",
    "GIT_PUSH_AUTO_STAGE": "1",
    "GIT_CHECKPOINT_THRESHOLD": "10",
    "DISABLE_TELEMETRY": "1"
  }
}
```

### Common Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | Keep working directory | `"1"` |
| `GIT_AUTO_STAGE_ALL` | Auto-stage all changes | `"0"` |
| `GIT_PUSH_AUTO_STAGE` | Auto-stage before push | `"1"` |
| `GIT_CHECKPOINT_THRESHOLD` | Changes before checkpoint | `"10"` |
| `DISABLE_TELEMETRY` | Disable telemetry | `"1"` |
| `EDITOR` | Default text editor | `"nano"` |

---

## Security Best Practices

### 1. Always Protect Sensitive Files

```json
{
  "permissions": {
    "deny": [
      "Read(.env*)",
      "Read(**/.env)",
      "Read(**/credentials*)",
      "Read(**/*secret*)",
      "Read(**/*password*)",
      "Read(**/*.key)",
      "Read(**/*.pem)",
      "Write(.env*)",
      "Write(**/credentials*)"
    ]
  }
}
```

### 2. Use PreToolUse Hooks for Validation

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write\\(.*\\.env.*\\)|Edit\\(.*\\.env.*\\)",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Blocked: Cannot edit .env files' && exit 2",
            "on_error": "block"
          }
        ]
      }
    ]
  }
}
```

### 3. Require Approval for Critical Operations

```json
{
  "permissions": {
    "ask": [
      "Bash(git push --force:*)",
      "Bash(docker run:*)",
      "Bash(kubectl delete:*)",
      "Write(**/package.json)",
      "Edit(**/go.mod)"
    ]
  }
}
```

---

## Multi-Environment Configuration

### Development Environment

```json
{
  "permissions": {
    "allow": [
      "SlashCommand",
      "Bash(npm run dev:*)",
      "Bash(python -m pytest:*)",
      "Write(src/**)",
      "Edit(src/**)"
    ]
  },
  "env": {
    "NODE_ENV": "development",
    "GIT_AUTO_STAGE_ALL": "1"
  }
}
```

### Production Environment (More Restrictive)

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "SlashCommand"
    ],
    "deny": [
      "Write(src/**)",
      "Edit(src/**)",
      "Bash(npm install:*)"
    ],
    "ask": [
      "Bash(git push:*)",
      "Bash(npm run build:*)"
    ]
  },
  "env": {
    "NODE_ENV": "production",
    "GIT_AUTO_STAGE_ALL": "0"
  }
}
```

---

## Troubleshooting

### Issue: SlashCommand Not Working

**Symptom**: Slash commands require approval

**Solution**: Verify `SlashCommand` is in the allow list

```bash
# Check current settings
cat .claude/settings.json | grep -A 20 '"allow"'

# Should see:
# "allow": [
#   "Read",
#   "Glob",
#   "Grep",
#   "WebSearch",
#   "SlashCommand",  ← This line must be present
#   ...
# ]
```

### Issue: Permission Denied Errors

**Symptom**: Tool calls are blocked unexpectedly

**Solution**: Check deny rules and add explicit allows

```bash
# Identify the blocked operation
# Look for the tool and argument pattern in deny list

# Add specific exception to allow list
# Example: Allow specific npm script
"Bash(npm run test:*)"
```

### Issue: Hooks Not Executing

**Symptom**: PostToolUse hooks don't trigger

**Solution**: Verify hook syntax and file permissions

```bash
# Check hook script exists and is executable
ls -l ~/.claude/hooks/smart-checkpoint.sh
chmod +x ~/.claude/hooks/smart-checkpoint.sh

# Verify matcher pattern
# Use double backslashes for regex: "Write\\(.*\\.py\\)"
```

---

## Template Validation

### Validate JSON Syntax

```bash
# Using jq
jq empty .claude/settings.json
echo $?  # Should output 0 if valid

# Using python
python -m json.tool .claude/settings.json > /dev/null
echo $?  # Should output 0 if valid
```

### Test Permissions

```bash
# In Claude Code, try each operation:
/status                    # Should work (SlashCommand allowed)
cat .env                   # Should be blocked (Read(.env*) denied)
git push                   # Should ask for approval (in ask list)
```

---

## Advanced: Generating Custom Templates

### Create Project-Type Templates

```bash
# Python template
cp ~/.claude/templates/settings.json.template ~/.claude/templates/python-project.json

# Edit to add Python-specific rules
# Add pytest, mypy, black commands
# Add src/, tests/ write permissions

# Node.js template
cp ~/.claude/templates/settings.json.template ~/.claude/templates/nodejs-project.json

# Edit to add Node.js-specific rules
# Add npm run scripts
# Add src/, tests/, dist/ rules
```

### Template Generator Script

```bash
#!/bin/bash
# ~/.claude/bin/generate-project-settings.sh

PROJECT_TYPE=$1
PROJECT_DIR=$2

case "$PROJECT_TYPE" in
  python)
    TEMPLATE="~/.claude/templates/python-project.json"
    ;;
  nodejs)
    TEMPLATE="~/.claude/templates/nodejs-project.json"
    ;;
  go)
    TEMPLATE="~/.claude/templates/go-project.json"
    ;;
  *)
    TEMPLATE="~/.claude/templates/settings.json.template"
    ;;
esac

mkdir -p "$PROJECT_DIR/.claude"
cp "$TEMPLATE" "$PROJECT_DIR/.claude/settings.json"
echo "✅ Created settings.json for $PROJECT_TYPE project"
```

Usage:
```bash
bash ~/.claude/bin/generate-project-settings.sh python /path/to/new-project
```

---

## Related Documentation

- **Slash Commands**: `~/.claude/docs/SLASHCOMMAND_QUICK_REFERENCE.md`
- **Hook System**: `~/.claude/hooks/README.md` (if exists)
- **Permission System**: https://docs.claude.com/en/docs/claude-code/settings
- **Global Settings**: `~/.claude/settings.json`

---

## Template Version

**Version**: 1.0
**Last Updated**: 2025-10-30
**Compatible With**: Claude Code v0.93+

---

## Feedback & Improvements

If you find issues or have suggestions for the template:

1. Test changes in a separate project first
2. Document the use case and rationale
3. Update this guide with examples
4. Share improvements via git commit

**Template Location**: `~/.claude/templates/settings.json.template`
