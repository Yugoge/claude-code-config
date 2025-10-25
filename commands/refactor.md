---
description: Suggest refactoring improvements for code quality
argument-hint: [file-path]
allowed-tools: [Read, Grep, Bash]
---

# Refactoring Suggestions | 重构建议

Analyze $ARGUMENTS and suggest refactoring improvements.

## Refactoring Goals | 重构目标

### 1. Code Smells to Address | 要解决的代码异味

#### Bloaters | 膨胀者
- **Long Method**: Functions that are too long
- **Large Class**: Classes with too many responsibilities
- **Primitive Obsession**: Overuse of primitives instead of objects
- **Long Parameter List**: Too many function parameters
- **Data Clumps**: Groups of data that always appear together

#### Object-Orientation Abusers | 面向对象滥用
- **Switch Statements**: Replace with polymorphism
- **Temporary Field**: Fields only used in certain cases
- **Refused Bequest**: Subclass doesn't use inherited methods
- **Alternative Classes**: Different interfaces, similar functionality

#### Change Preventers | 变更妨碍者
- **Divergent Change**: One class changed for different reasons
- **Shotgun Surgery**: One change requires many small changes
- **Parallel Inheritance**: Adding class requires adding another

#### Dispensables | 非必要元素
- **Comments**: Explaining bad code instead of improving it
- **Duplicate Code**: Same code in multiple places
- **Lazy Class**: Class that doesn't do much
- **Dead Code**: Unused code
- **Speculative Generality**: Unused flexibility

#### Couplers | 耦合者
- **Feature Envy**: Method uses another class more than its own
- **Inappropriate Intimacy**: Classes too coupled
- **Message Chains**: Long chains of method calls
- **Middle Man**: Class that just delegates

### 2. Refactoring Techniques | 重构技术

#### Composing Methods | 方法组合
- Extract Method
- Inline Method
- Extract Variable
- Inline Temp
- Replace Temp with Query
- Split Temporary Variable

#### Moving Features | 特性移动
- Move Method
- Move Field
- Extract Class
- Inline Class

#### Organizing Data | 数据组织
- Encapsulate Field
- Replace Magic Number with Constant
- Replace Type Code with Class
- Replace Array with Object

#### Simplifying Conditionals | 简化条件
- Decompose Conditional
- Consolidate Conditional Expression
- Remove Control Flag
- Replace Nested Conditional with Guard Clauses

#### Simplifying Method Calls | 简化方法调用
- Rename Method
- Add Parameter
- Remove Parameter
- Separate Query from Modifier
- Parameterize Method

## Output Format | 输出格式

For each refactoring opportunity:
1. **Code Smell**: What pattern is detected
2. **Location**: File and line numbers
3. **Current Code**: Problematic code snippet
4. **Impact**: Why it's problematic
5. **Refactoring Technique**: Suggested approach
6. **Refactored Code**: Improved implementation
7. **Benefits**: What improves after refactoring
8. **Risks**: Any potential issues with the change

### Priority Levels | 优先级
- **High**: Significantly impacts maintainability
- **Medium**: Notable improvement possible
- **Low**: Minor polish

Ensure refactorings maintain existing functionality (no behavior changes).
