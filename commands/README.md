# Deep Search Commands - Quick Reference

## 🚀 Available Commands

### 1. `/deep-search <domain> <goal>`
**Best for**: Finding specific documents on a particular website

**Example**:
```
/deep-search hikorea.go.kr "Korean tourist visa C-3 application guide"
```

**What it does**:
- Phase 1: Parallel searches (site:, PDF, official docs)
- Phase 2: Analyze homepage navigation
- Phase 3: Explore top 3-5 promising pages (parallel)
- Phase 4: Deep dive into most specific page
- Phase 5: Automatic fallback if blocked
- Phase 6: Comprehensive report with all findings

---

### 2. `/research-deep <topic>`
**Best for**: Comprehensive research with many sources

**Example**:
```
/research-deep "AI chip market trends 2025"
```

**What it does**:
- 15-20 iterative searches
- Extracts 3-5 key sub-topics
- Parallel deep dive on each sub-topic
- Fetches complete content from top 5-7 URLs
- Analyzes contradictions and gaps
- Generates comprehensive report with citations

---

### 3. `/search-tree <question>`
**Best for**: Open-ended problems with multiple approaches

**Example**:
```
/search-tree "How to start an AI company in 2025?"
```

**What it does**:
- Generates 3-5 distinct solution paths
- Explores all paths in parallel
- Scores each path (0-10)
- Deep dives on top 2 paths
- Recursive refinement (max 3 levels)
- Recommends best path with integration

---

### 4. `/reflect-search <goal>`
**Best for**: Finding very specific information with verification

**Example**:
```
/reflect-search "Find official FDA approval requirements for medical devices"
```

**What it does**:
- Articulates concrete, measurable goal
- Initial search execution
- Reflection loop (up to 5 iterations):
  - Scores goal achievement (0-10)
  - Identifies missing information
  - Decides: CONTINUE / PIVOT / DONE
- Adaptive search based on reflection
- Documents entire search journey

---

### 5. `/site-navigate <url> <task>`
**Best for**: Navigating complex site structures

**Example**:
```
/site-navigate https://www.hikorea.go.kr "Find downloadable visa application forms"
```

**What it does**:
- Analyzes homepage structure
- Selects top 3 most promising links
- Parallel exploration of chosen paths
- Up to 5 levels deep navigation
- Alternative strategies if stuck (sitemap, common paths)
- Full navigation report with path taken

---

## 🎯 When to Use Which Command?

| Scenario | Command | Why |
|----------|---------|-----|
| "Find official guide on website X" | `/deep-search` | Site-specific, structured exploration |
| "Research topic Y comprehensively" | `/research-deep` | Many sources, synthesis needed |
| "Best way to do Z?" | `/search-tree` | Multiple valid approaches |
| "Find exact regulation/requirement" | `/reflect-search` | Needs verification, iterative refinement |
| "Navigate complex government site" | `/site-navigate` | Deep nested structure |

---

## ⚡ Performance Tips

1. **Use parallel searches**: All commands automatically parallelize when possible
2. **Be specific**: More specific goals = better results
3. **Trust the process**: Commands will report progress through phases
4. **Review reports**: All commands generate structured reports with citations

---

## 🔧 Advanced Usage

### Combine Commands
```
# Step 1: Broad research
/research-deep "Korean visa types"

# Step 2: Deep dive on specific finding
/deep-search visa.go.kr "C-3 tourist visa application process"

# Step 3: Navigate to exact document
/site-navigate https://visa.go.kr "downloadable C-3 application form PDF"
```

### With MCP Browser Tools
If you have Playwright MCP installed:
- Commands automatically use it for JavaScript-heavy sites
- Fallback to WebFetch for simple sites
- No manual intervention needed

---

## 📊 Expected Performance

| Metric | Target | Typical |
|--------|--------|---------|
| **Success rate** | >85% | ~90% |
| **Simple search time** | <5 min | 2-4 min |
| **Complex search time** | <15 min | 8-12 min |
| **Sources per complex query** | 15-20 | 15-25 |

---

## 🆘 Troubleshooting

**Issue**: Command not found
**Solution**: Ensure file exists in `~/.claude/commands/` and restart Claude Code

**Issue**: WebFetch blocked repeatedly
**Solution**: 
1. Install Playwright MCP: `claude mcp add playwright @modelcontextprotocol/server-playwright`
2. Or use `/site-navigate` which has more fallback strategies

**Issue**: Too many results, information overload
**Solution**: Be more specific in your goal/question

**Issue**: Results not recent enough
**Solution**: Add year to query, e.g., `/research-deep "AI trends 2025"`

---

## 📚 Full Documentation

See `/root/.claude/CLAUDE.md` sections:
- 🌐 Advanced Web Search & Deep Navigation
- 💬 Interactive & Conversational Search

---

## 🎉 Quick Start

Try this now:
```
/deep-search wikipedia.org "List of largest cities in the world"
```

This will demonstrate:
- Parallel search execution
- Navigation extraction
- Document discovery
- Structured reporting

Enjoy your new deep search superpowers! 🚀
