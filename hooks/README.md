# Claude Code Auto-Commit Setup
# Claude Code 自动提交配置

> **自动提交所有 Claude Code 的修改并推送到 GitHub**

---

## 📦 已安装的文件

```
~/.claude/
├── settings.json                      # 全局配置（已更新）
└── hooks/
    ├── auto-commit.sh                 # 自动提交脚本
    ├── ensure-git-repo.sh             # 自动初始化仓库脚本
    ├── project-settings-template.json # 项目级配置模板
    └── README.md                      # 本文档
```

---

## ✅ 快速开始

### 1. 设置脚本执行权限

```bash
chmod +x ~/.claude/hooks/auto-commit.sh
chmod +x ~/.claude/hooks/ensure-git-repo.sh
```

### 2. 配置 GitHub CLI（可选，用于自动创建仓库）

```bash
# 安装 GitHub CLI
# macOS:
brew install gh

# Linux (Debian/Ubuntu):
sudo apt install gh

# 或下载: https://cli.github.com/

# 登录 GitHub
gh auth login
```

### 3. 启用自动创建仓库（可选）

在你的 `~/.bashrc` 或 `~/.zshrc` 添加：

```bash
# 自动创建 GitHub 仓库
export CLAUDE_AUTO_CREATE_REPO=true

# 或者：不自动创建（默认会询问）
export CLAUDE_AUTO_CREATE_REPO=false
```

然后重新加载配置：

```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

---

## 🚀 工作流程

### 自动触发的操作

| 事件 | 触发时机 | 功能 |
|------|---------|------|
| **SessionStart** | Claude Code 会话开始 | 检查并初始化 Git 仓库（如果需要） |
| **Stop** | Claude 完成响应 | 自动提交所有更改并推送 |

### 具体行为

#### 1️⃣ 会话开始时（SessionStart Hook）

运行 `ensure-git-repo.sh`：
- ✅ 检查当前目录是否为 Git 仓库
- ✅ 如果不是，则初始化新仓库
- ✅ 创建 `.gitignore` 文件
- ✅ 进行初始提交
- ✅ 可选：在 GitHub 创建远程仓库并推送

#### 2️⃣ Claude 停止时（Stop Hook）

运行 `auto-commit.sh`：
- ✅ 检查是否有文件更改
- ✅ 添加所有更改到暂存区 (`git add -A`)
- ✅ 创建提交（包含时间戳和文件列表）
- ✅ 自动推送到远程仓库（如果已配置）

---

## 🔧 自定义配置

### 禁用自动 Push

编辑 `~/.claude/hooks/auto-commit.sh`，找到这一行：

```bash
# 自动 Push（如果不想自动 push，注释掉下面的代码）
# ========================================
```

将下面的 Push 代码块注释掉：

```bash
# if git remote get-url origin > /dev/null 2>&1; then
#   echo -e "${YELLOW}📤 Pushing to remote...${NC}"
#   ...
# fi
```

### 自定义提交消息格式

编辑 `auto-commit.sh` 中的 `COMMIT_MSG` 变量：

```bash
COMMIT_MSG="Your custom message format

🤖 Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

### 项目级配置

在项目目录创建 `.claude/settings.json`：

```bash
mkdir -p .claude
cp ~/.claude/hooks/project-settings-template.json .claude/settings.json
```

编辑 `.claude/settings.json` 添加项目特定的 hooks。

---

## 📋 常见问题

### Q: 提交太频繁了，怎么办？

**A:** 这是 Stop Hook 的特点。如果你觉得太吵，可以：
1. 禁用自动提交，改用手动 `/quick-commit`
2. 使用 GitButler 的虚拟分支功能

### Q: Push 失败怎么办？

**A:** 常见原因：
- 远程仓库不存在：运行 `gh repo create` 手动创建
- 权限问题：检查 SSH 密钥或 `gh auth login`
- 分支未跟踪：运行 `git push -u origin main`

### Q: 能否只提交特定文件？

**A:** 修改 `auto-commit.sh` 中的 `git add -A` 为：

```bash
git add src/  # 只添加 src 目录
```

### Q: 如何查看所有提交？

**A:** 运行：

```bash
git log --oneline --graph --all
```

### Q: 能否在提交前运行测试？

**A:** 在 `auto-commit.sh` 中 `git commit` 之前添加：

```bash
# 运行测试
if command -v npm &> /dev/null; then
  npm test || exit 1
fi
```

---

## 🔒 安全注意事项

### ⚠️ 防止泄露敏感文件

已配置 PreToolUse Hook 防止编辑：
- `.env` 文件
- `credentials.json`
- `.git/` 目录

### ⚠️ 审查提交内容

虽然是自动提交，但仍需定期审查：

```bash
# 查看最近的提交
git log -5 --stat

# 查看特定提交的详细内容
git show <commit-hash>

# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1
```

---

## 🎯 最佳实践

### ✅ DO（推荐）

- ✅ 定期整理提交历史（`git rebase -i`）
- ✅ 使用有意义的分支名
- ✅ 在项目 `.gitignore` 中排除敏感文件
- ✅ 定期运行 `git log` 检查提交
- ✅ 使用 `.claude/settings.local.json` 存储本地配置

### ❌ DON'T（避免）

- ❌ 不要提交包含密码/API keys 的文件
- ❌ 不要在公共仓库自动推送敏感代码
- ❌ 不要忽略 Git 冲突（及时处理）
- ❌ 不要在未测试的情况下自动推送到生产分支

---

## 🛠️ 手动命令参考

### 手动初始化仓库

```bash
bash ~/.claude/hooks/ensure-git-repo.sh
```

### 手动提交

```bash
bash ~/.claude/hooks/auto-commit.sh
```

### 手动创建 GitHub 仓库

```bash
gh repo create my-project --private --source=. --remote=origin --push
```

### 禁用 Hooks（临时）

```bash
# 重命名 settings.json（备份）
mv ~/.claude/settings.json ~/.claude/settings.json.bak

# 恢复
mv ~/.claude/settings.json.bak ~/.claude/settings.json
```

---

## 📚 相关资源

- [Claude Code Hooks 官方文档](https://docs.claude.com/en/docs/claude-code/hooks-guide)
- [GitHub CLI 文档](https://cli.github.com/manual/)
- [Git 最佳实践](https://www.git-tower.com/learn/git/ebook)
- [GitButler](https://gitbutler.com) - 高级 Git 分支管理工具

---

## 🎉 完成！

你的 Claude Code 现在会：
1. ✅ 自动检查并初始化 Git 仓库
2. ✅ 每次响应后自动提交更改
3. ✅ 自动推送到 GitHub（如果配置了远程仓库）

开始编码吧！🚀

---

**生成时间**: 2025-10-25
**版本**: 1.0.0
**作者**: Generated with Claude Code via Happy
