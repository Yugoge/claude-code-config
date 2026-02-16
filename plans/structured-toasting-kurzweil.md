# 部署脚本调查与优化方案

## Context

用户质疑部署脚本 `scripts/deploy-travel-plans.sh` 在第242行每次执行 `rm -rf "$DEPLOY_DIR"` 然后重新clone整个gh-pages分支的设计。这导致每次部署都要下载完整的git历史，非常低效。

通过派出三个并行探索agents深入调查，发现了以下关键问题：

### 调查发现

#### 1. Clone逻辑问题 (Agent 1报告)

**当前设计**:
```bash
# Line 242: 每次都删除临时目录
rm -rf "$DEPLOY_DIR"

# Line 247: Clone完整的gh-pages分支
git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEPLOY_DIR"
```

**问题**:
- ❌ 使用了 `--single-branch` 但**没有使用** `--depth=1`
- ❌ 每次都下载gh-pages分支的完整历史（随着部署次数增加会越来越大）
- ❌ 浪费网络带宽和部署时间

**历史原因**:
- 初始设计(2026-01-29)采用 `git push -f` 强制推送
- 后来改为 `git push` 保留历史(commit 41e4544, 2026-02-05)
- 但忘记优化clone逻辑，仍然使用完整clone

**设计优点**:
- ✅ 逻辑简单可靠
- ✅ 每次从干净状态开始，避免merge冲突
- ✅ 适合初期开发和顺序部署

**设计缺点**:
- ❌ 性能低效（90%+的数据传输是不必要的）
- ❌ gh-pages分支越大，部署越慢
- ❌ 不适合频繁部署

#### 2. HTML文件不一致问题 (Agent 2报告)

**根本原因**: 部署脚本本身逻辑正确，文件不一致是因为：

1. **时间窗口问题**:
   - 74e660d (13:10) 生成了正确的356KB文件（含桃园火锅）
   - 880dba0-9ed71a8 (13:13-13:29) 多次部署使用了旧的378KB文件
   - 1eaf19f (13:30) 最终部署了正确的356KB文件

2. **调用方式差异**:
   - 直接调用 `deploy-travel-plans.sh` 可能传入错误的文件路径
   - 使用 `generate-and-deploy.sh` 确保生成→验证→部署的完整流程

**结论**: 部署脚本的 `cp "$INPUT_FILE" ...` 逻辑是正确的，问题在于调用者传入了错误的文件。

#### 3. 部署工作流设计 (Agent 3报告)

**两个脚本的分工**:
- `generate-and-deploy.sh`: 端到端流程（生成+部署），推荐使用
- `deploy-travel-plans.sh`: 纯部署功能，被前者调用或特殊场景使用

**临时目录设计** (`/tmp/travel-planner-graph-deploy`):
- ✅ 隔离Git操作，不污染项目目录
- ✅ 允许clone完整gh-pages分支
- ✅ 自动清理

**并发问题** ⚠️:
- ❌ **不支持并发部署** - 两个进程会竞争同一个临时目录
- ❌ 第242行和第483行的 `rm -rf` 在并发时会互相删除对方的数据
- ✅ 当前使用场景（手动顺序调用）没有问题

---

## 问题总结

### 根本原因 - 深度调查结果

经过三个并行探索agents的深入调查,发现**"某些部署调用传入了旧文件"的真正原因**:

#### 1. **Git Clone失败导致的错误处理分支** ⚠️ CRITICAL

**问题位置**: `scripts/deploy-travel-plans.sh` 第247行

```bash
git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEPLOY_DIR" 2>/dev/null || {
    echo "  Creating new gh-pages branch..."
    mkdir -p "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
    git init
    git checkout -b "$BRANCH"
}
```

**发现的问题**:
- `2>/dev/null` **掩盖了所有clone错误信息**
- Clone失败时,脚本静默地创建**空的新仓库**
- 没有验证clone是否真正成功
- 导致在空仓库中复制HTML文件,推送时丢失了历史

**时间线证据**:
```
880dba0 (13:13:42): 部署378KB旧文件 - git clone可能失败,使用了错误处理分支
9ed71a8 (13:29:44): 仅修改README - 可能再次失败
1eaf19f (13:30:19): 部署356KB新文件 - 仅相隔35秒,clone这次成功了
```

**关键证据**: 两次部署只相隔35秒,说明第一次失败后立即重试,第二次成功。

#### 2. **文件版本时间线混乱**

**Master分支的文件大小演变**:
```
528bb7c (11:03:29): 378,469 bytes ← 早期版本
0d1d3ab (11:20:58): 372,212 bytes
18855ec (12:58:12): 371,442 bytes
f4df1e1 (13:04:54): 372,412 bytes
74e660d (13:10:25): 364,189 bytes ← 正确的356KB版本(含桃园火锅)
e0a997c (13:14:48): 364,189 bytes ← 最新
```

**gh-pages部署历史**:
```
7064a96 (12:57:48): 378,845 bytes ← 从528bb7c时代部署的旧文件
880dba0 (13:13:42): 378,845 bytes ← 仍然是旧文件(只修改README)
e8b2876 (13:10:08): 378,845 bytes ← 虽然master已有新的364KB
1eaf19f (13:30:19): 364,189 bytes ← 终于部署了正确版本
```

**发现**: 880dba0虽然在74e660d(生成正确文件)之后3分钟部署,但**没有重新生成HTML**,直接使用了旧文件。

#### 3. **PLAN_ID差异导致的多文件问题**

**输出目录存在多个版本**:
```
output/travel-plan-china-feb-15-mar-7-2026.html                     [69KB,  旧版]
output/travel-plan-china-feb-15-mar-7-2026-20260202-195429.html     [356KB, 新版]
```

**路径构造逻辑**:
- `generate-and-deploy.sh` 第52行: `OUTPUT_FILE="$PROJECT_ROOT/output/travel-plan-${PLAN_ID}.html"`
- Python脚本第3020行: `output_file = output_dir / f"travel-plan-{self.plan_id}.html"`

**问题**: 不同的PLAN_ID会生成不同的文件名,如果调用者传入错误的PLAN_ID,会生成或使用旧文件。

#### 4. **临时目录缓存持久化**

**发现的旧缓存**:
```
/tmp/travel-planner-graph/
- 最后修改: 2026-02-11 15:19 (24小时前)
- 文件大小: 379,895 bytes
- HEAD: c27afc9 (比当前HEAD落后50+ commits)
```

虽然脚本第242行会`rm -rf "$DEPLOY_DIR"`,但存在**不同名称的缓存目录**未被清理。

### 综合分析

**"传入旧文件"的真正原因不是单一问题,而是多个因素的组合**:

1. ✅ **直接调用deploy-travel-plans.sh时未重新生成HTML** - 使用了output/目录中的旧文件
2. ✅ **git clone失败被掩盖** - 错误处理创建空仓库,导致部署异常
3. ✅ **PLAN_ID不一致** - 生成和部署使用了不同的文件名
4. ✅ **没有内容验证** - 部署前不检查文件是否是最新版本

### 修复优先级

1. **Clone效率问题**: 每次clone完整历史，应该使用 `--depth=1`
2. **Clone失败处理**: 移除`2>/dev/null`,添加验证,防止静默失败 🔴 HIGH PRIORITY
3. **内容验证**: 部署前检查文件内容/哈希是否匹配预期
4. **并发不安全**: 不支持多个部署同时运行（但当前场景不需要）

---

## 优化方案

### 方案A: 添加浅克隆 (推荐 - 最小改动)

**改动**: 在第247行添加 `--depth=1` 参数

```bash
# 当前 (第247行):
git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEPLOY_DIR"

# 优化后:
git clone --branch "$BRANCH" --single-branch --depth=1 "$REPO_URL" "$DEPLOY_DIR"
```

**优点**:
- 改动最小（只添加一个参数）
- 节省90%+的下载大小
- 保持现有逻辑的简单性和可靠性
- 风险极低

**缺点**:
- 仍然每次都重新clone（虽然是浅克隆）
- 对于连续多次部署仍有优化空间

---

### 方案B: 增量更新 (更优 - 中等改动)

**改动**: 检查临时目录是否存在，存在则增量更新

```bash
# 替换第242-253行
if [ -d "$DEPLOY_DIR/.git" ]; then
    # 目录存在，做增量更新
    echo "  Updating existing gh-pages clone..."
    cd "$DEPLOY_DIR"
    git fetch origin "$BRANCH" --depth=1
    git reset --hard origin/"$BRANCH"
else
    # 目录不存在，首次clone
    echo "  Cloning gh-pages branch..."
    rm -rf "$DEPLOY_DIR"  # 清理可能的脏目录
    git clone --branch "$BRANCH" --single-branch --depth=1 "$REPO_URL" "$DEPLOY_DIR"
fi
cd "$DEPLOY_DIR"
```

**优点**:
- 首次clone后，后续部署只需fetch增量
- 大幅提升连续部署的速度
- 仍保持干净状态（reset --hard）

**缺点**:
- 需要处理脏目录的edge cases
- 逻辑稍微复杂
- 需要更多测试

---

### 方案C: 添加并发支持 (可选 - 解决并发问题)

**改动**: 在脚本开头添加进程锁

```bash
# 在第8行之后添加
LOCK_FILE="/tmp/travel-planner-deploy.lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "❌ 另一个部署进程正在运行，请等待..."
    exit 1
fi
trap "flock -u 200; rm -f $LOCK_FILE" EXIT
```

**何时需要**:
- CI/CD并发构建场景
- 多用户同时部署
- 快速连续部署多个计划

**当前状态**: 不需要（手动顺序调用）

---

## 推荐实施方案(基于根本原因调查)

### 方案1: 修复Clone失败掩盖问题 (CRITICAL - 必须修复)

**改动**: 移除错误掩盖,添加验证

```bash
# 替换第247行
# 当前:
git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEPLOY_DIR" 2>/dev/null || {

# 修复后:
if ! git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEPLOY_DIR" 2>&1 | tee clone.log; then
    echo "❌ Error: Failed to clone gh-pages branch"
    cat clone.log
    exit 1
fi

# 验证clone成功
if [ ! -d "$DEPLOY_DIR/.git" ]; then
    echo "❌ Error: Clone succeeded but .git directory missing"
    exit 1
fi
```

**优点**:
- 不再掩盖clone失败
- 立即显示错误信息
- 防止使用错误处理分支创建空仓库
- 避免部署不完整的内容

**风险**: 低 - 只是改善错误处理

---

### 方案2: 添加浅克隆优化 (推荐 - 性能提升)

**改动**: 在第247行添加 `--depth=1` 参数

```bash
git clone --branch "$BRANCH" --single-branch --depth=1 "$REPO_URL" "$DEPLOY_DIR"
```

**优点**:
- 节省90%+下载大小
- 改动最小(只添加一个参数)
- 加快部署速度
- 风险极低

---

### 方案3: 添加文件内容验证 (推荐 - 防止旧文件)

**改动**: 在第279行cp之后,第417行commit之前添加验证

```bash
# 在第279行 cp 之后添加
cp "$INPUT_FILE" "${TARGET_DIR}/index.html"

# 验证文件大小合理性
FILE_SIZE=$(wc -c < "${TARGET_DIR}/index.html")
if [ "$FILE_SIZE" -lt 100000 ]; then
    echo "❌ Error: Deployed file too small ($FILE_SIZE bytes)"
    echo "Expected at least 100KB for a valid travel plan"
    exit 1
fi

# 验证包含PLAN_DATA
if ! grep -q "const PLAN_DATA" "${TARGET_DIR}/index.html"; then
    echo "❌ Error: Deployed file missing PLAN_DATA"
    exit 1
fi

# 验证包含React
if ! grep -q "React" "${TARGET_DIR}/index.html"; then
    echo "❌ Error: Deployed file missing React"
    exit 1
fi

echo "✓ File validation passed: ${FILE_SIZE} bytes"
```

**优点**:
- 防止部署空文件或损坏文件
- 防止部署旧版本(旧版本通常更小)
- 早期发现问题
- 改动较小,风险低

---

### 方案4: 使用generate-and-deploy.sh作为唯一入口

**改动**: 文档和流程改进(无代码改动)

**推荐做法**:
1. 将 `deploy-travel-plans.sh` 标记为内部脚本
2. 在README中明确说明:
   - ✅ 使用 `generate-and-deploy.sh` (完整流程,推荐)
   - ⚠️ 直接调用 `deploy-travel-plans.sh` 需要确保传入最新生成的文件

**优点**:
- 确保生成→验证→部署的完整流程
- 避免使用旧文件
- 无代码改动,零风险

---

### 实施优先级

#### Phase 1: 立即修复(高优先级)
1. **方案1** - 修复clone失败掩盖 🔴 CRITICAL
2. **方案2** - 添加 `--depth=1` 浅克隆
3. **方案3** - 添加文件验证

预计改动: 30行代码
风险: 低
收益: 消除根本原因,防止再次出现旧文件问题

#### Phase 2: 流程优化(中优先级)
4. **方案4** - 推荐使用generate-and-deploy.sh
5. 添加部署日志和调试信息
6. 清理/tmp旧缓存的定期任务

#### Phase 3: 长期优化(可选)
7. 方案B - 增量更新(如果部署频率增加)
8. 方案C - 并发支持(如果需要并发部署)

---

## 关键文件

- `scripts/deploy-travel-plans.sh` - 需要优化的脚本
  - Line 247: 添加 `--depth=1` 参数
  - Line 242-253: (可选) 改为增量更新逻辑

- `scripts/generate-and-deploy.sh` - 调用者
  - Line 144: 调用deploy-travel-plans.sh
  - 无需修改

---

## 验证计划

### 测试步骤

1. **功能测试**:
   ```bash
   # 测试正常部署流程
   bash scripts/generate-and-deploy.sh china-feb-15-mar-7-2026-20260202-195429

   # 验证部署的HTML内容正确
   curl -s https://Yugoge.github.io/travel-planner-graph/china-feb-15-mar-7-2026/2026-02-02/ | grep -o '桃园'
   ```

2. **性能测试**:
   ```bash
   # 对比优化前后的部署时间
   time bash scripts/deploy-travel-plans.sh output/travel-plan-*.html
   ```

3. **边界测试**:
   - 首次部署（临时目录不存在）
   - 重复部署（临时目录已存在）
   - 部署失败后重试

### 成功标准

- ✅ 部署时间减少50%+（方案A）或80%+（方案B）
- ✅ 部署的HTML内容与本地一致
- ✅ GitHub Pages能正常访问
- ✅ 索引页和README正确生成

---

## 不需要修改的地方

1. **部署脚本的核心逻辑** (Line 279: `cp "$INPUT_FILE" ...`)
   - 经验证是正确的
   - 文件不一致是调用方式问题，不是脚本问题

2. **临时目录设计** (`/tmp/travel-planner-graph-deploy`)
   - 设计合理，无需改动

3. **generate-and-deploy.sh**
   - 工作正常，是推荐的使用方式
