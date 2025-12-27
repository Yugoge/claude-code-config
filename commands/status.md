---
description: Show current Claude Code configuration and available capabilities
---

# 📊 Claude Code Status Report

## 🤖 System Information

**Claude Code Version**: 1.0.112
**Model**: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
**Knowledge Cutoff**: January 2025
**Today's Date**: 2025-10-26
**Working Directory**: $(pwd)

---

## 🧠 Extended Thinking Capabilities

**Available Thinking Modes**:
- `/think` - Standard extended thinking (2k tokens)
- `/think hard` - Deep analysis (5k tokens)
- `/think harder` - Very deep exploration (10k tokens)
- `/ultrathink` - Maximum depth reasoning (20k+ tokens)

**Current Session**: Extended thinking not currently active
**Recommendation**: Use `/ultrathink` for complex tasks requiring deep reasoning

---

## 🔧 MCP Servers (Model Context Protocol)

**Active MCP Servers**:
1. **context7** - Up-to-date library documentation
   - Status: ✅ Active
   - Tools: resolve-library-id, get-library-docs

2. **playwright** - Browser automation
   - Status: ✅ Active
   - Command: @modelcontextprotocol/server-playwright
   - Transport: stdio

3. **happy** - Chat management
   - Status: ✅ Active
   - Tools: change_title

---

## 🎯 Specialized Subagents

**Available Subagents**:
- `@deep-search` - Deep web search and site exploration
  - Triggers: official docs, site exploration, 5+ source research
  - Strategies: Multi-phase, reflection-driven, tree search

- `@general-purpose` - Complex multi-step tasks
- `@code-quality-auditor` - Security and code review
- `@artifact-generator` - Interactive apps and visualizations
- `@file-processor` - PDF, Excel, images, Word analysis

---

## ⚡ Slash Commands (Custom)

**Search & Research**:
- `/deep-search <domain> <goal>` - Site-specific deep exploration
- `/research-deep <topic>` - Multi-source research (15-20 searches)
- `/search-tree <question>` - MCTS-inspired exploration
- `/reflect-search <goal>` - Reflection-driven iterative search
- `/site-navigate <url> <task>` - Intelligent site navigation

**Code Development**:
- `/explain-code [file-path]` - Deep code explanation
- `/refactor [file-path]` - Refactoring suggestions
- `/optimize [file-path]` - Performance optimization
- `/test-gen [file-path]` - Generate comprehensive tests
- `/doc-gen [file-path]` - Generate documentation
- `/code-review [file-path]` - Best practices review
- `/security-check [file-path]` - Security vulnerability analysis
- `/debug-help [error-or-file]` - Debug assistance

**Productivity**:
- `/quick-commit [message-prefix]` - Auto-generate git commit
- `/quick-prototype [description]` - Rapid prototyping

**Artifacts & Tools**:
- `/artifact-react [app-name]` - Standalone React app
- `/artifact-mermaid [diagram-type]` - Interactive diagrams
- `/artifact-excel-analyzer` - Excel file analyzer
- `/file-analyze [file-path]` - Analyze PDF/Excel/Word/images

**Utilities**:
- `/playwright-helper` - Playwright MCP usage guide
- `/status` - This status report

---

## 📁 Configuration Files

**Global Config**: `~/.claude/CLAUDE.md` (206 lines, ~1200 tokens)
**Subagents**: `~/.claude/agents/deep-search.md`
**Commands**: `~/.claude/commands/` (21 slash commands)
**Repository**: https://github.com/Yugoge/claude-code-config.git

---

## 🎨 Current Session Settings

**Plan Mode**: Not active (use with `-p` flag)
**Todo Tracking**: Available via TodoWrite tool
**Parallel Execution**: ✅ Enabled (independent tools run in parallel)
**Auto-Commit**: Not configured as hook

---

## 💡 Quick Tips

1. **For complex reasoning**: Use `/ultrathink <task>`
2. **For library code**: Context7 auto-activates (e.g., "show me FastAPI example")
3. **For deep research**: Use `/deep-search` or `@deep-search` agent
4. **For code review**: Use `/code-review <file-path>`
5. **For security audit**: Use `/security-check <directory>`

---

**Status**: All systems operational ✅

Need help? Type `/help` or visit https://docs.claude.com/claude-code
