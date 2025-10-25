---
description: Create a well-formatted git commit with auto-generated message
argument-hint: [optional-message-prefix]
allowed-tools: [Bash, Read, Grep]
---

# Quick Commit | 快速提交

Create a git commit with an auto-generated message based on changes.

## Process | 流程

1. **Analyze Changes** | 分析变更
   - Review `git status` and `git diff`
   - Identify changed files and nature of changes
   - Categorize change type

2. **Generate Commit Message** | 生成提交信息
   - Follow Conventional Commits format
   - Include clear, descriptive summary
   - Add detailed body if needed

3. **Create Commit** | 创建提交
   - Stage appropriate files
   - Commit with generated message
   - Include co-authorship attribution

## Commit Message Format | 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types | 类型
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Other changes (dependencies, etc.)

### Scope | 范围 (optional)
- Component, module, or area affected
- Examples: `auth`, `api`, `ui`, `database`

### Subject | 主题
- Concise description (50 chars or less)
- Imperative mood: "add" not "added" or "adds"
- No period at the end
- Capitalize first letter

### Body | 正文 (optional)
- Explain the "why" not the "what"
- Wrap at 72 characters
- Separate from subject with blank line

### Footer | 页脚
- Breaking changes: `BREAKING CHANGE: description`
- Issue references: `Closes #123`
- Co-authorship attribution

## Example Commit Messages | 提交信息示例

```
feat(auth): add OAuth2 authentication

Implement OAuth2 flow for third-party authentication.
Supports Google, GitHub, and Microsoft providers.

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
```

```
fix(api): resolve race condition in user creation

The user creation endpoint had a race condition that could
lead to duplicate user records. Added transaction locking
to ensure atomicity.

Closes #456

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
```

## Execution | 执行

1. Run `git status` and `git diff` to analyze changes
2. Generate appropriate commit message
3. Stage files with `git add`
4. Commit with generated message using heredoc format
5. Confirm success with `git status`

If user provided $ARGUMENTS, use as message prefix or type.
