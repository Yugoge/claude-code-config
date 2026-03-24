# Happy 永久在线 Session 架构方案

## 现状分析

当前 session 生命周期：
1. daemon spawn session → happy-cli 进程启动 → WebSocket 连上 → session `active: true`
2. happy-cli 每隔一段时间发 `session-alive` 心跳
3. Claude SDK 进程退出 or happy-cli 进程退出 → daemon 调 `notifySessionEnd()` → server 立即标 `active: false`
4. 即使 happy-cli 没主动通知，server 也有 2 分钟超时自动标 offline

**问题**：session 进程退出 = session 离线。无法实现"永久在线等待消息"。

## 目标

1. Session 永远不自动 offline，只有用户手动 archive 才 offline
2. Daemon 启动时自动读取所有 online session，自动恢复 happy 进程
3. Happy 进程收到用户消息后自动连接 Claude 进程处理
4. Claude 处理完后退出，happy 进程继续等待下一条消息

## 方案设计

### 核心思路：分离 "happy-cli 进程" 和 "Claude 进程" 的生命周期

当前：`happy-cli 进程 = Claude 进程`。进程死了 session 就 offline。

改后：`happy-cli 进程 = 消息监听器（永久在线）`，Claude 进程按需启动/退出。

### 具体改动

#### 改动 1：`claudeRemoteLauncher.ts` — Claude 退出后不退出 happy-cli

**文件**：`/root/happy/packages/happy-cli/src/claude/claudeRemoteLauncher.ts`

当前行为：Claude SDK query 结束 → `nextMessage()` 返回 null → launcher 退出 → happy-cli 退出 → daemon 标 session offline。

改为：Claude SDK query 结束后，不退出 launcher，而是重新进入等待循环。happy-cli 进程保持活着，WebSocket 保持连接，继续发 `session-alive` 心跳。

**实现**：在 `claudeRemote.ts` 的主循环中，当 Claude conversation 结束时（`result.type === 'result'` 且没有新消息），不 return，而是回到 `nextMessage()` 等待下一条消息。收到新消息后，创建新的 Claude SDK query。

这是最小改动方案 — 不需要新的 launcher，只需要在现有 remote launcher 外面套一层 while(true) 循环。

#### 改动 2：`loop.ts` — remote mode 永不退出

**文件**：`/root/happy/packages/happy-cli/src/claude/loop.ts`

当前行为：`claudeRemoteLauncher` 返回后，loop 要么切到 local mode，要么退出。

改为：如果 `startedBy === 'daemon'`，remote launcher 返回后重新进入 remote launcher（不退出 loop）。只有显式 archive 请求才退出。

#### 改动 3：daemon `onChildExited` — 不立即通知 session offline

**文件**：`/root/happy/packages/happy-cli/src/daemon/run.ts:654-663`

当前行为：happy-cli 子进程退出 → 立即调 `notifySessionEnd()` → server 标 offline。

改为：如果改动 1 和 2 生效，happy-cli 进程不会退出（除非崩溃），所以这里的行为不变但触发频率大幅降低。

但为了防止崩溃后 session 永久 offline，需要增加**自动重启**逻辑：

```typescript
const onChildExited = (pid: number) => {
  const session = pidToTrackedSession.get(pid);
  if (session?.happySessionId) {
    // 不立即通知 offline，而是尝试重启
    logger.debug(`[DAEMON] Session ${session.happySessionId} exited, respawning...`);
    respawnSession(session);  // 新函数：用 --resume 重新 spawn
  }
};
```

#### 改动 4：daemon 启动时自动恢复 online session

**文件**：`/root/happy/packages/happy-cli/src/daemon/run.ts`

在 `apiMachine.connect()` 之后，daemon 应该：
1. 调用 `GET /v1/sessions` 获取当前账号所有 `active: true` 的 session
2. 对比本地已经在跑的进程
3. 对于不在跑的 online session，自动 spawn 恢复

这与 `happy-session-recovery.sh` 做的事情类似，但内置到 daemon 中更可靠。

```typescript
// After apiMachine.connect()
const activeSessions = await api.getActiveSessions();
for (const session of activeSessions) {
  if (!isAlreadyTracked(session.id)) {
    await spawnSession({
      directory: session.workingDir,  // 从 metadata 解密
      sessionId: session.claudeSessionId  // 从 metadata 解密
    });
  }
}
```

#### 改动 5：server timeout 放宽（可选）

**文件**：`/root/happy/packages/happy-server/sources/app/presence/timeout.ts`

当前 session 2 分钟没心跳就 offline。如果 happy-cli 进程永久在线且持续发心跳，这个 timeout 不需要改。但可以考虑增加一个 `persistent` flag：

```prisma
model Session {
  ...
  persistent  Boolean  @default(false)  // 标记为永久在线
}
```

`persistent: true` 的 session 不受 2 分钟 timeout 影响。只有手动 archive 才 offline。

#### 改动 6：archive API

需要一个显式的 archive 端点（如果还没有的话）：

```
POST /v1/sessions/:sessionId/archive
```

设置 `active: false` + metadata 中 `lifecycleState: 'archived'`。这是唯一让永久在线 session offline 的方式。

### 不需要改的

- **加密流程**：完全不变
- **消息收发**：WebSocket 已经是持久连接
- **session-alive 心跳**：happy-cli 已经在发，保持即可
- **机器 heartbeat**：daemon 的 `machine-alive` 不变

## 实现优先级

| 步骤 | 改动 | 复杂度 | 影响范围 |
|------|------|--------|---------|
| 1 | 改动 1+2：remote launcher 永不退出 | 低 | `claudeRemote.ts`, `loop.ts` |
| 2 | 改动 3：daemon 崩溃自动重启 session | 中 | `daemon/run.ts` |
| 3 | 改动 4：daemon 启动自动恢复 session | 中 | `daemon/run.ts`, `api.ts` |
| 4 | 改动 5+6：persistent flag + archive API | 低 | server routes, prisma schema |

步骤 1 是核心，做完就能实现"session 永不自动 offline"。
步骤 2-3 是容错，确保崩溃/重启后自动恢复。
步骤 4 是完善，给用户手动下线的能力。

## 风险

1. **内存泄漏**：happy-cli 进程永久运行，需要确保没有内存泄漏（特别是 Claude SDK 每次 query 后的清理）
2. **僵尸进程**：如果 happy-cli 进程死了但 daemon 没检测到，session 在 server 端 2 分钟后 timeout。改动 3 的自动重启能缓解
3. **资源占用**：每个 online session 占一个 Node.js 进程（~30MB）。10 个 session = ~300MB。可接受。
