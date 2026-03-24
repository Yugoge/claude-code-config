---
description: Tree search exploration with MCTS-inspired path evaluation
argument-hint: <question-or-problem>
---

Explore multiple solution paths for: **$ARGUMENTS**

## Methodology: Tree Search with Path Evaluation

Inspired by MCTS (Monte Carlo Tree Search) and LATS (Language Agent Tree Search).

### Phase 1: Path Generation
Generate 3-5 distinct possible search paths to answer the question.

Example: Question "How to start an AI company in 2025?"
Possible paths:
- Path A: Technical approach (infrastructure, tools, ML stack)
- Path B: Business approach (funding, market, customers)
- Path C: Legal approach (incorporation, regulations, IP)
- Path D: Talent approach (hiring, team building, culture)
- Path E: Product approach (MVP, validation, iteration)

### Phase 2: Initial Path Exploration (parallel)
For each path, execute 1-2 exploratory searches **in parallel**.

Prompt for each:
```
Explore the "$ARGUMENTS" question from the [PATH NAME] angle.
What are the key considerations, steps, or information needed?
Provide: main points, potential challenges, resources needed.
```

### Phase 3: Path Evaluation
For each path, score based on:
- **Relevance** (0-3): How directly it addresses the question
- **Completeness** (0-3): How fully it answers the question
- **Actionability** (0-3): How practical/implementable the info is
- **Evidence Quality** (0-1): Quality of sources found

Total score: 0-10 per path

### Phase 4: Deep Dive on Top Paths
Select the top 2 highest-scoring paths.
For each, execute 3-5 deep searches:
```
Deep dive into [PATH NAME] for "$ARGUMENTS".
Find: specific steps, expert advice, case studies, data.
Prioritize: actionable information, recent examples, proven methods.
```

Execute these **in parallel**.

### Phase 5: Recursive Refinement (optional)
If the top path reveals new sub-paths worth exploring:
- Generate 2-3 sub-paths within the best path
- Repeat evaluation and exploration (max depth: 2 levels)

### Phase 6: Integration & Decision
Synthesize findings from all explored paths:

```markdown
## Tree Search Report: $ARGUMENTS

### Question
$ARGUMENTS

### Paths Explored
1. **Path A: [Name]** - Score: [X/10]
   - Key findings: [...]
   - Strengths: [...]
   - Limitations: [...]

2. **Path B: [Name]** - Score: [X/10]
   - Key findings: [...]
   - Strengths: [...]
   - Limitations: [...]

[Continue for all paths]

### Recommended Path(s)
Based on evaluation, the optimal approach is: **[Path Name(s)]**

Reasoning: [Why this path scored highest]

### Integrated Solution
[Combine insights from multiple paths into cohesive answer]

### Implementation Steps
1. [Actionable step from best path]
2. [...]
3. [Consider incorporating elements from secondary paths]

### Alternative Approaches
[Brief summary of other viable paths not chosen]

### Decision Tree Visualization
```
Question: $ARGUMENTS
├─ Path A [Score: X/10] → [Outcome]
├─ Path B [Score: X/10] → [Outcome] ✓ SELECTED
│  ├─ Sub-path B1 → [...]
│  └─ Sub-path B2 → [...]
├─ Path C [Score: X/10] → [Outcome]
└─ Path D [Score: X/10] → [Outcome]
```

### Sources by Path
**Path A**: [URLs]
**Path B**: [URLs]
...

### Reflection
What worked: [...]
What didn't: [...]
If I were to search again: [...]
```

## Execution Guidelines
1. **Diverse paths**: Ensure paths approach from different angles
2. **Parallel exploration**: Explore all paths simultaneously initially
3. **Honest scoring**: Don't force a path to work if evidence is weak
4. **Prune dead ends**: If a path scores <4, don't deep dive
5. **Combine insights**: Best solution often integrates multiple paths
6. **Use TodoWrite**: Track which paths are being explored

## Best For
- Open-ended questions with multiple valid approaches
- Problems requiring evaluation of trade-offs
- Strategic decisions with uncertainty
- Research where the "best" path isn't obvious
