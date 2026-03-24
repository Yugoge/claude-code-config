# Plan: 机筛 / 手筛 分离

## Context

当前 `stock-screener.py` 跑完后自动写入 `latest.json`，机器筛选结果和人工确认名单混在同一个文件。用户希望：
- **机筛**：screener 自动保存，供参考
- **手筛**：逐只股票明确 include/skip，最终名单才进入手筛
- **`/equity-research` 默认读手筛**，机筛作为备用

中途保存退出时，未看到的股票**全部丢弃**（只有明确加入的进手筛名单）。

---

## 文件改动（4个文件）

### 1. `scripts/stock-screener.py`

**Line ~1283**: 改一行

```python
# 改前
latest_path = Path("data/screens/latest.json")

# 改后
latest_path = Path("data/screens/latest_machine.json")
```

同步更新 print 输出（line ~1335）：
```python
# 改前
print(f"✅ Merged into latest.json: ...")
# 改后
print(f"✅ Merged into latest_machine.json: ...")
```

---

### 2. `scripts/shortlist-manager.py`

**Line ~41**: 增加机筛路径常量

```python
SHORTLIST_PATH = PROJECT_ROOT / "data" / "screens" / "latest.json"         # 手筛
MACHINE_SHORTLIST_PATH = PROJECT_ROOT / "data" / "screens" / "latest_machine.json"  # 机筛（新增）
```

其余逻辑不变，`latest.json` 继续作为手筛标准路径。

---

### 3. `.claude/commands/equity-pick.md`

**Step 5 persuasion loop options**（当前 3 个选项 → 改为 4 个）：

```
# 改前（每只股票后）
<option>Continue to next stock</option>
<option>Tell me more about {TICKER}</option>
<option>Enough, save shortlist and exit</option>

# 改后
<option>加入手筛名单，继续下一只</option>
<option>跳过这只，继续下一只</option>
<option>Tell me more about {TICKER}</option>
<option>保存手筛名单，退出（已加入 N 只）</option>
```

**Step 5 tracking logic**（在 Implementation 伪代码中）：

```bash
# 初始化手筛列表
MANUAL_SHORTLIST=()

# 每只股票用户选择后：
# 如果选 "加入" → MANUAL_SHORTLIST+=("$TICKER")
# 如果选 "跳过" → 什么都不做
# 如果选 "保存退出" → 跳出循环，只保存 MANUAL_SHORTLIST
# 如果所有股票看完 → 跳出循环，提示加入了多少只
```

**Step 8 save logic**（改为保存手筛，不再用机筛 JSON）：

```bash
# 改前
source venv/bin/activate && python scripts/shortlist-manager.py save --input "$LATEST_JSON"

# 改后：从 latest_machine.json 中提取手筛股票写入 latest.json
source venv/bin/activate && python scripts/shortlist-manager.py save-manual \
  --tickers "${MANUAL_SHORTLIST[@]}" \
  --source "$LATEST_MACHINE_JSON"
```

**新增 `save-manual` 命令** → 见 shortlist-manager.py 改动（下面补充）。

**Step 0 描述更新**：在说明里注明机筛/手筛文件路径区别。

**最终确认消息更新**：
```
机筛结果（全部通过算法过滤）: data/screens/latest_machine.json ({M} 只)
手筛名单（你明确加入）:      data/screens/latest.json ({N} 只)
/equity-research 默认使用手筛名单
```

---

### 4. `scripts/shortlist-manager.py`（续）

**新增 `save-manual` 子命令**（约 40 行）：

```python
elif args.command == 'save-manual':
    # 从 latest_machine.json 中提取指定 ticker 的完整数据
    # 写入 latest.json（手筛文件）
    manager.save_manual(tickers=args.tickers, source_path=args.source)
```

`save_manual` 方法逻辑：
1. 读取 `source_path`（机筛 JSON）
2. 过滤只保留 `args.tickers` 中的股票
3. 写入 `SHORTLIST_PATH`（`latest.json`）
4. 标记 `source: "manual"` 在 metadata 中

---

### 5. `.claude/commands/equity-research.md`

**Step 1 shortlist 读取逻辑**（改为双路径检测）：

```bash
# 改前：只找 latest.json
python scripts/shortlist-manager.py load

# 改后：先找手筛，没有则 fallback 机筛
if [ -f "data/screens/latest.json" ]; then
  echo "✅ 使用手筛名单 (data/screens/latest.json)"
  python scripts/shortlist-manager.py load
elif [ -f "data/screens/latest_machine.json" ]; then
  echo "⚠️  未找到手筛名单，使用机筛名单 (data/screens/latest_machine.json)"
  # 提示用户是否继续用机筛
  <option>继续用机筛名单做 equity research</option>
  <option>先回去跑 /equity-pick 生成手筛名单</option>
else
  # 没有任何名单
  <option>运行 /equity-pick 生成名单</option>
  <option>直接输入 ticker</option>
fi
```

---

## 验证方式

1. 跑 `stock-screener.py` → 确认写入 `latest_machine.json`，不写 `latest.json`
2. 跑 `/equity-pick` persuasion loop，加入2只、跳过1只 → 确认 `latest.json` 只有2只
3. 跑 `/equity-research`（不带 ticker）→ 确认读 `latest.json`（手筛）
4. 删除 `latest.json` 后跑 `/equity-research` → 确认 fallback 到 `latest_machine.json` 并提示

---

## 文件清单

| 文件 | 改动量 | 关键变化 |
|------|--------|---------|
| `scripts/stock-screener.py` | 2行 | latest.json → latest_machine.json |
| `scripts/shortlist-manager.py` | ~50行 | 新增常量 + save-manual 命令 |
| `.claude/commands/equity-pick.md` | ~30行 | 逐只 include/skip + 手筛保存逻辑 |
| `.claude/commands/equity-research.md` | ~15行 | 双路径检测 + fallback |
