---
description: Generate comprehensive documentation for code
argument-hint: [file-path-or-module]
allowed-tools: [Read, Grep, Glob]
---

# Documentation Generation

Generate comprehensive documentation for $ARGUMENTS.

## Documentation Types

### 1. API Documentation

#### Function/Method Documentation
- **Purpose**: What does it do?
- **Parameters**: Name, type, description, default value
- **Returns**: Type and description
- **Raises/Throws**: Exceptions and when they occur
- **Examples**: Usage examples
- **Notes**: Special considerations

#### Format by Language:
- **Python**: docstring (Google, NumPy, or Sphinx style)
- **JavaScript/TypeScript**: JSDoc
- **Java**: JavaDoc
- **Go**: godoc comments
- **Rust**: rustdoc comments
- **C#**: XML documentation

### 2. Module/Class Documentation

- **Overview**: Purpose and responsibility
- **Architecture**: Design and structure
- **Usage**: How to use it
- **Examples**: Code examples
- **Dependencies**: Required packages
- **See Also**: Related modules

### 3. README Documentation

#### Essential Sections:
1. **Project Title & Description**
   - What is it?
   - Why does it exist?

2. **Features**
   - Key capabilities
   - What makes it useful?

3. **Installation**
   - Prerequisites
   - Step-by-step setup
   - Dependencies

4. **Quick Start**
   - Minimal working example
   - Common use cases

5. **Usage**
   - Detailed examples
   - Configuration options
   - CLI usage (if applicable)

6. **API Reference**
   - Link to full API docs
   - Key functions/classes

7. **Contributing**
   - How to contribute
   - Coding standards
   - Pull request process

8. **Testing**
   - How to run tests
   - Test coverage

9. **License**
   - License type
   - Copyright info

10. **Authors & Acknowledgments**
    - Contributors
    - Credits

### 4. Architecture Documentation

- **System Overview**: High-level architecture
- **Components**: Major parts and responsibilities
- **Data Flow**: How data moves through the system
- **Design Decisions**: Why things are built this way
- **Diagrams**: Architecture diagrams (ASCII or Mermaid)

### 5. Change Documentation

#### CHANGELOG.md Format:
```markdown
# Changelog

## [Version] - YYYY-MM-DD
### Added
- New features

### Changed
- Changes to existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes
```

## Documentation Best Practices

### Writing Style
- **Clear**: Use simple, direct language
- **Concise**: Remove unnecessary words
- **Complete**: Cover all important aspects
- **Correct**: Keep documentation up-to-date
- **Consistent**: Use consistent terminology

### Code Examples
- Include imports/setup
- Show expected output
- Use realistic examples
- Cover common use cases
- Include error handling

### Maintenance
- Update docs with code changes
- Review docs regularly
- Remove outdated information
- Fix broken links

## Output Format

Generate documentation that includes:

1. **Inline Comments** (if needed)
   - Complex algorithms
   - Non-obvious logic
   - Important constraints

2. **Docstrings/API Docs**
   - All public functions/classes
   - Proper format for the language
   - Complete parameter descriptions

3. **README Sections**
   - All essential sections
   - Formatted markdown
   - Links and badges

4. **Examples**
   - Working code examples
   - Expected outputs
   - Common patterns
