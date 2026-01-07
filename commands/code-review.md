---
description: Comprehensive code review with best practices analysis
argument-hint: [file-path-or-pattern]
allowed-tools: [Read, Grep, Glob, Bash]
---

# Code Review

Perform a comprehensive code review on $ARGUMENTS following these criteria:

## Review Checklist | 审查清单

### 1. Code Quality
- **Readability**: Is the code easy to understand?
- **Naming**: Are variables and functions well-named?
- **Complexity**: Is the code unnecessarily complex?
- **DRY Principle**: Is there code duplication?

### 2. Security | 安全性
- **Input Validation**: Are inputs properly validated?
- **Secrets**: Are there any hardcoded credentials or API keys?
- **Injection**: Is the code vulnerable to injection attacks?
- **Dependencies**: Are dependencies up-to-date and secure?

### 3. Performance | 性能
- **Algorithms**: Are appropriate algorithms used?
- **Resource Usage**: Is memory/CPU used efficiently?
- **Caching**: Can caching improve performance?
- **Database Queries**: Are queries optimized?

### 4. Testing
- **Test Coverage**: Are there sufficient tests?
- **Edge Cases**: Are edge cases handled?
- **Error Handling**: Is error handling robust?

### 5. Documentation | 文档
- **Comments**: Are complex parts explained?
- **API Docs**: Are public APIs documented?
- **README**: Is setup/usage documented?

## Output Format

Provide:
1. **Summary** - Overall assessment
2. **Critical Issues** - Must-fix problems (security, bugs)
3. **Major Issues** - Should-fix problems (performance, maintainability)
4. **Minor Issues** - Nice-to-fix improvements (style, optimization)
5. **Positive Aspects** - What's done well
6. **Recommendations** - Specific actionable suggestions

Focus on being constructive and provide specific examples and suggestions for improvement.
