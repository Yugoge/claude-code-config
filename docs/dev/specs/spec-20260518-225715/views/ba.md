<!-- AUTO-GENERATED VIEW for ba | source: docs/dev/specs/spec-20260518-225715.md | extracted: 2026-05-19T06:00:00Z -->

# ba view of spec-20260518-225715

**Monolith**: docs/dev/specs/spec-20260518-225715.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> **Pipeline**: ba → dev → qa

> - **BA 更新**：输出 `acceptance-criteria-<task_id>.json`（Executable AC schema），调用 Blast Radius Tool 生成预测图

---

## BA Integration Point

**ba.md 当前 JSON context 缺少 acceptance_criteria 字段**（line 1004 之后无此字段），需新增指向 `acceptance-criteria-<task_id>.json` 的路径引用。

---

## BA Obligations

### 5.2 Trigger Fields

- **触发条件**：`complexity_tier >= STANDARD` 或任意 tier 且 `risk_level = high`
- **位置**：BA → **[test-writer]** → Dev → QA

### 5.3 BA Phase

- **双阶段**：BA 阶段基于 files_to_modify 预测，QA 阶段基于实际 git diff 重跑

### 5.4: BA → Executable AC Format

BA 输出结构化 AC JSON，机器可执行，Test-Writer 和 QA 直接读取。

- **独立文件**：`docs/dev/acceptance-criteria-<task_id>.json`（context.json 只引用路径）
- **主观视觉 AC**：强制先量化（色彩 token、px 测量），实在不行才 `testability: manual-only`
- **manual-only**：产生 `pending_manual_evidence` 状态，不计入自动化通过率

**ui type check 示例**：
```json
{
  "type": "ui",
  "given": "...", "when": "...", "then": "...",
  "check": {
    "url": "/page",
    "viewports": ["1440x900", "390x844"],
    "selectors": { "primary_role": {"role": "button", "name": "Save"}, "data_testid": "save-btn" },
    "assertions": [{"selector_ref": "success-toast", "property": "visible", "match": "equals", "value": true}]
  }
}
```

### 5.6 BA Update

- **BA 更新**：输出 `acceptance-criteria-<task_id>.json`（Executable AC schema），调用 Blast Radius Tool 生成预测图
