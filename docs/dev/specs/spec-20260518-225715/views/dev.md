<!-- AUTO-GENERATED VIEW for dev | source: docs/dev/specs/spec-20260518-225715.md | extracted: 2026-05-19T06:00:00Z -->

# dev view of spec-20260518-225715

**Monolith**: docs/dev/specs/spec-20260518-225715.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> **Pipeline**: ba → dev → qa

> - **Dev 更新**：读取 blast-radius-map.json，对每个 gap 必须声明验证方式，让 test-writer 骨架测试通过

---

## Section 1: Before

**集成点探查结果（background exploration，2026-05-18）**

关键发现：AC 注入基础设施已**部分存在**（close.md branch 2、qa.md spec_section_updates），缺失的是标准化 AC ID 命名、scoring tier 追踪、QA results ledger、和 post-QA 注入 hook。

| 文件 | 步骤/位置 | 行范围 | 新增内容 |
|------|----------|--------|---------|
| dev.md | Step 3 BA 派单 | 336–373 | score-inject.sh 调用（BA 派单前） |
| dev.md | Step 8 Dev 派单 | 597–623 | score-inject.sh 调用（Dev 派单前） |
| dev.md | Step 11 QA 派单 | 723–758 | score-inject.sh 调用（QA 派单前） |
| dev.md | Step 12.0 spec 更新后 | 766–788 | score-update.sh 调用（QA 完成后） |
| dev.md | Step 15 完成报告 | 971–1081 | 工分变化摘要 |
| close.md | Step 3 生成报告后 | 360–376 | AskUserQuestion 1-5★ + score-update.sh |
| ba.md | Output JSON | ~1004 | 新增 `acceptance_criteria_path` 字段 |
| qa.md | Output JSON | ~1189 | 新增 `failures[].primary_cause` 枚举字段 |

**设计原则**：
- `agent-scores.json`：inject（只读）+ update（追加写），不进任何条件分支，纯 prompt 层
- `acceptance-criteria-*.json`：BA→test-writer→QA 共享契约，context.json 只引用路径
- Blast Radius 双阶段：BA 侧预测（约束 Dev）→ QA 侧核查（不可豁免）
- Canary：stdout 重定向 `/dev/null`，不影响 prompt cache TTL

**集成挂载点**：commands/dev.md（BA/Dev/QA 派单步骤各加 score-inject.sh 调用，QA 完成后加 score-update.sh），commands/close.md（CLOSE:YES 后加 AskUserQuestion + score-update.sh）

---

## Section 5: User's Acceptance Criterion

以上全部计划（研究对话中设计的所有组件），按优先级实施：

### 5.1: 吉祥物工分系统（Mascot Scoring System）

每个 agent 有独立工分（0-100），五个段位：见习学徒(0-20)、初级工匠(21-40)、熟练工匠(41-60)、资深工匠(61-80)、宗师级(81-100)。

- **存储**：`~/.claude/agent-scores.json`，全局文件，含 global + projects 双轨
- **范围**：全部 21 个 agents（ba, dev, qa, ui-specialist, architect, product-owner, user, pm, changelog-analyst, push-analyst, merge-analyst, pull-analyst, cleanliness-inspector, style-inspector, prompt-inspector, rule-inspector, git-edge-case-analyst, cleaner, test-validator, test-executor, spec）
- **当前有事件的 agents**：ba, dev, qa（专家暂时不计算事件，但 schema 预留）
- **Prompt 注入**：prompt 里显示段位+区间（不显示精确数字），最近 3 条历史事件，角色专属提示语
- **注入位置**：角色声明之后、任务指令之前
- **分值待定**：dev 的 delta 量级需校准（用户认为当前太大），待用户确认"升一段位需要几个成功 cycle"后确定最终数字

**当前事件表（dev/ba/qa，scale 待最终确认）**：

| 来源 | 事件 | dev | ba | qa |
|------|------|-----|----|----|
| QA | 首轮通过 | +6 | +3 | 0 |
| QA | 驳回(Dev问题) | -12 | 0 | 0 |
| QA | 驳回(BA问题) | -5 | -8 | 0 |
| QA | 二轮通过 | +3 | 0 | 0 |
| /close | SUCCESS，QA曾PASS | +15 | +8 | +8 |
| /close | SUCCESS，QA曾FAIL→修复 | +15 | +8 | +6 |
| /close | FAIL，QA曾PASS | -10 | -5 | -12 |
| /close | FAIL，QA曾FAIL | -10 | -5 | 0 |
| 用户 | 5★ | +2 | +1 | +1 |
| 用户 | 4★ | -5 | -3 | -3 |
| 用户 | 3★ | -15 | -8 | -8 |
| 用户 | 2★ | -25 | -12 | -12 |
| 用户 | 1★ | -40 | -20 | -20 |

**1-5 星评分 Delta 表（非线性，非对称）**：

| 用户评分 | dev | ba | qa | 说明 |
|---------|-----|----|----|------|
| **5★** | **+2** | **+1** | **+1** | **基准线：做到位仅此而已** |
| 4★ | -5 | -3 | -3 | 略有不足 |
| 3★ | -15 | -8 | -8 | 明显问题 |
| 2★ | -25 | -12 | -12 | 很差 |
| **1★** | **-40** | **-20** | **-20** | **万劫不复** |
| 跳过 | 0 | 0 | 0 | 不触发任何 delta |

**实现脚本**：
- `~/.claude/scripts/score-update.sh` —— 接收 `--agent <name> --event <type> --note <text>` 参数，读改写 agent-scores.json
- `~/.claude/scripts/score-inject.sh` —— 输出注入文本块，供编排器在派单前调用

### 5.2: Test-Writer Agent

从 BA 输出的 Executable AC JSON 生成 pytest + Playwright 测试骨架，测试持久化积累，Dev 让骨架测试通过（TDD 流）。

- **触发条件**：`complexity_tier >= STANDARD` 或任意 tier 且 `risk_level = high`
- **位置**：BA → **[test-writer]** → Dev → QA
- **输出**：`tests/generated/<task_id>/test_AC*.py` + `tests/generated/manifest.json`
- **骨架内容**：非空 TODO，用 `pytest.fail("TEST_INCOMPLETE: ...")` 作硬阻断
- **hook_check 类型**：从 AC JSON 完全自动生成，无需 Dev 填写
- **Dev 边界**：只能填充 `pytest.fail(...)` 处的期望值，不能修改断言逻辑
- **UPDATE vs CREATE 逻辑**：基于内容哈希（`ac_uid`），哈希相同幂等跳过，哈希变化归档旧文件生成新文件，永不删除只归档

### 5.3: TDAD Blast Radius Tool（AST 级别测试依赖图）

在 BA 和 QA 阶段各运行一次，输出 `blast-radius-map.json`，告知 Dev 必须验证哪些具体测试。

- **分析器**：Python `ast` 模块 + grep（不用 jedi/rope，保持轻量），每条边标注置信度
- **输出**：`dev-registry/<task_id>/blast-radius-map.json`（持久化，嵌入 context.json 引用）
- **Dev 必须声明**：对每个 coverage_gap 和 required_validation，必须在 report 里声明运行了哪些测试 / 新写了什么测试 / 显式豁免（QA 可否决豁免）
- **严重性**：hooks/ 目录的缺口 → `severity: critical`
- **当前无测试时**：工具仍运行，但 dependent_tests 为空，仅输出 coverage_gaps（激励写测试）

### 5.4: BA → Executable AC Format

BA 输出结构化 AC JSON，机器可执行，Test-Writer 和 QA 直接读取。

- **四种 type**：`ui | api | data | hook`，每种有专属 check 对象字段
- **ac_uid**：`sha256(type + given + when + then + check内容)` 前16位，排除易变字段

### 5.5: Cache-Safe Canary Verification（SessionStart Hook）

每次 session 启动验证所有关键 hook 是否正常工作。

- **前置修复**：`session-info.sh` 和 `session-git-init.sh` 目前有 stdout 输出需改为 stderr
- **LINE_LIMIT 决策**：`pretool-read-size-guard.py` 实际使用 1000，CLAUDE.md 写 600，实施前需统一
- **注册**：SessionStart hook in settings.json

### 5.6: BA/Dev/QA Agent 更新（支持新组件）

- **Dev 更新**：读取 blast-radius-map.json，对每个 gap 必须声明验证方式，让 test-writer 骨架测试通过
