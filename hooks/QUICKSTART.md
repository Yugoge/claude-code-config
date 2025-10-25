# 🚀 快速开始指南

## ✅ 安装已完成！

所有配置文件和脚本已经安装到 `~/.claude/hooks/`

---

## 📋 必须执行的步骤

### 1️⃣ 重启 Claude Code

配置已更新，需要重启 Claude Code 才能生效：

```bash
# 退出当前会话并重新启动 Claude Code
exit
```

### 2️⃣ 安装 GitHub CLI（可选，但强烈推荐）

**macOS:**
```bash
brew install gh
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install gh
```

**其他系统:**
访问 https://cli.github.com/

### 3️⃣ 登录 GitHub

```bash
gh auth login
```

按照提示选择：
- GitHub.com
- HTTPS
- Login with a web browser

### 4️⃣ 配置自动创建仓库（可选）

编辑你的 shell 配置文件：

```bash
# 对于 Bash 用户
nano ~/.bashrc

# 对于 Zsh 用户
nano ~/.zshrc
```

添加以下内容：

```bash
# Claude Code 自动创建 GitHub 仓库
export CLAUDE_AUTO_CREATE_REPO=true
```

保存后重新加载：

```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

---

## 🎯 测试配置

### 测试 1: 检查脚本权限

```bash
ls -lh ~/.claude/hooks/*.sh
```

应该看到 `-rwxr-xr-x`（x 表示可执行）

### 测试 2: 手动运行脚本

```bash
# 测试仓库初始化脚本
cd /tmp/test-project
bash ~/.claude/hooks/ensure-git-repo.sh

# 测试自动提交脚本
echo "test" > test.txt
bash ~/.claude/hooks/auto-commit.sh
```

### 测试 3: 验证 GitHub CLI

```bash
gh auth status
```

应该显示已登录。

---

## 🔄 工作流程示例

### 场景 1: 新项目

```bash
# 1. 创建新项目目录
mkdir my-new-project
cd my-new-project

# 2. 启动 Claude Code
claude-code  # 或你的启动命令

# 3. Claude 会自动：
#    ✅ 初始化 Git 仓库
#    ✅ 创建 .gitignore
#    ✅ 创建 GitHub 仓库（如果配置了 AUTO_CREATE）
#    ✅ 每次响应后自动提交 + 推送
```

### 场景 2: 现有项目

```bash
# 1. 进入现有项目
cd existing-project

# 2. 启动 Claude Code
claude-code

# 3. Claude 会自动：
#    ✅ 检测到已有 Git 仓库
#    ✅ 每次响应后自动提交 + 推送
```

---

## ⚙️ 自定义选项

### 选项 1: 禁用自动 Push

如果你只想自动提交，不想自动推送：

编辑 `~/.claude/hooks/auto-commit.sh`:

```bash
nano ~/.claude/hooks/auto-commit.sh
```

找到这几行并注释掉（添加 # 号）：

```bash
# if git remote get-url origin > /dev/null 2>&1; then
#   echo -e "${YELLOW}📤 Pushing to remote...${NC}"
#   ...
# fi
```

### 选项 2: 更改提交消息格式

编辑 `~/.claude/hooks/auto-commit.sh`:

```bash
nano ~/.claude/hooks/auto-commit.sh
```

修改 `COMMIT_MSG` 变量。

### 选项 3: 项目级配置

为特定项目创建自定义配置：

```bash
cd your-project
mkdir -p .claude
cp ~/.claude/hooks/project-settings-template.json .claude/settings.json
nano .claude/settings.json
```

---

## 🔍 验证配置

运行以下命令检查配置：

```bash
# 查看全局配置
cat ~/.claude/settings.json | grep -A 10 '"Stop"'

# 应该看到:
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

## 📚 下一步

- 📖 阅读完整文档: `~/.claude/hooks/README.md`
- 🛠️ 查看脚本源码: `~/.claude/hooks/auto-commit.sh`
- 🌐 访问 Claude Code 文档: https://docs.claude.com/

---

## ❓ 常见问题

**Q: 我看不到自动提交？**

A: 检查：
1. 是否重启了 Claude Code
2. 运行 `ls -lh ~/.claude/hooks/*.sh` 确认脚本可执行
3. 查看 Claude Code 输出是否有错误信息

**Q: Push 失败？**

A: 检查：
1. `gh auth status` - 确认已登录
2. `git remote -v` - 确认远程仓库存在
3. `git push` - 手动测试推送

**Q: 如何临时禁用？**

A: 重命名配置文件：

```bash
mv ~/.claude/settings.json ~/.claude/settings.json.disabled
# 恢复:
mv ~/.claude/settings.json.disabled ~/.claude/settings.json
```

---

## 🎉 完成！

你现在可以开始使用 Claude Code，它会自动：
1. ✅ 检查/初始化 Git 仓库
2. ✅ 每次响应后提交更改
3. ✅ 自动推送到 GitHub

**享受自动化的 Git 工作流！** 🚀
