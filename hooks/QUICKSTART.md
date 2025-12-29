# 🚀 Quick Start Guide

## ✅ Installation Complete!

All configuration files and scripts have been installed to `~/.claude/hooks/`

---

## 📋 Required Steps

### 1️⃣ Restart Claude Code

Configuration has been updated, restart Claude Code to take effect:

```bash
# Exit current session and restart Claude Code
exit
```

### 2️⃣ Install GitHub CLI (Optional, but Highly Recommended)

**macOS:**
```bash
brew install gh
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install gh
```

**Other Systems:**
Visit https://cli.github.com/

### 3️⃣ Login to GitHub

```bash
gh auth login
```

Follow the prompts to select:
- GitHub.com
- HTTPS
- Login with a web browser

### 4️⃣ Configure Auto-Create Repository (Optional)

Edit your shell configuration file:

```bash
# For Bash users
nano ~/.bashrc

# For Zsh users
nano ~/.zshrc
```

Add the following:

```bash
# Claude Code auto-create GitHub repository
export CLAUDE_AUTO_CREATE_REPO=true
```

Save and reload:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

---

## 🎯 Test Configuration

### Test 1: Check Script Permissions

```bash
ls -lh ~/.claude/hooks/*.sh
```

Should see `-rwxr-xr-x` (x indicates executable)

### Test 2: Manually Run Scripts

```bash
# Test repository initialization script
cd /tmp/test-project
bash ~/.claude/hooks/ensure-git-repo.sh

# Test auto-commit script
echo "test" > test.txt
bash ~/.claude/hooks/auto-commit.sh
```

### Test 3: Verify GitHub CLI

```bash
gh auth status
```

Should show logged in.

---

## 🔄 Workflow Examples

### Scenario 1: New Project

```bash
# 1. Create new project directory
mkdir my-new-project
cd my-new-project

# 2. Start Claude Code
claude-code  # or your launch command

# 3. Claude will automatically:
#    ✅ Initialize Git repository
#    ✅ Create .gitignore
#    ✅ Create GitHub repository (if AUTO_CREATE is configured)
#    ✅ Auto-commit + push after each response
```

### Scenario 2: Existing Project

```bash
# 1. Enter existing project
cd existing-project

# 2. Start Claude Code
claude-code

# 3. Claude will automatically:
#    ✅ Detect existing Git repository
#    ✅ Auto-commit + push after each response
```

---

## ⚙️ Custom Options

### Option 1: Disable Auto Push

If you only want auto-commit without auto-push:

Edit `~/.claude/hooks/auto-commit.sh`:

```bash
nano ~/.claude/hooks/auto-commit.sh
```

Find these lines and comment them out (add # prefix):

```bash
# if git remote get-url origin > /dev/null 2>&1; then
#   echo -e "${YELLOW}📤 Pushing to remote...${NC}"
#   ...
# fi
```

### Option 2: Change Commit Message Format

Edit `~/.claude/hooks/auto-commit.sh`:

```bash
nano ~/.claude/hooks/auto-commit.sh
```

Modify the `COMMIT_MSG` variable.

### Option 3: Project-Level Configuration

Create custom configuration for specific project:

```bash
cd your-project
mkdir -p .claude
cp ~/.claude/hooks/project-settings-template.json .claude/settings.json
nano .claude/settings.json
```

---

## 🔍 Verify Configuration

Run the following command to check configuration:

```bash
# View global configuration
cat ~/.claude/settings.json | grep -A 10 '"Stop"'

# Should see:
# "Stop": [
#   {
#     "hooks": [
#       {
#         "type": "command",
#         "command": "bash ~/.claude/hooks/auto-commit.sh"
#       }
#     ]
#   }
# ],
```

---

## 📚 Next Steps

- 📖 Read full documentation: `~/.claude/hooks/README.md`
- 🛠️ View script source: `~/.claude/hooks/auto-commit.sh`
- 🌐 Visit Claude Code docs: https://docs.claude.com/

---

## ❓ FAQ

**Q: I don't see auto-commits?**

A: Check:
1. Have you restarted Claude Code
2. Run `ls -lh ~/.claude/hooks/*.sh` to confirm scripts are executable
3. Check Claude Code output for error messages

**Q: Push fails?**

A: Check:
1. `gh auth status` - Confirm logged in
2. `git remote -v` - Confirm remote repository exists
3. `git push` - Manually test push

**Q: How to temporarily disable?**

A: Rename configuration file:

```bash
mv ~/.claude/settings.json ~/.claude/settings.json.disabled
# Restore:
mv ~/.claude/settings.json.disabled ~/.claude/settings.json
```

---

## 🎉 Complete!

You can now start using Claude Code, it will automatically:
1. ✅ Check/initialize Git repository
2. ✅ Commit changes after each response
3. ✅ Auto-push to GitHub

**Enjoy the automated Git workflow!** 🚀
