---
description: Suggest refactoring improvements for code quality
argument-hint: [file-path]
allowed-tools: [Read, Grep, Bash]
---

# Refactoring Suggestions

Analyze $ARGUMENTS and suggest refactoring improvements.

## Refactoring Goals

### 1. Code Smells to Address

#### Bloaters
- **Long Method**: Functions that are too long
- **Large Class**: Classes with too many responsibilities
- **Primitive Obsession**: Overuse of primitives instead of objects
- **Long Parameter List**: Too many function parameters
- **Data Clumps**: Groups of data that always appear together

#### Object-Orientation Abusers
- **Switch Statements**: Replace with polymorphism
- **Temporary Field**: Fields only used in certain cases
- **Refused Bequest**: Subclass doesn't use inherited methods
- **Alternative Classes**: Different interfaces, similar functionality

#### Change Preventers
- **Divergent Change**: One class changed for different reasons
- **Shotgun Surgery**: One change requires many small changes
- **Parallel Inheritance**: Adding class requires adding another

#### Dispensables
- **Comments**: Explaining bad code instead of improving it
- **Duplicate Code**: Same code in multiple places
- **Lazy Class**: Class that doesn't do much
- **Dead Code**: Unused code
- **Speculative Generality**: Unused flexibility

#### Couplers
- **Feature Envy**: Method uses another class more than its own
- **Inappropriate Intimacy**: Classes too coupled
- **Message Chains**: Long chains of method calls
- **Middle Man**: Class that just delegates

### 2. Refactoring Techniques

#### Composing Methods
- Extract Method
- Inline Method
- Extract Variable
- Inline Temp
- Replace Temp with Query
- Split Temporary Variable

#### Moving Features
- Move Method
- Move Field
- Extract Class
- Inline Class

#### Organizing Data
- Encapsulate Field
- Replace Magic Number with Constant
- Replace Type Code with Class
- Replace Array with Object

#### Simplifying Conditionals
- Decompose Conditional
- Consolidate Conditional Expression
- Remove Control Flag
- Replace Nested Conditional with Guard Clauses

#### Simplifying Method Calls
- Rename Method
- Add Parameter
- Remove Parameter
- Separate Query from Modifier
- Parameterize Method

## Output Format

For each refactoring opportunity:
1. **Code Smell**: What pattern is detected
2. **Location**: File and line numbers
3. **Current Code**: Problematic code snippet
4. **Impact**: Why it's problematic
5. **Refactoring Technique**: Suggested approach
6. **Refactored Code**: Improved implementation
7. **Benefits**: What improves after refactoring
8. **Risks**: Any potential issues with the change

### Priority Levels
- **High**: Significantly impacts maintainability
- **Medium**: Notable improvement possible
- **Low**: Minor polish

Ensure refactorings maintain existing functionality (no behavior changes).
