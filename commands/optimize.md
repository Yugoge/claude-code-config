---
description: Analyze code for performance optimization opportunities
argument-hint: [file-path]
allowed-tools: [Read, Grep, Bash]
---

# Performance Optimization Analysis

Analyze $ARGUMENTS for performance optimization opportunities.

## Analysis Focus

### 1. Algorithm Complexity
- Identify O(n²) or worse algorithms that could be improved
- Suggest more efficient data structures
- Look for unnecessary nested loops

### 2. Resource Usage
- Memory leaks or excessive allocations
- Unnecessary object creation
- Large data structures that could be optimized

### 3. Database & I/O
- N+1 query problems
- Missing indexes
- Inefficient queries
- File I/O that could be batched or cached

### 4. Caching Opportunities
- Repeated calculations that could be memoized
- API calls that could be cached
- Static data that should be precomputed

### 5. Concurrency
- Blocking operations that could be async
- Opportunities for parallel processing
- Race conditions or deadlocks

### 6. Code-level Optimizations
- String concatenation in loops
- Inefficient regular expressions
- Unnecessary type conversions
- Function call overhead

## Output Format

For each optimization opportunity, provide:
1. **Location** - File and line number
2. **Current Implementation** - Code snippet
3. **Issue** - Performance problem explanation
4. **Impact** - Estimated performance improvement
5. **Suggested Solution** - Optimized code example
6. **Trade-offs** - Any readability or complexity concerns

Prioritize by impact: High → Medium → Low
