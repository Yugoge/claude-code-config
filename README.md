# 🚀 Claude Code Global Configuration

> Professional Claude Code setup with hooks, commands, and sub-agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude-Code-blue.svg)](https://claude.ai/code)

**Last structural update**: 2026-01-08 (ref: commit 590881d5)

---

## 📋 Overview

This is a **production-ready Claude Code global configuration** that includes:
- ✅ Global CLAUDE.md with best practices
- ✅ Comprehensive settings.json with security controls
- ✅ 21 automation hooks (session, safety, quality, pre/post tool use)
- ✅ 32 slash commands (artifacts, file analysis, workflows, research)
- ✅ 14 specialized sub-agents (dev, QA, cleaner, inspectors, orchestrator)
- ✅ Comprehensive project organization and cleanup workflows

---

## 🎯 Features

### 🪝 Hooks (21 total)
- **SessionStart**: Display environment info and available tools
- **PreToolUse Safety**: Warn before dangerous operations
- **PostToolUse**: Code quality hints after file modifications
- Plus 18 specialized hooks for validation, inspection, and workflow automation

### ⚡ Slash Commands (32 total)
**Artifacts & Prototyping**:
- `/artifact-react` - Create React applications with 20+ libraries
- `/artifact-excel-analyzer` - Excel analysis with formula extraction
- `/artifact-mermaid` - Interactive Mermaid diagrams
- `/quick-prototype` - Rapid prototyping tool

**File Operations**:
- `/file-analyze` - Universal file analyzer (PDF, Excel, Word, images)
- `/docx`, `/xlsx`, `/pdf`, `/pptx` - Specialized file manipulation

**Development Workflows**:
- `/dev` - Orchestrated development workflow with multi-agent coordination
- `/test`, `/test-gen` - Test generation and validation
- `/code-review`, `/refactor`, `/optimize` - Code quality workflows
- `/debug-help`, `/security-check` - Debugging and security analysis

**Project Management**:
- `/clean` - Aggressive project cleanup and organization
- `/status` - Show current configuration and capabilities
- `/quick-commit` - Auto-generate commit messages

**Research & Search**:
- `/deep-search`, `/research-deep` - Multi-source research (15-20 iterations)
- `/search-tree`, `/reflect-search` - Advanced search strategies
- `/site-navigate` - Intelligent site exploration

**Thinking & Analysis**:
- `/think`, `/ultrathink` - Extended reasoning (up to 20k+ tokens)
- `/explain-code`, `/doc-gen` - Documentation generation

### 🤖 Sub-Agents (14 total)
**Core Workflow Agents**:
- **orchestrator** - Coordinates multi-agent workflows
- **dev** - Implementation specialist
- **qa** - Quality assurance and validation
- **cleaner** - Executes cleanup actions

**Inspector Agents**:
- **cleanliness-inspector** - File organization issues
- **style-inspector** - Development standards compliance
- **rule-inspector** - Git-based rule discovery and README generation

**Specialized Agents**:
- **artifact-generator** - React apps and visualizations
- **file-processor** - Excel, PDF, image processing
- **code-quality-auditor** - Security and performance analysis
- Plus 4 additional specialized agents

---

## 📦 Installation

### Option 1: Clone to ~/.claude (Recommended)

```bash
# Backup existing configuration
mv ~/.claude ~/.claude.backup

# Clone repository
git clone https://github.com/Yugoge/claude-code-config.git ~/.claude

# Set executable permissions
chmod +x ~/.claude/hooks/*.sh
chmod +x ~/.claude/scripts/*.sh
```

### Option 2: Manual Installation

```bash
# Download and extract
cd ~
git clone https://github.com/Yugoge/claude-code-config.git
cp -r claude-code-config/.claude ~/

# Set permissions
chmod +x ~/.claude/hooks/*.sh
chmod +x ~/.claude/scripts/*.sh
```

---

## 🚀 Quick Start

### 1. Basic Usage

```bash
# In Claude Code, use any slash command
/artifact-react my-dashboard recharts

# Analyze files
/file-analyze data.xlsx "extract formulas"

# Quick prototype
/quick-prototype "sales visualization dashboard"

# Development workflows
/dev "implement feature X"
/clean  # Clean and organize project structure
```

### 2. Customize

Edit configuration files:
- `~/.claude/CLAUDE.md` - Global instructions
- `~/.claude/settings.json` - Permissions and hooks
- `~/.claude/commands/` - Add your own commands
- `~/.claude/agents/` - Add your own agents

---

## 📁 Structure

### Core Directories

- **agents/** (14 agents) - Specialized subagent system prompts
- **commands/** (32 commands) - Slash command definitions
- **hooks/** (21 hooks) - Automation hooks (session, safety, quality)
- **scripts/** (18 scripts) - Helper scripts for workflows
- **docs/** - Documentation organized by category
  - docs/guides/ - User guides and tutorials
  - docs/reference/ - Technical documentation
  - docs/planning/ - Planning docs and design proposals
  - docs/reports/ - Completion reports and summaries
  - docs/archive/ - Historical documentation (organized by date)
  - docs/examples/ - Example files and templates
  - docs/templates/ - Template files
  - docs/dev/ - Development workflow JSONs
  - docs/clean/ - Clean workflow JSONs
  - docs/test/ - Test workflow JSONs

### Other Directories

- **projects/** - Project-specific configurations
- **logs/** - Log files from workflow executions
- **todos/** - Todo tracking files
- **plugins/** - Plugin configurations
- **venv/** - Python virtual environment for scripts

---

## 🎓 Key Capabilities

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

## 🔒 Security

Built-in security controls:
- ❌ Block reading `.env`, credentials, secrets
- ❌ Block dangerous system commands
- ⚠️  Confirm before destructive operations
- 🔒 Fine-grained permission control

---

## 📚 Documentation

Detailed documentation available:
- **Configuration Summary**: `~/.claude/CONFIGURATION_SUMMARY.md`
- **Integration Guide**: `~/.claude/INTEGRATION_GUIDE.md`
- **Official Docs**: https://docs.claude.com/en/docs/claude-code

---

## 🤝 Integration

### Multi-Agent Orchestration
Sophisticated workflow coordination:
- `/dev` workflow: Orchestrator → Dev → QA with full context passing
- `/clean` workflow: Orchestrator → Inspectors → Cleaner with approval gates
- `/test` workflow: Orchestrated test generation and validation
- JSON-based agent communication in docs/{workflow}/ directories

---

## 🛠️ Customization

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

## 🎯 Best Practices

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

## 🔧 Troubleshooting

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

## 📊 Statistics

```
Total Configuration Files: 100+
├── Hooks: 21
├── Commands: 32
├── Agents: 14
├── Scripts: 18
├── CLAUDE.md: 147 lines
└── settings.json: Comprehensive permissions with MCP integrations
```

---

## 🙏 Credits

**Based on:**
- Claude.ai Web artifact capabilities
- [fcakyon/claude-codex-settings](https://github.com/fcakyon/claude-codex-settings) - Real-world configuration reference
- Claude Code official documentation
- Community best practices

---

## 📄 License

MIT License

---

## 👨‍💻 Author

Created by Claude Code (Anthropic) for **Yugoge**

---

---

## 📝 Recent Structural Changes

Last 30 days:

- 2026-01-08 14:08:02: docs: add README files for newly created archive folders
- 2026-01-08 13:22:12: docs: add comprehensive cleanup completion report
- 2026-01-08 13:20:30: feat: comprehensive project cleanup - resolve all organization issues
- 2026-01-08 13:18:54: checkpoint: Before aggressive cleanup on 2026-01-08
- 2026-01-08 12:44:20: fix: enhance /clean workflow - detect non-functional folders and auto-update READMEs
- 2026-01-07 11:47:24: fix: achieve 100% validator pass rate by fixing EC002 documentation
- 2026-01-07 11:44:24: fix: translate remaining hooks files to complete EC006 compliance

---

## 📈 Git Analysis

<!-- AUTO-GENERATED by rule-inspector - DO NOT EDIT -->
Project initialized: 2025-12-27 22:51:35
Last structural update: 2026-01-08 14:08:02
Total commits: 36
<!-- END AUTO-GENERATED -->

---

*Root README updated by rule-inspector on 2026-01-08 to reflect current project structure (ref: commit 590881d5 fix)*
