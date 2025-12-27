---
description: Generate comprehensive test cases for code
argument-hint: [file-path-or-function]
allowed-tools: [Read, Grep, Glob]
---

# Test Generation | 测试生成

Generate comprehensive test cases for $ARGUMENTS.

## Test Strategy | 测试策略

### 1. Test Types | 测试类型

#### Unit Tests | 单元测试 (70%)
- Test individual functions/methods in isolation
- Mock external dependencies
- Fast execution
- High coverage

#### Integration Tests | 集成测试 (20%)
- Test component interactions
- Real dependencies where appropriate
- API endpoint testing
- Database integration

#### Edge Cases | 边界情况 (10%)
- Boundary values
- Invalid inputs
- Error conditions
- Extreme scenarios

### 2. Test Coverage Areas | 测试覆盖领域

#### Happy Path | 正常路径
- Expected inputs and outputs
- Common use cases
- Typical workflows

#### Error Handling | 错误处理
- Invalid inputs
- Null/undefined values
- Empty collections
- Type mismatches
- Out-of-range values

#### Edge Cases | 边界情况
- Minimum/maximum values
- Empty strings
- Very large inputs
- Special characters
- Concurrent access

#### State Management | 状态管理
- Initial state
- State transitions
- State persistence
- State cleanup

### 3. Test Structure | 测试结构

Follow AAA pattern:
- **Arrange**: Set up test data and conditions
- **Act**: Execute the code under test
- **Assert**: Verify expected outcomes

### 4. Test Naming | 测试命名

Use descriptive names:
- `test_function_whenCondition_shouldExpectedBehavior`
- `should_returnExpectedValue_when_validInputProvided`

## Output Format | 输出格式

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

### Language-Specific Frameworks | 特定语言框架

- **Python**: pytest, unittest
- **JavaScript/TypeScript**: Jest, Mocha, Vitest
- **Java**: JUnit, TestNG
- **Go**: testing package
- **Rust**: built-in test framework
- **C#**: xUnit, NUnit

## Test Quality Principles | 测试质量原则

- **Independent**: Tests don't depend on each other
- **Repeatable**: Same results every time
- **Fast**: Quick execution
- **Readable**: Clear intent and structure
- **Maintainable**: Easy to update when code changes

Generate idiomatic tests for the target language.
