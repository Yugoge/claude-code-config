---
description: Deep website exploration with iterative search strategy
argument-hint: <domain> <search-goal>
---

Execute deep search on **$1** to find: **$2**

## Strategy: Multi-Phase Iterative Search

### Phase 1: Parallel Discovery (并行发现)
Execute these searches **in parallel**:
- `site:$1 "$2"`
- `site:$1 "$2" filetype:pdf`
- `site:$1 "$2" official guide documentation manual`
- `"$2" site:$1 OR site:www.$1`

### Phase 2: Entry Point Analysis (入口分析)
WebFetch the main homepage with this prompt:
```
Extract all navigation menu links related to "$2".
For each relevant link, provide:
- Menu category and submenu name
- Complete URL
- Brief description

Also identify:
- Any search functionality or search box
- Document repository or download sections
- Sitemap or directory pages
```

### Phase 3: Breadth Exploration (广度探索 - 并行)
From Phase 2 results, identify the top 3-5 most promising URLs.
WebFetch them **in parallel** with this prompt:
```
Find all downloadable documents, guides, PDFs, or deep links related to "$2".
Extract:
- Document title and type (PDF, DOC, etc.)
- Direct download URL or access link
- Description/summary
- Last updated date if shown
```

### Phase 4: Depth Targeting (深度定位)
Based on Phase 3 findings, WebFetch the most specific/relevant page with:
```
Extract complete information about "$2" from this page:
- Main content and key sections
- Required steps or procedures
- Important requirements or documents needed
- Contact information or support links
- Any referenced sub-pages or related documents
```

### Phase 5: Fallback Recovery (失败恢复)
If WebFetch is blocked at any stage:

**Fallback A**: Search for alternative official sources
- `"$2" official mirror site`
- `"$2" embassy consulate official`
- `"$2" government portal`

**Fallback B**: Use subdomain/related domain search
- Search organization's other domains (e.g., visa.go.kr if hikorea.go.kr blocked)

**Fallback C**: Task agent for creative solutions
- Launch general-purpose agent to explore alternative paths

### Phase 6: Synthesis & Report (综合报告)
Compile all findings into a structured report:

```markdown
## Deep Search Report: $2 on $1

### 🎯 Search Goal
$2

### 📊 Search Summary
- Total searches executed: [N]
- WebFetch attempts: [N successful / N total]
- Documents found: [N]

### 📄 Key Findings
1. **Primary Document/Resource**
   - Title: [...]
   - URL: [...]
   - Type: [...]
   - Status: ✅ Verified / ⚠️ Unverified
   - Summary: [...]

2. **Additional Resources**
   - [List other relevant findings]

### 🔗 All Discovered URLs
- [URL 1] - [Description]
- [URL 2] - [Description]
- ...

### ⚠️ Issues Encountered
- [List any blocked URLs, failed fetches, or limitations]

### 💡 Recommendations
- [Next steps or alternative approaches if needed]

### 📝 Search Path Log
Phase 1: [Results summary]
Phase 2: [Results summary]
...
```

## Critical Execution Rules
1. **Always use parallel tool calls** in Phase 1 and 3
2. **Never skip phases** - each builds on previous findings
3. **Track all visited URLs** to avoid loops
4. **Adapt dynamically** - if a phase fails, adjust strategy
5. **Provide detailed prompts** - simulate Grok's instruction-based approach
6. **Use TodoWrite** to track progress through phases
