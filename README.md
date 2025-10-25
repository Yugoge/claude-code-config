# 🚀 Claude Code Global Configuration
# Claude Code 全局配置

> Professional Claude Code setup with hooks, commands, and sub-agents
> 专业的 Claude Code 配置，包含 hooks、命令和子代理

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude-Code-blue.svg)](https://claude.ai/code)

---

## 📋 Overview | 概述

This is a **production-ready Claude Code global configuration** that includes:
- ✅ Global CLAUDE.md with best practices
- ✅ Comprehensive settings.json with security controls
- ✅ 3 automation hooks (session, safety, quality)
- ✅ 5 core slash commands (artifacts + file analysis)
- ✅ 3 specialized sub-agents (artifact, file processor, code auditor)
- ✅ Deep integration with excel-analyzer

这是一个**生产级的 Claude Code 全局配置**，包含：
- ✅ 全局 CLAUDE.md 最佳实践
- ✅ 完整的 settings.json 安全控制
- ✅ 3个自动化 hooks（会话、安全、质量）
- ✅ 5个核心 slash 命令（artifacts + 文件分析）
- ✅ 3个专业子代理（artifact、文件处理、代码审计）
- ✅ 与 excel-analyzer 深度集成

---

## 🎯 Features | 特性

### 🪝 Hooks
- **SessionStart**: Display environment info and available tools
- **PreToolUse Safety**: Warn before dangerous operations
- **PostToolUse**: Code quality hints after file modifications

### ⚡ Slash Commands
- `/artifact-react` - Create React applications with 20+ libraries
- `/artifact-excel-analyzer` - Excel analysis with formula extraction
- `/artifact-mermaid` - Interactive Mermaid diagrams
- `/file-analyze` - Universal file analyzer (PDF, Excel, Word, images)
- `/quick-prototype` - Rapid prototyping tool

### 🤖 Sub-Agents
- **artifact-generator** - Expert in creating React apps and visualizations
- **file-processor** - Excel formula extraction, PDF/image analysis
- **code-quality-auditor** - Security and performance analysis

---

## 📦 Installation | 安装

### Option 1: Clone to ~/.claude (Recommended)

```bash
# Backup existing configuration
mv ~/.claude ~/.claude.backup

# Clone repository
git clone https://github.com/Yugoge/claude-code-config.git ~/.claude

# Set executable permissions
chmod +x ~/.claude/hooks/*.sh
chmod +x ~/.claude/bin/*
```

### Option 2: Manual Installation

```bash
# Download and extract
cd ~
git clone https://github.com/Yugoge/claude-code-config.git
cp -r claude-code-config/.claude ~/

# Set permissions
chmod +x ~/.claude/hooks/*.sh
chmod +x ~/.claude/bin/*
```

---

## 🚀 Quick Start | 快速开始

### 1. Basic Usage

```bash
# In Claude Code, use any slash command
/artifact-react my-dashboard recharts

# Analyze files
/file-analyze data.xlsx "extract formulas"

# Quick prototype
/quick-prototype "sales visualization dashboard"
```

### 2. Use Quick Excel

```bash
# Use the wrapper script
quick-excel financial-model.xlsx --formulas
quick-excel budget.xlsx --all
```

### 3. Customize

Edit configuration files:
- `~/.claude/CLAUDE.md` - Global instructions
- `~/.claude/settings.json` - Permissions and hooks
- `~/.claude/commands/` - Add your own commands
- `~/.claude/agents/` - Add your own agents

---

## 📁 Structure | 结构

```
~/.claude/
├── CLAUDE.md                    # Global memory and best practices
├── settings.json                # Global settings with hooks
├── CONFIGURATION_SUMMARY.md     # Complete documentation
├── INTEGRATION_GUIDE.md         # Excel-analyzer integration guide
├── hooks/                       # Automation hooks
│   ├── session_start.sh
│   ├── pre_tool_use_safety.sh
│   └── post_tool_use.sh
├── commands/                    # Slash commands
│   ├── artifact-react.md
│   ├── artifact-excel-analyzer.md
│   ├── artifact-mermaid.md
│   ├── file-analyze.md
│   └── quick-prototype.md
├── agents/                      # Sub-agents
│   ├── artifact-generator.md
│   ├── file-processor.md
│   └── code-quality-auditor.md
└── bin/                         # Utility scripts
    └── quick-excel
```

---

## 🎓 Key Capabilities | 核心能力

### Artifact Creation (Inherited from Claude.ai Web)
Create standalone interactive applications:
- ✅ React apps with Tailwind, Recharts, D3.js, TensorFlow.js
- ✅ Excel analyzers with formula extraction
- ✅ Mermaid diagrams
- ✅ Data visualizations

### File Processing
Handle multiple file formats:
- ✅ Excel: Formula extraction, statistics, visualization
- ✅ PDF: Text extraction, content analysis
- ✅ Images: Content recognition, OCR
- ✅ Word: Document conversion
- ✅ CSV: Data analysis

### Code Quality
Professional code review:
- ✅ Security vulnerability detection
- ✅ Performance optimization suggestions
- ✅ Best practices checking

---

## 🔒 Security | 安全

Built-in security controls:
- ❌ Block reading `.env`, credentials, secrets
- ❌ Block dangerous system commands
- ⚠️  Confirm before destructive operations
- 🔒 Fine-grained permission control

---

## 📚 Documentation | 文档

Detailed documentation available:
- **Configuration Summary**: `~/.claude/CONFIGURATION_SUMMARY.md`
- **Integration Guide**: `~/.claude/INTEGRATION_GUIDE.md`
- **Official Docs**: https://docs.claude.com/en/docs/claude-code

---

## 🤝 Integration | 集成

### Works with excel-analyzer
Seamlessly integrated with the [excel-analyzer](https://github.com/Yugoge/excel-analyzer) project:
- Quick CLI analysis via `/file-analyze`
- Web visualization via `/artifact-excel-analyzer`
- Global `quick-excel` command

---

## 🛠️ Customization | 自定义

### Add Your Own Commands

```bash
# Create a new command
cat > ~/.claude/commands/my-command.md << 'EOF'
---
description: My custom command
---

Your command instructions here...
EOF
```

### Add Your Own Agent

```bash
# Create a new agent
cat > ~/.claude/agents/my-agent.md << 'EOF'
---
name: my-agent
description: When to use this agent
tools: Read, Write, Bash
---

Your agent system prompt here...
EOF
```

### Add Your Own Hook

```bash
# Create a hook script
cat > ~/.claude/hooks/my-hook.sh << 'EOF'
#!/bin/bash
# Your hook logic here
EOF

chmod +x ~/.claude/hooks/my-hook.sh

# Add to settings.json
# Edit ~/.claude/settings.json and add to hooks section
```

---

## 🎯 Best Practices | 最佳实践

### Keep CLAUDE.md Concise
- Focus on essential instructions
- Use "IMPORTANT" for critical rules
- Include common commands
- Under 200 lines recommended

### Use Hooks Wisely
- Keep hooks simple and fast
- Focus on safety and automation
- Avoid complex logic in hooks

### Organize Commands
- Use namespaces for related commands
- Provide clear descriptions
- Include usage examples

---

## 🔧 Troubleshooting | 故障排除

### Hooks Not Running
```bash
chmod +x ~/.claude/hooks/*.sh
```

### Commands Not Showing
Check frontmatter format in command files.

### JSON Syntax Errors
```bash
python3 -m json.tool ~/.claude/settings.json
```

---

## 📊 Statistics | 统计

```
Total Configuration Files: 20+
├── Hooks: 3
├── Commands: 14 (5 core + 9 existing)
├── Agents: 3
├── CLAUDE.md: 147 lines
└── settings.json: 189 lines
```

---

## 🙏 Credits | 致谢

**Based on:**
- Claude.ai Web artifact capabilities
- [fcakyon/claude-codex-settings](https://github.com/fcakyon/claude-codex-settings) - Real-world configuration reference
- Claude Code official documentation
- Community best practices

---

## 📄 License | 许可证

MIT License

---

## 👨‍💻 Author | 作者

Created by Claude Code (Anthropic) for **Yugoge**

---

## 🔗 Related Projects | 相关项目

- [excel-analyzer](https://github.com/Yugoge/excel-analyzer) - Professional Excel analysis tool

---

**🚀 Enjoy powerful Claude Code capabilities! | 享受强大的 Claude Code 能力！**

For questions or suggestions, please open an issue on GitHub.
