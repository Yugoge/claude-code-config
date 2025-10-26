---
description: Intelligent site navigation simulating "click-through" exploration
argument-hint: <url> <task>
---

Navigate **$1** to accomplish: **$2**

## Methodology: Simulated Navigation (Grok-style)

Simulate intelligent site navigation without actual browser interaction.

### Phase 1: Homepage Analysis
WebFetch the starting URL ($1) with this prompt:
```
Analyze this page structure to find information about "$2".

Extract:
1. **Navigation Structure**: All menu items, categories, sections
2. **Key Links**: URLs that might lead to "$2"
3. **Search Functionality**: Any search box or site search feature
4. **Direct Matches**: Any content directly related to "$2" on this page

For each relevant link, provide:
- Link text
- Complete URL
- Estimated relevance to goal (High/Medium/Low)
- Why it might contain the target information

Organize by estimated relevance.
```

### Phase 2: Path Selection
From Phase 1 analysis, select the top 3 most promising links.

Selection criteria:
- Link text explicitly mentions keywords from $2
- URL structure suggests relevant content (e.g., /docs/, /guide/, /download/)
- Description indicates authoritative/official content

### Phase 3: Parallel Exploration
WebFetch the top 3 links **in parallel** with this prompt:
```
Search this page for information about "$2".

If found:
- Extract the complete information
- Note any downloadable resources (PDFs, forms)
- Identify any deeper links that provide more details

If not found:
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
WebFetch: $1/sitemap.xml or $1/sitemap.html
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
