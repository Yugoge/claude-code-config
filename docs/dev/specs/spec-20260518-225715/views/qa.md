<!-- AUTO-GENERATED VIEW for qa | source: docs/dev/specs/spec-20260518-225715.md | extracted: 2026-05-19T06:00:00Z -->

# qa view of spec-20260518-225715

**Monolith**: docs/dev/specs/spec-20260518-225715.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> **Pipeline**: ba → dev → qa

> - **QA 更新**：执行 manifest.json 验证 + blast radius 双阶段验证，输出 `failures[].primary_cause` 枚举（用于工分归因），不再仅靠 prose 判断 AC

---

## QA Integration Point

**qa.md 当前 verdict structure 无 primary_cause 枚举**，需在 `failures[]` 下新增此字段供工分归因使用。

**集成挂载点**：commands/dev.md（BA/Dev/QA 派单步骤各加 score-inject.sh 调用，QA 完成后加 score-update.sh），commands/close.md（CLOSE:YES 后加 AskUserQuestion + score-update.sh）

**实现脚本**：
- `~/.claude/scripts/score-update.sh` —— 接收 `--agent <name> --event <type> --note <text>` 参数，读改写 agent-scores.json
- `~/.claude/scripts/score-inject.sh` —— 输出注入文本块，供编排器在派单前调用

---

## QA Scoring Context

**QA 评分逻辑**：QA 不从自己的 PASS/FAIL 决定直接得分，只从 /close 结果后验得分。

**用户评分机制**：/close CLOSE:YES 后，编排器用 AskUserQuestion 询问 1-5 星，含"跳过"选项。仅 CLOSE:YES 后触发，CLOSE:NO 不询问。

**哲学**：做到位是基本，搞砸万劫不复。正向收益设计为极浅（5★仅+2），负向惩罚设计为陡（4★已亏损，1★-40）。

**非对称设计意图**：5★正向上限仅+2，1★负向深度-40。得到的极少，失去的极多。

**Prompt 注入中的体现**（每个 agent 的提示尾部加入）：
> 用户满意是衡量你工作价值的最终标准，也是工分系统中权重最大的信号。5★意味着你只是完成了本职工作——这不是奖励，这是起点。低于5★将带来远超其他任何事件的惩罚，且不可逆。

---

## QA Verification Obligations

- **QA 职责扩展**：验证 manifest 中 active 测试存在且可导入，运行 `pytest tests/generated/`
- **manual-only**：产生 `pending_manual_evidence` 状态，不计入自动化通过率
- **QA 更新**：执行 manifest.json 验证 + blast radius 双阶段验证，输出 `failures[].primary_cause` 枚举（用于工分归因），不再仅靠 prose 判断 AC
- **成功时**：零 stdout 输出（`exec >/dev/null`），不注入 context，不影响 prompt cache
- **失败时**：仅 stderr 输出，exit 2 阻断会话
- **验证方式**：行为测试（真正运行 hook 脚本传入合成 JSON），不是 grep 源码
- **验证范围**：Write guard、Bash safety、git privilege guard、read size guard
