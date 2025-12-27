---
description: Intelligent site navigation simulating "click-through" exploration
argument-hint: <url> <task>
---

Navigate **$1** to accomplish: **$2**

## Methodology: Simulated Navigation (Grok-style)

Simulate intelligent site navigation without actual browser interaction.

### Phase 1: Homepage Analysis

⚠️ **CRITICAL**: WebFetch is DISABLED (timeout risk). Use Playwright MCP instead.

Navigate to starting URL ($1) using Playwright:
```
1. Use mcp__playwright__navigate to open $1
2. Extract page structure using mcp__playwright__evaluate:
   - Navigation menus: document.querySelectorAll('nav a, .menu a')
   - All links: document.querySelectorAll('a[href]')
   - Main content: document.querySelector('main, article, .content')
3. Analyze structure to find information about "$2":
   - Navigation Structure: All menu items, categories, sections
   - Key Links: URLs that might lead to "$2"
   - Search Functionality: input[type="search"], .search-box
   - Direct Matches: Any content directly related to "$2"
4. For each relevant link, provide:
   - Link text
   - Complete URL
   - Estimated relevance to goal (High/Medium/Low)
   - Why it might contain the target information
5. Organize by estimated relevance
```

### Phase 2: Path Selection
From Phase 1 analysis, select the top 3 most promising links.

Selection criteria:
- Link text explicitly mentions keywords from $2
- URL structure suggests relevant content (e.g., /docs/, /guide/, /download/)
- Description indicates authoritative/official content

### Phase 3: Parallel Exploration
Navigate to the top 3 links **in parallel** using Playwright:
```
For each link:
1. Use mcp__playwright__navigate
2. Search page for information about "$2" using mcp__playwright__evaluate
3. If found:
   - Extract complete information from main content area
   - Find downloadable resources: a[href$=".pdf"], a[href*="download"]
   - Identify deeper links in content
4. If not found:
   - Identify which links on this page might lead to "$2"
   - Extract URLs of up to 3 most relevant next steps
```

### Phase 4: Depth Navigation (if needed)
If Phase 3 found promising deeper links but not final target:
- Select the most promising next-level link
- Repeat navigation (max 5 total levels)
- Track path taken to avoid loops

### Phase 5: Alternative Strategies (if stuck)
If unable to find target after 3 levels:

**Strategy A**: Try site search
```
WebSearch: site:$1 "$2"
```

**Strategy B**: Look for sitemap
```
Navigate to $1/sitemap.xml or $1/sitemap.html using Playwright
```

**Strategy C**: Check common paths
```
Try: /docs/, /help/, /support/, /downloads/, /resources/
```

### Phase 6: Navigation Report
```markdown
## Site Navigation Report

### Target Site
$1

### Goal
$2

### Navigation Path
1. **Homepage**: $1
   - Found: [Summary]
   - Chose: [Link A] (reason: ...)

2. **Level 2**: [URL]
   - Found: [Summary]
   - Chose: [Link B] (reason: ...)

3. **Level 3**: [URL]
   - Found: [Summary]
   - [FOUND TARGET / Chose next link]

[Continue for each level]

### Result
Status: ✅ Found / ⚠️ Partially Found / ❌ Not Found

**Final Content**:
[If found, provide the target information]

**Final URL**: [URL where target was found]

### All URLs Visited
1. [URL] - [What was found]
2. [URL] - [What was found]
...

### Dead Ends Encountered
- [URL] - [Why it didn't lead to target]

### Alternative Paths Not Taken
- [URL] - [Why it was deprioritized]

### Recommendations
[If not found, suggest next steps]
```

## Execution Guidelines
1. **Depth limit: 5 levels** - prevents infinite navigation
2. **Parallel when possible**: Explore multiple promising paths at same time
3. **Track visited URLs**: Avoid revisiting same pages
4. **Prefer specificity**: Choose more specific links over general ones
5. **Look for patterns**: Official docs often in /docs/, /guide/, /help/
6. **Use TodoWrite**: Track navigation depth

## Navigation Heuristics
**High-value indicators in URLs**:
- /docs/, /documentation/
- /guide/, /tutorial/
- /download/, /files/
- /official/, /formal/
- /api/, /reference/

**High-value indicators in link text**:
- "Official guide"
- "Download"
- "Documentation"
- "How to"
- "Requirements"

## Best For
- Finding specific documents on complex government/corporate sites
- Navigating to deeply nested information
- When direct search doesn't reveal the target
- Understanding site structure and content organization
