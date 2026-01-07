---
description: Generate comprehensive test cases for code
argument-hint: [file-path-or-function]
allowed-tools: [Read, Grep, Glob]
---

# Test Generation

Generate comprehensive test cases for $ARGUMENTS.

## Test Strategy

### 1. Test Types

#### Unit Tests
- Test individual functions/methods in isolation
- Mock external dependencies
- Fast execution
- High coverage

#### Integration Tests
- Test component interactions
- Real dependencies where appropriate
- API endpoint testing
- Database integration

#### Edge Cases
- Boundary values
- Invalid inputs
- Error conditions
- Extreme scenarios

### 2. Test Coverage Areas

#### Happy Path
- Expected inputs and outputs
- Common use cases
- Typical workflows

#### Error Handling
- Invalid inputs
- Null/undefined values
- Empty collections
- Type mismatches
- Out-of-range values

#### Edge Cases
- Minimum/maximum values
- Empty strings
- Very large inputs
- Special characters
- Concurrent access

#### State Management
- Initial state
- State transitions
- State persistence
- State cleanup

### 3. Test Structure

Follow AAA pattern:
- **Arrange**: Set up test data and conditions
- **Act**: Execute the code under test
- **Assert**: Verify expected outcomes

### 4. Test Naming

Use descriptive names:
- `test_function_whenCondition_shouldExpectedBehavior`
- `should_returnExpectedValue_when_validInputProvided`

## Output Format

Generate test code with:

1. **Test Framework Setup**
   - Import statements
   - Test fixture/suite setup
   - Mock configurations

2. **Test Cases**
   - Clear test names
   - Arrange-Act-Assert structure
   - Descriptive comments
   - Assertions with meaningful messages

3. **Test Data**
   - Fixtures
   - Mock objects
   - Test constants

4. **Coverage Summary**
   - What's tested
   - What's not tested (and why)
   - Coverage percentage estimate

### Language-Specific Frameworks

- **Python**: pytest, unittest
- **JavaScript/TypeScript**: Jest, Mocha, Vitest
- **Java**: JUnit, TestNG
- **Go**: testing package
- **Rust**: built-in test framework
- **C#**: xUnit, NUnit

## Test Quality Principles

- **Independent**: Tests don't depend on each other
- **Repeatable**: Same results every time
- **Fast**: Quick execution
- **Readable**: Clear intent and structure
- **Maintainable**: Easy to update when code changes

Generate idiomatic tests for the target language.
