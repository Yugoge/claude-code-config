---
description: Reflection-driven iterative search with goal evaluation
argument-hint: <search-goal>
---

Execute reflection-driven search for: **$ARGUMENTS**

## Methodology: Goal-Oriented Search with Self-Reflection

Inspired by RE-Searcher (Robust Agentic Search).

### Step 1: Articulate Concrete Goal
Transform the user request into a specific, measurable search goal.

Example:
- User: "Find info about Korean visas"
- Goal: "Find official Korean tourist visa (C-3) application guide with required documents list, fees, and processing time"

**Articulated Goal for this search**: [Specific, measurable version of "$ARGUMENTS"]

### Step 2: Initial Search
Execute initial search based on articulated goal:
```
WebSearch: [Goal keywords] official guide
WebSearch: [Goal keywords] requirements 2024 2025
```

### Step 3: Reflection Loop (max 5 iterations)

After each search iteration, perform structured reflection:

#### Reflection Questions:
1. **Goal Achievement**
   - Does the retrieved evidence satisfy the goal?
   - Score: 0-10 (0=nothing, 10=completely satisfied)

2. **Missing Information**
   - What critical pieces are still missing?
   - List specific gaps: [...]

3. **Evidence Quality**
   - Are sources authoritative and current?
   - Are there contradictions or uncertainties?

4. **Next Action Decision**
   - [ ] Goal achieved (score ≥ 8) → Proceed to synthesis
   - [ ] Need deeper search on current path (score 4-7) → Continue
   - [ ] Need pivot to different approach (score < 4) → Change strategy

#### Reflection Output Format:
```markdown
### Reflection - Iteration [N]

**Goal Achievement Score**: [X/10]

**What was found**: [Bullet points of key findings]

**What's still missing**: [Specific gaps]

**Evidence quality**: [Assessment]

**Decision**: [CONTINUE / PIVOT / DONE]

**Reasoning**: [Why this decision]

**Next search strategy**: [If continuing, what to search next]
```

### Step 4: Adaptive Search
Based on reflection decision:

**If CONTINUE**: Execute deeper search on current path
```
WebSearch: [More specific query based on gaps identified]
Playwright: Navigate to most promising URLs from previous iteration
```

⚠️ **CRITICAL**: WebFetch is DISABLED (timeout risk). Use Playwright MCP for page content extraction.

**If PIVOT**: Change search strategy
```
Try alternative sources: government sites, academic papers, forums
Try alternative keywords or framing
Try different domains or languages
```

**If DONE**: Proceed to synthesis

### Step 5: Final Synthesis
After goal is achieved or max iterations reached:

```markdown
## Reflection-Driven Search Report: $ARGUMENTS

### Articulated Goal
[Specific, measurable goal]

### Goal Achievement
Final Score: [X/10]
Status: ✅ Fully Achieved / ⚠️ Partially Achieved / ❌ Not Achieved

### Search Journey
**Iteration 1**:
- Searched: [...]
- Found: [...]
- Reflection: [Summary]
- Score: [X/10]

**Iteration 2**:
- Searched: [...]
- Found: [...]
- Reflection: [Summary]
- Score: [X/10]

[Continue for all iterations]

### Key Findings
[Organized list of all findings that satisfy the goal]

### Unfulfilled Aspects
[If score < 10, what's still missing and why]

### Evidence Quality Assessment
- Sources used: [N] 
- Authority level: [High/Medium/Low]
- Recency: [All within X months/years]
- Consistency: [Findings align / Some contradictions]

### Recommendations
[Based on findings, what actions should user take]

### Learning for Future Searches
- What worked well: [...]
- What didn't work: [...]
- If searching again, I would: [...]
```

## Execution Guidelines
1. **Be specific with goals**: Vague goals lead to unfocused searches
2. **Honest reflection**: Don't artificially inflate scores
3. **Iterate up to 5 times**: More than that suggests need to pivot or reframe
4. **Track reasoning**: Document why each decision was made
5. **Use TodoWrite**: Track iteration progress

## Reflection Triggers
Automatic pivot if:
- 3 consecutive iterations with score increase < 1
- Same information appearing repeatedly
- All searches return no new relevant info

## Best For
- Complex searches where initial attempts often fail
- Finding very specific information
- Situations requiring verification and validation
- When unsure of the best search strategy upfront
