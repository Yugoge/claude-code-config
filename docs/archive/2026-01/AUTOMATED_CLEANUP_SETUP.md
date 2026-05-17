# 自动化清理系统配置文档

## 📋 概述

已成功配置自动化清理系统，防止磁盘空间再次占满。系统包含三个核心组件：
1. **每日缓存清理** - 自动清理安全的临时文件和缓存
2. **每周Docker清理** - 清理未使用的Docker资源
3. **磁盘使用监控** - 实时监控并在超过阈值时发出警告

---

## ✅ 已完成的配置

### 1️⃣ 第一层清理（已执行）

**立即释放空间：4GB**
- ✅ Yarn缓存 (3.1GB)
- ✅ 旧Linux内核配置文件
- ✅ 系统日志 (7天以上)
- ✅ Python缓存文件 (.pyc, __pycache__)
- ✅ APT缓存

**结果：磁盘使用率从 99% 降至 89%**

---

## 🤖 自动化配置

### 清理脚本

#### `/root/bin/system-cache-cleanup.sh` (增强版)
**功能：** 每日自动清理安全缓存
**新增功能：**
- Yarn缓存清理
- 旧内核包清理
- 系统日志清理（保留7天）
- Python缓存清理
- APT缓存清理

**测试：**
```bash
# 测试模式（不实际执行）
/root/bin/system-cache-cleanup.sh true

# 实际执行
/root/bin/system-cache-cleanup.sh
```

#### `/root/bin/docker-cleanup.sh` (已存在)
**功能：** 每周清理未使用的Docker资源
- 未使用的容器
- 未使用的镜像
- 未使用的卷
- 未使用的网络
- 构建缓存

#### `/root/bin/disk-usage-monitor.sh` (新建)
**功能：** 监控磁盘使用率并发出警告
- 阈值：85%（可配置）
- 冷却期：6小时（避免重复警告）
- 自动记录日志

---

## ⏰ Cron定时任务

```bash
# 查看当前配置
crontab -l

# 当前配置：
0 3 * * *   /root/bin/system-cache-cleanup.sh  # 每天凌晨3点清理缓存
0 4 * * 0   /root/bin/docker-cleanup.sh        # 每周日凌晨4点清理Docker
0 */6 * * * /root/bin/disk-usage-monitor.sh    # 每6小时检查磁盘使用率
```

### 修改定时任务

```bash
# 编辑crontab
crontab -e

# 或者直接设置
crontab -l > /tmp/mycron
# 编辑 /tmp/mycron
crontab /tmp/mycron
```

---

## 🐳 Docker日志轮转

### 配置文件：`/etc/docker/daemon.json`

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",      // 单个日志文件最大100MB
    "max-file": "3",         // 保留最多3个日志文件
    "compress": "true"       // 压缩旧日志
  },
  "storage-driver": "overlay2"
}
```

**效果：** 每个容器最多占用 300MB 日志空间（3个文件 × 100MB）

### 重启Docker以应用配置

```bash
sudo systemctl restart docker
docker ps  # 验证容器重启正常
```

---

## 📊 监控与日志

### 查看清理日志

```bash
# 系统缓存清理日志
tail -f /var/log/system-cache-cleanup.log

# Docker清理日志
tail -f /var/log/docker-cleanup.log

# 磁盘监控日志
tail -f /var/log/disk-usage-monitor.log
```

### 检查磁盘使用情况

```bash
# 总体磁盘使用
df -h /

# Docker磁盘使用
docker system df

# 大文件/目录排名
du -sh /root/* | sort -hr | head -10
```

---

## 🎯 预期效果

### 每日自动清理预期回收空间
- npm缓存：~100-500MB
- Yarn缓存：自动重建时才占用
- Python缓存：~10-50MB
- APT缓存：~10-50MB
- 系统日志：~20-100MB

### Docker日志控制
- **之前：** happy-server日志达到 2.2GB
- **现在：** 单容器日志上限 300MB
- **节省：** 长期避免日志无限增长

### 监控警报
- **85%** - 发送警告（黄色警报）
- **90%** - 发送严重警告（红色警报）
- **95%+** - 立即需要人工干预

---

## 🔧 故障排查

### 如果清理脚本失败

```bash
# 检查脚本权限
ls -l /root/bin/*.sh

# 赋予执行权限
chmod +x /root/bin/*.sh

# 手动运行查看错误
/root/bin/system-cache-cleanup.sh
```

### 如果监控未发送警告

```bash
# 检查cron服务状态
systemctl status cron

# 重启cron服务
systemctl restart cron

# 查看cron日志
grep CRON /var/log/syslog | tail -20
```

### 如果Docker日志仍然很大

```bash
# 检查当前日志大小
du -sh /var/lib/docker/containers/*/

# 手动截断现有日志
truncate -s 100M /var/lib/docker/containers/*/*-json.log

# 验证配置已应用
docker inspect <container_name> | grep -A5 LogConfig
```

---

## 📈 进一步优化建议

### 可选的第2层清理（需手动确认）

1. **清理Claude项目缓存** (2.3GB)
   ```bash
   rm -rf /root/.claude/projects/*
   ```
   - 影响：Claude Code需要重新索引项目（5-10分钟/项目）

2. **清理Claude debug归档** (400MB)
   ```bash
   rm -rf /root/.claude/debug/archive-*
   ```
   - 影响：丢失旧调试历史

3. **检查重复目录**
   ```bash
   # 对比两个application_assistant目录
   diff -r /root/application_assistant /root/application-assistant

   # 删除旧版本（假设application-assistant是新的）
   rm -rf /root/application_assistant
   ```

### 长期维护建议

1. **定期审查项目**
   - 每月检查 `/root` 下的项目
   - 归档或删除不再使用的项目

2. **监控Docker镜像**
   ```bash
   # 查看未使用的镜像
   docker images --filter "dangling=true"

   # 手动清理（谨慎！）
   docker image prune -a
   ```

3. **考虑外部存储**
   - 大型数据集移至对象存储（如S3）
   - 使用Git LFS管理大文件

---

## 📞 快速命令参考

```bash
# 立即清理缓存
/root/bin/system-cache-cleanup.sh

# 检查磁盘状态
df -h /

# 检查Docker使用
docker system df

# 查看最大文件
du -sh /root/* | sort -hr | head -10

# 查看清理日志
tail -f /var/log/system-cache-cleanup.log

# 强制运行监控
/root/bin/disk-usage-monitor.sh

# 查看定时任务
crontab -l
```

---

## ✨ 总结

**已实现：**
- ✅ 第1层清理完成，释放4GB空间
- ✅ 自动化每日清理（凌晨3点）
- ✅ 自动化每周Docker清理（周日凌晨4点）
- ✅ Docker日志轮转配置（单容器300MB上限）
- ✅ 每6小时磁盘监控
- ✅ 所有Docker容器正常运行

**当前状态：**
- 磁盘使用率：89%（从99%改善）
- 可用空间：4.2GB（从670MB改善）
- 系统稳定性：良好

**维护成本：**
- 零人工干预（完全自动化）
- 监控会在需要时发出警告

---

*配置完成时间：2026-02-15 06:05*
*下次自动清理：每天凌晨3点*
*下次Docker清理：每周日凌晨4点*
