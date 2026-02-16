# System Storage Cleanup Plan

## Context

The system shows **99% disk usage** (36G/38G used, only 670MB free). This is a critical situation that could cause system instability, prevent updates, and block new file creation. The user requested a thorough investigation to determine what can and cannot be safely deleted before proceeding with cleanup.

## Detailed Investigation Results

### 🔍 Safe to Delete (High Confidence)

#### 1. **Yarn Cache (3.1GB)** ✅ SAFE
- Location: `/usr/local/share/.cache/yarn`
- Contains: 1308 cached package versions
- **Impact**: None - can be regenerated on demand
- **Recoverable**: 3.1GB

#### 2. **Old Linux Kernels (Estimated 200-300MB)** ✅ SAFE
- Found 10 old kernel versions (6.8.0-71 through 6.8.0-94)
- Currently running: 6.8.0-88 (not the latest installed)
- Status: "rc" (removed but config remains)
- **Impact**: None - keeping only current kernel is standard
- **Recoverable**: ~200-300MB

#### 3. **Claude Debug Files (507MB)** ✅ SAFE
- Location: `/root/.claude/debug/`
- Contains: Old debug logs and archives
- Notable: 122MB in archive-2025-12, 14MB in archive-2025-11
- **Impact**: None - old debugging sessions
- **Recoverable**: 300-400MB (keep recent 100MB)

#### 4. **Python Cache Files (.pyc, __pycache__)** ✅ SAFE
- Found: 265,749 cache files across all projects
- **Impact**: None - Python auto-regenerates on import
- **Recoverable**: 50-100MB estimated

#### 5. **System Logs > 7 days old (150MB)** ✅ SAFE
- journal: 104MB (can vacuum to 7 days)
- syslog rotations: 56MB
- btmp (failed logins): 29MB
- **Impact**: Lose old log history only
- **Recoverable**: ~150MB

#### 6. **Claude Config Backups** ✅ SAFE
- Location: `/root/.claude.json.backup.*`
- Found: 5+ backup files, 24KB each
- **Impact**: Minimal - keep latest 2-3
- **Recoverable**: Negligible (<1MB)

### ⚠️ Needs Analysis (Medium Confidence)

#### 7. **node_modules in Projects (1.43GB total)**
- happy: 1.4GB ⚠️ **ACTIVE** (last commit Jan 22, Happy CLI daemon running)
- knowledge-system: 13MB ✅ (last commit Feb 8, recent)
- travel-planner: 14MB ⚠️ **VERY ACTIVE** (last commit today Feb 13)
- excel-analyzer: 7.8MB ❓ (last commit Jan 10, possibly inactive)

**Recommendation**: Only safe to delete excel-analyzer node_modules (~8MB)

#### 8. **Python venv in Projects (2.2GB total)**
- multi-asset-portfolio: 548MB ⚠️ (last commit Feb 6, recent)
- knowledge-system: 466MB ⚠️ (last commit Feb 8, recent)
- application_assistant: 411MB ❓ (last commit Jan 19, older)
- application-assistant (duplicate): 334MB ⚠️ (last commit Feb 10, active)
- budget-management: 283MB ⚠️ (last commit Feb 8, recent)
- travel-planner: 179MB ⚠️ **VERY ACTIVE** (last commit today)

**Recommendation**: All projects show recent activity. **DO NOT DELETE** without user confirmation.

#### 9. **Claude Project Caches (2.3GB)** ⚠️ IMPORTANT
- Location: `/root/.claude/projects/`
- Breakdown:
  - multi-asset-portfolio: 974MB
  - travel-planner: 636MB
  - application-assistant: 325MB
  - budget-management: 202MB
  - knowledge-system: 104MB

**Impact**: Deleting forces Claude to re-index projects (slow, but safe)
**Recoverable**: 2.3GB
**Recommendation**: User decision - impacts Claude Code performance

### ❌ Do NOT Delete (High Risk)

#### 10. **Docker Images (2.5GB)** ❌ MIXED
- All 5 containers are **RUNNING**:
  - happy-server: Up 9 days (1.9GB image) ⚠️ **ACTIVE**
  - postgres:15-alpine: Up 4 minutes (273MB) ⚠️ **ACTIVE**
  - cloudflared: Up 2 months (61.4MB) ⚠️ **ACTIVE**
  - redis:7-alpine: Up 2 months (41.4MB) ⚠️ **ACTIVE**
  - minio: Up 2 months (175MB) ⚠️ **ACTIVE**

**Docker reports "100% reclaimable" BUT all containers are actively running!**
**Recommendation**: **DO NOT** run `docker system prune -a` - it will break running services

#### 11. **Docker Container Logs (2.2GB)** ⚠️ RISKY
- happy-server container: 2.2GB logs
- Shows active recent logs (last 30 seconds ago)
- **Impact**: Truncating may lose debugging info
- **Recommendation**: User decision - can truncate but keep recent logs

#### 12. **Docker Volumes (1.5GB)** ❌ CRITICAL
- happy-server_postgres_data: 1.4GB ❌ **PRODUCTION DATABASE**
- happy-server_postgres-data: 64MB (duplicate/old?)
- minio-data: 88KB + 96KB
- redis-data: 20KB
- happy-data: 4KB

**CRITICAL**: The 1.4GB postgres volume contains production data!
**Recommendation**: **NEVER DELETE** - this is your application's database

#### 13. **Google Chrome (382MB)** ❌ IN USE
- Installed and functional (v143.0.7499.109)
- Used by Playwright MCP server (running process detected)
- **Recommendation**: **DO NOT UNINSTALL** - actively used

#### 14. **Active Projects** ❌ ACTIVE
- application-assistant: Last commit Feb 10 (2 days ago)
- travel-planner: Last commit TODAY (Feb 13)
- budget-management: Last commit Feb 8
- knowledge-system: Last commit Feb 8
- multi-asset-portfolio: Last commit Feb 6

**All projects show recent commits - DO NOT archive without permission**

### 💡 Duplicate Detection

#### 15. **Duplicate application_assistant** ⚠️
- `/root/application_assistant`: 370MB (no venv shown, last commit Jan 19)
- `/root/application-assistant`: 520MB (has venv, last commit Feb 10)

**One appears to be a duplicate/old copy**
**Recommendation**: User should verify which is current

## Cleanup Strategy - Safe Actions Only

### ✅ Tier 1: Ultra-Safe Cleanup (~3.6GB - No Risk)

**These actions have ZERO impact on functionality:**

1. **Clear Yarn Cache (3.1GB)**
   ```bash
   rm -rf /usr/local/share/.cache/yarn
   ```
   - Regenerates automatically when needed
   - No downtime, no data loss

2. **Remove Old Kernels (200-300MB)**
   ```bash
   # List kernels first (verify)
   dpkg --list | grep linux-image

   # Remove old kernels (keeps current 6.8.0-88)
   apt-get remove --purge linux-image-6.8.0-71-generic
   apt-get remove --purge linux-image-6.8.0-79-generic
   apt-get remove --purge linux-image-6.8.0-83-generic
   apt-get remove --purge linux-image-6.8.0-84-generic
   apt-get remove --purge linux-image-6.8.0-85-generic
   apt-get remove --purge linux-image-6.8.0-86-generic
   apt-get remove --purge linux-image-6.8.0-87-generic
   apt-get remove --purge linux-image-6.8.0-90-generic
   apt-get remove --purge linux-image-6.8.0-94-generic
   apt-get remove --purge linux-image-6.8.0-100-generic

   apt-get autoremove -y
   ```

3. **Clean System Logs (150MB)**
   ```bash
   journalctl --vacuum-time=7d
   find /var/log -type f -name "*.1" -delete
   find /var/log -type f -name "*.gz" -mtime +7 -delete
   > /var/log/btmp  # Clear failed login log
   ```

4. **Clear Python Cache (50-100MB)**
   ```bash
   find /root -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
   find /root -type f -name "*.pyc" -delete 2>/dev/null
   ```

5. **Clean APT Cache (100-200MB)**
   ```bash
   apt-get clean
   ```

**Total Recovery: ~3.6-3.8GB → Brings disk usage to ~93%**

---

### ⚠️ Tier 2: Low-Risk Cleanup (~2.8GB - User Decision)

**These require your confirmation:**

6. **Clean Claude Project Cache (2.3GB)**
   - Impact: Claude Code will re-index projects (5-10 min per project)
   - Benefit: 2.3GB space recovered
   - Risk: Performance degradation until re-indexed

   ```bash
   # OPTIONAL - Requires user approval
   rm -rf /root/.claude/projects/*
   ```

7. **Clean Old Claude Debug Logs (400MB)**
   - Impact: Lose old debugging history (archives from Nov-Dec 2025)
   - Benefit: 400MB space

   ```bash
   # OPTIONAL - Requires user approval
   rm -rf /root/.claude/debug/archive-*
   find /root/.claude/debug -name "*.txt" -mtime +30 -delete
   ```

8. **Truncate Docker Container Logs (2.2GB)**
   - Impact: Lose happy-server historical logs
   - Benefit: 2.2GB space
   - Risk: May lose debugging information

   ```bash
   # OPTIONAL - Requires user approval
   truncate -s 100M /var/lib/docker/containers/ca96cc2d92466b5cde763b9449758d06aedbe74fd2f4abf3f185491a5999cf39/*-json.log
   ```

**Potential Total: Up to 4.9GB additional (requires user decisions)**

---

### ❓ Tier 3: Needs Investigation (User Action Required)

9. **Duplicate application_assistant Directory**
   - `/root/application_assistant` (370MB, older)
   - `/root/application-assistant` (520MB, newer)
   - **Action Required**: User must verify which to keep

10. **Unused Project Dependencies**
    - excel-analyzer node_modules: 7.8MB (possibly inactive)
    - **Action Required**: User confirms if project is still needed

---

### ❌ DO NOT TOUCH - Critical Systems

**NEVER delete or modify these:**

- Docker containers (all 5 are running)
- Docker images (in active use by running containers)
- Docker volumes (contains production postgres database - 1.4GB)
- Google Chrome (used by Playwright MCP)
- Active project directories (all show recent commits)
- Project venv folders (all projects are active)
- node_modules in happy/knowledge-system/travel-planner (active projects)

---

## Recommended Action Plan

### 🚀 Immediate Action (Safe - Execute Now)
**Run Tier 1 cleanup to recover 3.6GB:**
1. Clear yarn cache
2. Remove old kernels
3. Clean system logs
4. Clear Python cache
5. Clean APT cache

**Result**: Disk usage drops from 99% to ~93% ✅

### 🤔 User Decisions Required

After Tier 1, you'll have breathing room. Then decide:

**Question 1**: Clear Claude project cache? (2.3GB)
- Pro: Significant space savings
- Con: Slower Claude Code performance until re-indexed

**Question 2**: Truncate Docker logs? (2.2GB)
- Pro: Major space savings
- Con: Lose debugging history

**Question 3**: Which `application_assistant` to keep?
- Check both directories to identify the current version

### 📊 Expected Final State

- **After Tier 1 only**: ~93% disk usage (~2.7GB free)
- **After Tier 1+2**: ~82% disk usage (~6.9GB free)
- **With duplicate cleanup**: ~80% disk usage (~7.6GB free)

---

## Verification Commands

```bash
# Before cleanup
df -h /

# After each tier
df -h /
docker ps -a
docker system df

# Verify services still running
systemctl status docker
docker ps
```

## Prevention Recommendations

1. **Set up automatic cleanup**:
   ```bash
   # Add to crontab
   0 3 * * 0 journalctl --vacuum-time=7d
   0 3 * * 0 apt-get clean
   ```

2. **Monitor disk usage**:
   ```bash
   # Add disk usage alert
   echo "df -h / | awk 'NR==2 {if (\$5+0 > 90) print \"WARNING: Disk usage > 90%\"}'" >> ~/.bashrc
   ```

3. **Docker log rotation**:
   ```json
   # Add to /etc/docker/daemon.json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "100m",
       "max-file": "3"
     }
   }
   ```
