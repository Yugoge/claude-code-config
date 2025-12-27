# Git Lock File Handling

## 概述

`push.sh` 和 `pull.sh` 脚本现在自动检测并处理 git lock 文件冲突。

## 什么是 Git Lock 文件？

Git 使用 `.git/index.lock` 文件来防止多个进程同时修改仓库。当 git 操作正在进行时，会创建这个文件；操作完成后自动删除。

## 问题场景

Lock 文件可能会在以下情况下残留：
- Git 进程被强制中断（Ctrl+C）
- 系统崩溃或重启
- 进程挂起或卡死

## 错误信息示例

```
fatal: Unable to create '/path/to/repo/.git/index.lock': File exists.
Another git process seems to be running in this repository
```

## 自动检测功能

### Push 脚本 (`hooks/push.sh`)

在 Step 7（创建 commit 之前）自动检测 lock 文件：

1. **检测 lock 文件存在**
   - 如果 `.git/index.lock` 存在，显示警告

2. **检查活跃进程**
   - 使用 `ps aux | grep git` 检查是否有其他 git 进程运行
   - 如果有活跃进程，退出并提示用户等待

3. **处理陈旧锁文件**
   - 如果没有活跃进程，判定为陈旧文件
   - 询问用户是否删除：`Remove the lock file and continue? (y/n)`
   - 用户确认后自动删除并继续操作

### Pull 脚本 (`hooks/pull.sh`)

在 Step 4（执行 pull 操作之前）自动检测，逻辑与 push 相同。

**特殊处理**：如果已经创建了 stash，在退出前会自动恢复 stashed 内容。

## 用户体验

### 场景 1：陈旧锁文件（最常见）

```
⚠️  Warning: Git lock file detected

A lock file exists at: .git/index.lock
This usually means:
  • Another git process is running
  • A previous git process crashed

No active git processes detected.
The lock file appears to be stale (from a crashed process).

Remove the lock file and continue? (y/n)
```

**用户操作**：输入 `y` 继续，脚本自动清理并继续操作

### 场景 2：活跃的 Git 进程

```
⚠️  Warning: Git lock file detected

Active git processes found:
user  12345  0.1  0.2  git fetch origin

Please wait for other git operations to complete.
```

**用户操作**：等待其他进程完成，然后重新运行脚本

## 手动清理（如果需要）

如果自动清理失败，可以手动删除：

```bash
rm .git/index.lock
```

**注意**：仅在确认没有其他 git 进程运行时手动删除！

## 安全性

✅ **安全检查**：
- 总是先检查活跃进程再删除
- 需要用户确认才删除
- 提供清晰的错误信息和建议

⚠️ **不会自动删除的情况**：
- 检测到活跃的 git 进程时
- 用户拒绝删除确认时

## 测试

运行测试验证功能：

```bash
bash ~/.claude/tests/test-lock-detection.sh
```

测试覆盖：
1. ✓ Lock 文件检测
2. ✓ Git 进程检测
3. ✓ Lock 文件删除
4. ✓ Git 操作恢复

## 技术实现

### 检测代码

```bash
LOCK_FILE=".git/index.lock"
if [ -f "$LOCK_FILE" ]; then
  # 检测逻辑
  GIT_PROCESSES=$(ps aux | grep -i '[g]it' | grep -v grep || true)

  if [ -n "$GIT_PROCESSES" ]; then
    # 有活跃进程，退出
    echo "Please wait for other git operations to complete."
    exit 1
  else
    # 陈旧文件，询问删除
    read -r RESPONSE
    if [ "$RESPONSE" = "y" ]; then
      rm -f "$LOCK_FILE"
    fi
  fi
fi
```

### 集成点

- **push.sh**: Line 129-172 (Step 7)
- **pull.sh**: Line 55-117 (Step 4)

## 改进历史

**Version 1.1** (2025-10-28)
- 添加自动 lock 文件检测
- 智能区分活跃进程和陈旧文件
- 用户确认机制
- Pull 脚本中保护 stash 内容

**Version 1.0** (初始版本)
- 基础 push/pull 功能
- 未处理 lock 文件冲突

## 常见问题

**Q: 为什么会出现 lock 文件？**
A: 通常是因为 git 操作被中断（Ctrl+C）或系统崩溃。

**Q: 删除 lock 文件安全吗？**
A: 只要确认没有其他 git 进程运行，删除是安全的。脚本会自动检查。

**Q: 如果我选择 "n" 不删除呢？**
A: 脚本会退出，你需要手动处理或重新运行。

**Q: 会丢失数据吗？**
A: 不会。Lock 文件只是一个锁机制，删除它不会影响代码内容。

## 相关文件

- `hooks/push.sh` - Push 脚本（含 lock 检测）
- `hooks/pull.sh` - Pull 脚本（含 lock 检测）
- `tests/test-lock-detection.sh` - Lock 文件检测测试
- `docs/git-tracking-solution-plan.md` - 完整实现计划

## 贡献

如果发现 bug 或有改进建议，请在项目中创建 issue。
