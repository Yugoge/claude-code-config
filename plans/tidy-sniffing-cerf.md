# Fix: Session Recovery Script — stdin 泄漏 + Server 健康检查

## Context

服务器重启后，recovery 脚本只恢复了 2/11 个 session。根因是 `daemon_spawn_session()` 中 `nohup node ...` 没有关闭 stdin，导致 Node 子进程吃掉了 while-read 循环剩余的 stdin 数据。同时脚本缺少 server 可达性检查，在 Docker 容器尚未就绪时就开始 spawn session。

## 修改文件

`/root/bin/happy-session-recovery.sh`

## 修复 1：stdin 泄漏（根因）

**行 608-609** — `daemon_spawn_session()` 函数：

```bash
# Before (bug):
env $spawn_env IS_SANDBOX=1 nohup node "$cli_path" $args \
    > /dev/null 2>&1 &

# After (fix):
env $spawn_env IS_SANDBOX=1 nohup node "$cli_path" $args \
    < /dev/null > /dev/null 2>&1 &
```

加 `< /dev/null` 阻止子进程继承 while-read 循环的 stdin。这是唯一的根因修复。

## 修复 2：Server 健康检查等待

在 `restore_online_sessions()` 中，daemon 就绪检查之后（行 651）、开始恢复之前，加入 server 健康检查：

```bash
# Wait for happy-server to be reachable
local server_url=""
for home in "${HAPPY_HOMES[@]}"; do
    local dpid
    dpid=$(python3 -c "import json; print(json.load(open('$home/daemon.state.json'))['pid'])" 2>/dev/null)
    [ -n "$dpid" ] && [ -d "/proc/$dpid" ] && {
        server_url=$(tr '\0' '\n' < /proc/$dpid/environ 2>/dev/null | grep '^HAPPY_SERVER_URL=' | cut -d= -f2-)
        [ -n "$server_url" ] && break
    }
done

if [ -n "$server_url" ]; then
    local sw=0 smax=60
    log "Waiting for server at $server_url ..."
    while [ $sw -lt $smax ]; do
        if curl -sf -o /dev/null --connect-timeout 3 "$server_url/health" 2>/dev/null || \
           curl -sf -o /dev/null --connect-timeout 3 "$server_url/" 2>/dev/null; then
            break
        fi
        sleep 3
        sw=$((sw + 3))
    done
    if [ $sw -ge $smax ]; then
        log "WARNING: Server not reachable after ${smax}s, proceeding anyway"
    else
        log "Server reachable after ${sw}s"
    fi
fi
```

插入位置：行 651 (`log "Daemon(s) available, starting restore"`) 之后。

## 验证

1. 检查修改后的脚本语法：`bash -n /root/bin/happy-session-recovery.sh`
2. 模拟测试：手动调用 `happy-session-recovery.sh restore`（当前所有 session 已在线，会全部 skip 为 already running）
3. 未来重启时验证：观察 `/var/log/happy-session-recovery.log` 中是否出现所有 session 的 "Restoring" 日志
