---
description: Debug assistance and troubleshooting guidance
argument-hint: [error-message-or-file]
allowed-tools: [Read, Grep, Glob, Bash]
---

# Debug Assistance | 调试辅助

Provide debugging help for $ARGUMENTS.

## Debugging Methodology | 调试方法论

### 1. Understand the Problem | 理解问题

#### Gather Information | 收集信息
- **Error Message**: Exact error text
- **Stack Trace**: Full stack trace
- **Context**: What were you trying to do?
- **Environment**: OS, language version, dependencies
- **Reproducibility**: Can you reproduce it consistently?

#### Questions to Ask | 要问的问题
- What is the expected behavior?
- What is the actual behavior?
- When did it start happening?
- What changed recently?
- Does it happen in all environments?

### 2. Isolate the Issue | 隔离问题

#### Techniques | 技术
- **Binary Search**: Remove half the code, test, repeat
- **Minimal Reproduction**: Create smallest example that fails
- **Change One Thing**: Test one change at a time
- **Rubber Duck Debugging**: Explain the problem out loud

### 3. Common Error Patterns | 常见错误模式

#### Syntax Errors | 语法错误
- Missing parentheses, brackets, braces
- Incorrect indentation
- Typos in keywords
- Missing semicolons (language-dependent)

#### Runtime Errors | 运行时错误
- **NullPointerException / TypeError**: Accessing null/undefined
- **IndexError / ArrayIndexOutOfBounds**: Invalid array index
- **KeyError / NameError**: Missing dictionary key or variable
- **TypeError**: Wrong type used
- **DivisionByZero**: Division by zero

#### Logic Errors | 逻辑错误
- Off-by-one errors
- Incorrect conditional logic
- Wrong operator (= vs ==)
- Incorrect loop conditions
- Unintended side effects

#### Concurrency Errors | 并发错误
- Race conditions
- Deadlocks
- Resource contention
- Thread safety issues

#### Integration Errors | 集成错误
- API version mismatch
- Network connectivity
- Authentication failures
- Database connection issues
- Missing environment variables

### 4. Debugging Tools | 调试工具

#### Language-Specific | 特定语言
- **Python**: pdb, ipdb, print(), logging
- **JavaScript**: console.log(), debugger, Chrome DevTools
- **Java**: jdb, IDE debuggers (IntelliJ, Eclipse)
- **Go**: delve, fmt.Println()
- **C/C++**: gdb, lldb, valgrind
- **Rust**: rust-gdb, dbg!() macro

#### General Tools | 通用工具
- **Logging**: Add strategic log statements
- **Breakpoints**: Pause execution at specific points
- **Watch Variables**: Monitor variable values
- **Step Through**: Execute line by line
- **Call Stack**: Examine function call chain

### 5. Debugging Strategies | 调试策略

#### Print Debugging | 打印调试
```
Add print statements to:
- Verify code execution reaches certain points
- Check variable values at different stages
- Confirm function inputs and outputs
- Trace execution flow
```

#### Divide and Conquer | 分而治之
```
1. Identify the failing section
2. Split it in half
3. Test which half fails
4. Repeat until you find the exact line
```

#### Scientific Method | 科学方法
```
1. Observe the problem
2. Form hypothesis about the cause
3. Test hypothesis
4. Analyze results
5. Repeat until solved
```

### 6. Common Solutions | 常见解决方案

#### Quick Fixes | 快速修复
- Check for typos
- Verify imports/includes
- Confirm file paths
- Check variable scope
- Validate function arguments
- Review recent changes

#### Dependencies | 依赖问题
- Update dependencies
- Clear cache (node_modules, __pycache__, etc.)
- Reinstall packages
- Check version compatibility

#### Environment | 环境问题
- Verify environment variables
- Check file permissions
- Confirm working directory
- Review configuration files

## Output Format | 输出格式

Provide debugging assistance with:

1. **Problem Analysis**
   - Error interpretation
   - Likely causes
   - Similar known issues

2. **Diagnostic Steps**
   - How to gather more information
   - What to check
   - Commands to run

3. **Potential Solutions**
   - Ordered by likelihood
   - Step-by-step fixes
   - Code examples

4. **Prevention**
   - How to avoid this in the future
   - Best practices
   - Testing strategies

5. **Additional Resources**
   - Related documentation
   - Similar issues (if known)
   - Debugging tools to try

Use 中文 and English to explain complex concepts clearly.
