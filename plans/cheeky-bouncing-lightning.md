# Plan: 实现Apple Calendar风格的自适应字体缩放

## Context

### 新需求
用户希望改用**Apple Calendar的自适应渲染方式**，而不是之前计划的三级切换模式：

**Apple Calendar风格逻辑：**
1. **正常显示**：高度充足时，使用标准字体大小
2. **字体缩小**：当高度不足一行时，**逐渐缩小字体**以适应block大小
3. **最小限制**：当时长小于某个阈值（如10分钟）时，block高度不再缩小，保持固定大小

**关键差异：**
- ❌ 不要"三级切换"（两行→一行→左移）
- ✅ 使用**渐进式字体缩放**
- ✅ block内容始终显示，不移到左边
- ✅ 极短活动保持最小可点击尺寸

### 当前实现分析

**现状（通过Explore agent发现）：**

1. **字体大小固定**：
   - 标题：sm ? '12px' : '14px'
   - 时间：'11px'
   - 详情：'11px'
   - **不会根据entry高度动态调整**

2. **高度计算**：
   ```javascript
   const hH = sm ? 68 : 80;  // 1小时的像素高度
   const rawHgt = (s, e) => top(e) - top(s);  // 时间段对应的像素
   const hgt = (s, e) => Math.max(rawHgt(s, e), 8);  // 最小8px
   ```

   **10分钟对应高度：**
   - 小屏：(10/60) * 68 ≈ **11.33px**
   - 大屏：(10/60) * 80 ≈ **13.33px**

3. **三级模式（当前实现，需要移除）：**
   ```javascript
   const twoRowsMode = entryH >= 52;           // >= 52px
   const oneRowMode = entryH >= 36 && entryH < 52;  // 36-51px
   const moveToLeft = entryH < 36;              // < 36px
   ```

### Apple Calendar参考逻辑

**目标行为（类似Apple Calendar）：**

```
正常情况（如2小时活动 ≈ 136-160px）：
  ┌─────────────────┐
  │ 🎨 故宫博物院   │ ← 标准字体 14px
  │ 09:00 - 12:00   │ ← 标准字体 11px
  │ ⏱ 3小时 💰¥60  │ ← 详情
  └─────────────────┘

中等高度（如30分钟 ≈ 34-40px）：
  ┌─────────────────┐
  │ 🍜 午餐         │ ← 字体缩小到 10px
  │ 12:00-12:30     │ ← 字体缩小到 9px
  └─────────────────┘

极短活动（如10分钟 ≈ 11-13px）：
  ┌─────────────────┐
  │ 🚇 Line 1       │ ← 字体缩小到 8px，但block保持最小高度
  └─────────────────┘
```

**核心特性：**
1. **字体连续缩放**：根据可用高度平滑调整fontSize
2. **保持可读性**：字体不小于某个阈值（如8px）
3. **最小block高度**：10分钟以内的活动，高度固定在可点击尺寸（如24px）
4. **内容优先级**：优先显示标题，次要显示时间，最后显示详情

### 实现策略

**字体缩放算法：**

```javascript
// 基准字体大小
const baseFontSize = sm ? 12 : 14;  // 标题
const baseTimeFontSize = 11;        // 时间

// 计算缩放因子
const calculateFontScale = (entryH) => {
  const minHeight = 52;  // 开始缩小的阈值（两行正常显示需要的高度）

  if (entryH >= minHeight) {
    return 1.0;  // 不缩放
  }

  // 线性缩放：从52px缩小到24px（最小可点击高度）
  const minClickableHeight = 24;
  const scale = Math.max(
    (entryH - 8) / (minHeight - 8),  // 8px padding
    minClickableHeight / minHeight
  );

  return Math.max(scale, 0.57);  // 最小缩放到57%（8px字体，14px * 0.57 ≈ 8px）
};

// 应用缩放
const titleFontSize = `${baseFontSize * calculateFontScale(entryH)}px`;
const timeFontSize = `${baseTimeFontSize * calculateFontScale(entryH)}px`;
```

**最小高度限制（10分钟阈值）：**

```javascript
// 10分钟对应的原始高度
const tenMinHeight = (10/60) * hH;  // ≈ 11-13px

// 如果实际时长 < 10分钟，强制使用最小可点击高度
const hgt = (s, e) => {
  const raw = rawHgt(s, e);
  const durationMin = (raw / hH) * 60;  // 转换为分钟

  if (durationMin < 10) {
    return 24;  // 最小可点击高度
  }

  return Math.max(raw, 24);  // 其他情况也不小于24px
};
```

---

## Implementation Plan

### 目标
实现Apple Calendar风格的自适应字体缩放，让timeline entry在不同高度下平滑调整字体大小，保持内容可读性。

### 修改文件
- `/root/travel-planner/scripts/generate-html-interactive.py`（主要修改TimelineView组件，lines 2700-2950）

### 实现步骤

#### Step 1: 修改hgt函数 - 添加10分钟最小高度逻辑 (line 2719)

**当前代码（需要完全替换）：**
```javascript
const hgt = (s, e) => Math.max(rawHgt(s, e), 8);
```

**新逻辑：**
```javascript
const hgt = (s, e) => {
  const raw = rawHgt(s, e);
  const durationMin = (raw / hH) * 60;  // 转换为分钟数

  // 10分钟以内：固定最小可点击高度
  if (durationMin < 10) {
    return 24;  // 最小可点击高度（约等于两行小字体的空间）
  }

  // 10分钟以上：按实际时长，但不小于24px
  return Math.max(raw, 24);
};
```

**解释：**
- 10分钟对应 11-13px（太小无法点击）
- 强制10分钟内的活动高度为24px
- 10分钟以上的活动按实际时长显示
- 所有entry最小高度24px（可点击）

#### Step 2: 添加字体缩放计算函数 (新增，在hgt定义后)

**新增代码：**
```javascript
// 字体缩放计算（Apple Calendar风格）
const calculateFontScale = (height) => {
  const fullSizeThreshold = 52;  // 两行完整显示的高度

  if (height >= fullSizeThreshold) {
    return 1.0;  // 100% 标准字体
  }

  // 线性缩放：从52px到24px之间平滑过渡
  const minHeight = 24;
  const scale = (height - 8) / (fullSizeThreshold - 8);  // 8px留给padding

  // 最小缩放到0.57（14px * 0.57 ≈ 8px）
  return Math.max(scale, 0.57);
};
```

#### Step 3: 移除三级模式，改用统一的字体缩放渲染 (lines 2787-2930)

**移除的代码块：**
- 删除 `twoRowsMode`, `oneRowMode`, `moveToLeft` 变量定义
- 删除 `showText`, `showTime`, `showSubtext`, `showInlineTime` 变量
- 删除 `hasNarrowEntries` 检测逻辑（不再需要左侧标题预留空间）
- 删除 `moveToLeft` 条件下的左侧标题渲染
- 删除 `oneRowMode` 和 `twoRowsMode` 的分支渲染

**新的统一渲染逻辑：**
```javascript
// 计算entry的字体缩放
const fontScale = calculateFontScale(entryH);
const baseTitleSize = sm ? 12 : 14;
const baseTimeSize = 11;
const baseDetailSize = 11;

const titleFontSize = `${baseTitleSize * fontScale}px`;
const timeFontSize = `${baseTimeSize * fontScale}px`;
const detailFontSize = `${baseDetailSize * fontScale}px`;

// 内容显示阈值（基于缩放后的字体）
const showTitle = entryH >= 14;  // 至少能容纳一行标题（14px * 0.57 ≈ 8px）
const showTime = entryH >= 24;   // 至少能容纳标题+时间两行
const showDetails = entryH >= 52; // 完整高度才显示详情

return (
  <div style={{
    position: 'absolute',
    top: t,
    left: hasColumns ? `calc(10px + ${colLeft}%)` : '10px',
    width: hasColumns ? `calc(${colWidth}% - 12px)` : 'calc(100% - 20px)',
    height: entryH - 4,
    background: st.bg,
    borderLeft: `3px ${entry.optional ? 'dashed' : 'solid'} ${st.border}`,
    borderRadius: '6px',
    padding: sm ? '4px 6px' : '6px 8px',  // 更小的padding适应缩放字体
    display: 'flex',
    gap: '6px',
    alignItems: 'flex-start',
    boxShadow: isTop ? '0 4px 12px rgba(0,0,0,0.12)' : '0 1px 3px rgba(0,0,0,0.04)',
    zIndex: zIdx,
    overflow: 'hidden',
    transition: 'all .15s',
    cursor: 'pointer'
  }}
  onClick={...}
  onMouseEnter={...}
  onMouseLeave={...}>

    {/* 图片（仅完整高度显示） */}
    {entry.image && !sm && showDetails && (
      <div style={{ width: '50px', height: '50px', borderRadius: '6px', overflow: 'hidden', flexShrink: 0 }}>
        <img src={entry.image} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => e.target.style.display = 'none'} />
      </div>
    )}

    {/* 文字内容 */}
    <div style={{ flex: 1, minWidth: 0 }}>
      {/* 时间行（>=24px显示） */}
      {showTime && (
        <div style={{ fontSize: timeFontSize, color: '#b4b4b4', lineHeight: 1.2 }}>
          {entry.time.start} – {entry.time.end}
        </div>
      )}

      {/* 标题行（>=14px显示） */}
      {showTitle && (
        <div style={{
          fontSize: titleFontSize,
          fontWeight: '600',
          color: '#37352f',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          lineHeight: 1.2
        }}>
          {entry._type === 'transportation' || entry._type === 'travel' ? (
            <span>{entry.icon || '🚶'} {entry._label}{entry.duration ? ` (${entry.duration})` : ''}</span>
          ) : (
            <span>{entry.icon || '📍'} {getDisplayName(entry, lang)}</span>
          )}
          {entry.optional && showDetails && (
            <span style={{
              fontSize: `${9 * fontScale}px`,
              padding: '1px 4px',
              background: '#f5f5f3',
              borderRadius: '3px',
              color: '#9b9a97',
              marginLeft: '4px'
            }}>
              {L('optional', lang)}
            </span>
          )}
        </div>
      )}

      {/* 详情行（>=52px显示） */}
      {showDetails && (entry._type === 'transportation' ? (
        <div style={{ fontSize: detailFontSize, color: '#9b9a97', marginTop: '2px', lineHeight: 1.3 }}>
          {/* 保持现有的transportation详情渲染 */}
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: detailFontSize, color: '#9b9a97', flexWrap: 'wrap', marginTop: '2px' }}>
          {/* 保持现有的其他类型详情渲染（cost, duration, stars等） */}
        </div>
      ))}
    </div>
  </div>
);
```

#### Step 4: 移除hasNarrowEntries逻辑（不再需要）

**删除以下代码：**
```javascript
// Line 2721-2724: 删除这个检测逻辑
const hasNarrowEntries = entriesWithLayout.some(e => {
  const h = hgt(e.time.start, e.time.end);
  return h < 36;
});
```

**删除timeline track的paddingLeft：**
```javascript
// Line 2763-2769: 恢复为原始的无padding版本
<div style={{
  flex: 1,
  position: 'relative',
  borderLeft: '1px dashed #e5e4e1',
  minWidth: 0
  // 删除：paddingLeft: hasNarrowEntries ? (sm ? '80px' : '120px') : '0'
}}>
```

### 验证方案

#### 测试场景

使用现有的`data/china-feb-15-mar-7-2026-20260202-195429/timeline.json`数据：

**场景1：长活动（如故宫博物院 09:00-12:00，3小时 ≈ 204-240px）**
- 预期：标准字体（14px标题，11px时间）
- 检查：时间、标题、详情、图片全部显示
- fontScale: 1.0（无缩放）

**场景2：中等活动（如午餐 12:00-13:00，1小时 ≈ 68-80px）**
- 预期：字体略微缩小（约12px标题，10px时间）
- 检查：时间和标题显示，详情可能隐藏
- fontScale: 约0.8-0.9

**场景3：短活动（如地铁换乘 08:45-09:00，15分钟 ≈ 17-20px）**
- 预期：字体缩小到约8-9px
- 检查：只显示标题（时间可能隐藏）
- block高度: 24px（因为<10分钟）
- fontScale: 约0.57-0.6

**场景4：极短活动（如2分钟散步）**
- 预期：同场景3
- block高度: 24px（强制最小高度）
- fontScale: 0.57
- 只显示标题，字体8px

#### 验证步骤

1. **生成HTML**：
   ```bash
   bash scripts/generate-and-deploy.sh china-feb-15-mar-7-2026-20260202-195429
   ```

2. **浏览器测试**：
   - 打开生成的HTML文件
   - 切换到Timeline视图
   - 检查不同时长的活动

3. **开发者工具检查**：
   ```javascript
   // 在浏览器console中运行
   document.querySelectorAll('[style*="fontSize"]').forEach(el => {
     console.log(el.textContent, el.style.fontSize);
   });
   ```

4. **视觉验证**：
   - 字体平滑缩放（无突变）
   - 极短活动仍可点击（24px高度）
   - 无文字溢出或截断

#### 预期效果对比

| 活动时长 | 原始高度 | 实际高度 | 字体缩放 | 显示内容 |
|---------|---------|---------|---------|---------|
| 3小时 | 204-240px | 204-240px | 100% | 时间+标题+详情+图片 |
| 1小时 | 68-80px | 68-80px | ~85% | 时间+标题 |
| 30分钟 | 34-40px | 34-40px | ~65% | 时间+标题（缩小） |
| 15分钟 | 17-20px | 24px | ~60% | 标题（时间可能隐藏） |
| 5分钟 | 5-7px | 24px | 57% | 标题（最小字体） |

---

## Design Considerations

### Apple Calendar风格的优势

1. **平滑体验**：字体连续缩放，无布局突变
2. **内容优先**：始终尝试显示标题，而非隐藏
3. **可点击性**：极短活动保持最小高度（24px）
4. **简化实现**：无需左侧标题定位，无需额外padding

### 潜在问题与解决方案

**问题1**：字体太小难以阅读（<8px）
- **解决**：设置最小缩放比例0.57（对应8px）
- **补充**：10分钟内活动强制24px高度，确保有足够空间

**问题2**：极短活动（2分钟）block太大显得不成比例
- **权衡**：可点击性 > 时间准确性
- **Apple Calendar做法**：同样会放大极短活动
- **用户感知**：极短活动通常是移动/换乘，放大不影响理解

**问题3**：字体缩放可能导致抗锯齿问题
- **解决**：使用lineHeight: 1.2而非1.0，增加可读性
- **CSS优化**：可考虑添加`-webkit-font-smoothing: antialiased`

**问题4**：并列活动的字体缩放
- **现状**：每个entry独立计算缩放
- **效果**：并列的不同时长活动会有不同字体大小（符合预期）

### 与三级切换模式的对比

| 特性 | 三级切换模式 | Apple Calendar风格 |
|------|-------------|-------------------|
| 实现复杂度 | 高（需要左侧定位） | 低（仅字体缩放） |
| 用户体验 | 突变（52px→36px时布局跳变） | 平滑（连续缩放） |
| 极短活动 | 标题移到左侧 | 保持在block内 |
| 可维护性 | 低（三套渲染逻辑） | 高（统一逻辑） |
| 空间利用 | 需要预留左侧空间 | 无额外空间需求 |

---

## Critical Files

- `/root/travel-planner/scripts/generate-html-interactive.py` (lines 2700-2950)
  - `hgt()` function (line 2719) ← **修改：添加10分钟阈值**
  - `calculateFontScale()` function (新增) ← **添加：字体缩放计算**
  - `TimelineView` component (lines 2656-2950)
  - Entry rendering logic (lines 2800-2930) ← **重写：统一缩放渲染**

### 需要删除的代码

- `twoRowsMode`, `oneRowMode`, `moveToLeft` 变量（lines 2789-2791）
- `showText`, `showTime`, `showSubtext` 变量（lines 2794-2796）
- `hasNarrowEntries` 检测逻辑（lines 2721-2724）
- Timeline track的`paddingLeft`（line 2766）
- `oneRowMode`条件渲染块（lines 2854-2869）
- `twoRowsMode`条件渲染块（lines 2871-2888）
- 左侧标题渲染（lines 2807-2821）

### 需要保留的代码

- `computeColumnLayout()` 函数（处理重叠活动）
- `top()`, `rawHgt()` 函数（时间到像素转换）
- 详情渲染逻辑（transportation和其他类型）
- 图片渲染逻辑（仅在完整高度显示）
- 点击事件和高亮逻辑

---

## Summary

**核心改变：从"三级切换模式"改为"Apple Calendar自适应字体缩放"**

**优势：**
1. **平滑体验**：字体连续缩放，无布局跳变
2. **简化实现**：无需左侧标题定位，删除复杂的三分支逻辑
3. **更好的可读性**：始终尝试显示内容，而非隐藏
4. **Apple Calendar标准**：符合业界最佳实践

**关键实现点：**
1. 10分钟内活动强制24px最小高度（可点击性）
2. 字体线性缩放，最小0.57倍（8px）
3. 基于高度阈值显示/隐藏不同内容层级
4. 统一渲染逻辑，减少代码复杂度

**测试重点：**
- 极短活动（<10分钟）保持24px高度和可点击性
- 字体平滑缩放无突变
- 不同时长活动显示正确的内容层级
- 并列活动的独立缩放效果
