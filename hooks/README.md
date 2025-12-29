# Claude Code Auto-Commit Setup

> **Automatically commit all Claude Code changes and push to GitHub**

---

## 📦 Installed Files

```
~/.claude/
├── settings.json                      # Global configuration (updated)
└── hooks/
    ├── auto-commit.sh                 # Auto-commit script
    ├── ensure-git-repo.sh             # Auto-initialize repository script
    ├── project-settings-template.json # Project-level configuration template
    └── README.md                      # This document
```

---

## ✅ Quick Start

### 1. Set Script Execute Permissions

```bash
chmod +x ~/.claude/hooks/auto-commit.sh
chmod +x ~/.claude/hooks/ensure-git-repo.sh
```

### 2. Configure GitHub CLI (Optional, for Auto-Creating Repositories)

```bash
# Install GitHub CLI
# macOS:
brew install gh

# Linux (Debian/Ubuntu):
sudo apt install gh

# Or download: https://cli.github.com/

# Login to GitHub
gh auth login
```

### 3. Enable Auto-Create Repository (Optional)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Automatically create GitHub repository
export CLAUDE_AUTO_CREATE_REPO=true

# Or: Don't auto-create (will prompt by default)
export CLAUDE_AUTO_CREATE_REPO=false
```

Then reload configuration:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

---

## 🚀 Workflow

### Automatically Triggered Actions

| Event | Trigger | Function |
|------|---------|------|
| **SessionStart** | Claude Code session starts | Check and initialize Git repository (if needed) |
| **Stop** | Claude completes response | Automatically commit all changes and push |

### Specific Behaviors

#### 1️⃣ On Session Start (SessionStart Hook)

Runs `ensure-git-repo.sh`:
- ✅ Check if current directory is a Git repository
- ✅ If not, initialize new repository
- ✅ Create `.gitignore` file
- ✅ Perform initial commit
- ✅ Optional: Create remote repository on GitHub and push

#### 2️⃣ On Claude Stop (Stop Hook)

Runs `auto-commit.sh`:
- ✅ Check if files have changed
- ✅ Add all changes to staging area (`git add -A`)
- ✅ Create commit (includes timestamp and file list)
- ✅ Automatically push to remote repository (if configured)

---

## 🔧 Custom Configuration

### Disable Auto Push

Edit `~/.claude/hooks/auto-commit.sh`, find this line:

```bash
# Auto Push (comment out the code below if you don't want auto push)
# ========================================
```

Comment out the Push code block below:

```bash
# if git remote get-url origin > /dev/null 2>&1; then
#   echo -e "${YELLOW}📤 Pushing to remote...${NC}"
#   ...
# fi
```

### Customize Commit Message Format

Edit the `COMMIT_MSG` variable in `auto-commit.sh`:

```bash
COMMIT_MSG="Your custom message format

🤖 Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

### Project-Level Configuration

Create `.claude/settings.json` in project directory:

```bash
mkdir -p .claude
cp ~/.claude/hooks/project-settings-template.json .claude/settings.json
```

Edit `.claude/settings.json` to add project-specific hooks.

---

## 📋 FAQ

### Q: Commits are too frequent, what should I do?

**A:** This is a characteristic of the Stop Hook. If you find it too noisy, you can:
1. Disable auto-commit and use manual `/quick-commit` instead
2. Use GitButler's virtual branch feature

### Q: What if Push fails?

**A:** Common causes:
- Remote repository doesn't exist: Run `gh repo create` to manually create
- Permission issue: Check SSH keys or `gh auth login`
- Branch not tracked: Run `git push -u origin main`

### Q: Can I commit only specific files?

**A:** Modify `git add -A` in `auto-commit.sh` to:

```bash
git add src/  # Only add src directory
```

### Q: How to view all commits?

**A:** Run:

```bash
git log --oneline --graph --all
```

### Q: Can I run tests before committing?

**A:** Add this before `git commit` in `auto-commit.sh`:

```bash
# Run tests
if command -v npm &> /dev/null; then
  npm test || exit 1
fi
```

---

## 🔒 Security Notes

### ⚠️ Prevent Leaking Sensitive Files

PreToolUse Hook is configured to prevent editing:
- `.env` files
- `credentials.json`
- `.git/` directory

### ⚠️ Review Commit Content

Although commits are automatic, regular reviews are still needed:

```bash
# View recent commits
git log -5 --stat

# View details of specific commit
git show <commit-hash>

# Undo last commit (keep changes)
git reset --soft HEAD~1
```

---

## 🎯 Best Practices

### ✅ DO (Recommended)

- ✅ Regularly clean up commit history (`git rebase -i`)
- ✅ Use meaningful branch names
- ✅ Exclude sensitive files in project `.gitignore`
- ✅ Regularly run `git log` to check commits
- ✅ Use `.claude/settings.local.json` to store local configuration

### ❌ DON'T (Avoid)

- ❌ Don't commit files containing passwords/API keys
- ❌ Don't auto-push sensitive code to public repositories
- ❌ Don't ignore Git conflicts (handle them promptly)
- ❌ Don't auto-push to production branches without testing

---

## 🛠️ Manual Command Reference

### Manually Initialize Repository

```bash
bash ~/.claude/hooks/ensure-git-repo.sh
```

### Manual Commit

```bash
bash ~/.claude/hooks/auto-commit.sh
```

### Manually Create GitHub Repository

```bash
gh repo create my-project --private --source=. --remote=origin --push
```

### Disable Hooks (Temporary)

```bash
# Rename settings.json (backup)
mv ~/.claude/settings.json ~/.claude/settings.json.bak

# Restore
mv ~/.claude/settings.json.bak ~/.claude/settings.json
```

---

## 📚 Related Resources

- [Claude Code Hooks Official Documentation](https://docs.claude.com/en/docs/claude-code/hooks-guide)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [Git Best Practices](https://www.git-tower.com/learn/git/ebook)
- [GitButler](https://gitbutler.com) - Advanced Git branch management tool

---

## 🎉 Complete!

Your Claude Code will now:
1. ✅ Automatically check and initialize Git repository
2. ✅ Automatically commit changes after each response
3. ✅ Automatically push to GitHub (if remote repository is configured)

Start coding! 🚀

---

**Generated**: 2025-10-25
**Version**: 1.0.0
**Author**: Generated with Claude Code via Happy
