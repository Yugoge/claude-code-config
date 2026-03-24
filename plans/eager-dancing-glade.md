# Plan: Systematic Pipeline Fixes

## 你给的每条feedback → 根本原因 → 怎么修

---

### Resume问题

**1. Hyde Park bullet写成了Harvest Fund的内容（$224bn AuM ETF）**

- 根本原因：纯粹hallucination。Writing expert通过 `read_yaml_section.py --index 2` 拿到的YAML数据是正确的Hyde Park数据，数据层没问题。但writing expert无视了story plan（说写DCF/comps）和YAML excerpt（Hyde Park），凭记忆把Harvest Fund的内容搬过来了。`writing-expert.md` 缺少两条硬规则：(a) story plan是最终权威不得偏离；(b) 如果用了一个数字/公司名但它不在你的yaml_excerpt里，你在hallucinate，停下来检查。
- 修法：在 `.claude/agents/writing-expert.md` 的 Critical Rules 里加：
  - Rule 8 — Story plan是PRIMARY AUTHORITY：story说写什么就写什么，不得替换成其他narrative
  - Rule 9 — 数据自查：写完后对bullet里每一个数字、公司名、产品名做一次检查——它是否出现在yaml_excerpt里？如果不是，删除或替换

---

**2. C++ wording + 衔接性技能**

- 根本原因：writing-expert对技能的描述没有coherence意识，孤立地添加技能词而不考虑resume skills section里已有的相关技能。
- 修法：在 `.claude/agents/writing-expert.md` 加规则：在bullet里提到一项programming language或技术时，检查YAML skills section，如果存在同一技术家族（如C-family: C/C++/C#，JVM-family: Java/Kotlin/Scala，.NET-family: C#/F#/VB等）的其他语言，应该自然地将它们组合提及（如"C++ and C#"），不得孤立地提及一项而忽略明显相关的已有技能。不得hardcode具体语言组合——让agent根据skills section动态判断。

---

### CL问题

**3. CL太长（~365词，两页）**

- 根本原因：`cl-designer.md` 默认budget=350，`cl-story-professional.md` 目标350±20。模板本身有header/footer开销，这个budget必然超一页。
- 修法（三处联动）：
  - `cl-designer.md`：所有 `350` 改为 `300`（包括Total target文字、`total_word_budget` 示例JSON、`--budget` 示例调用、section allocation示例）；同时更新 `calculate_cl_weights.py` 调用示例里的 `--budget 350` → `--budget 300`
  - `cl-story-professional.md`：word target改为"**280–310词，硬上限315**"，所有"~350"和"±20 tolerance"替换
  - 新建 `scripts/validate-cl-wordcount.py`：接受CL draft JSON path作为参数，统计body数组里所有字符串的总词数，输出结果并在超过315词时以非零exit code退出。参考 `validate-bullet-charlimits.py` 的模式。在 `cl-story-professional.md` 的Quality Checklist（CL-5和CL-7）里加一步：写完文件后运行 `python scripts/validate-cl-wordcount.py <output_file>`，词数超限必须重写。

---

**4. 学术段太啰嗦/CL写成了achievement列举而不是故事**

- 根本原因：更宏观的问题——`cl-story-professional.md`（以及上游的education/project agents）没有"写故事"的明确指导，倾向于堆砌课程名和成就列表。
- 修法：在 `cl-story-professional.md` 的 Writing Style Rules 里加：
  - CL写的是narrative，不是achievement list。每段应该有situation-context-so-what的弧线，不得出现"I took courses in X, Y, Z"或"I did A, B, C"的枚举式表达
  - 具体：学术段描述方向和能力（"my coursework in stochastic processes and derivatives pricing gave me..."），不得列公式名或课程名称列表

---

**5. 电力预测项目出现在CL里（不相关经历不应该出现）**

- 根本原因：project/professional agent没有相关性过滤的规则，把所有经历都往里塞。
- 修法：在 `cl-story-professional.md` 加规则：每一段提到的经历必须找到与JD的明确连接角度。如果某个项目/经历与目标岗位没有直接相关性，优先找到一个能让它相关的framing角度（例如电力预测 → "time series forecasting methodologies applicable to..."）；如果实在找不到angle，直接省略，不得为了"全面"而列举无关经历。

---

**6. "I collaborate daily with Quant Analysts"重复出现（迭代架构问题）**

- 根本原因：`cl-story-professional.md` 在CL-5和CL-7两次运行，每次都有权修改全文，但缺少显式的全文去重扫描。第二次运行时读了自己CL-5的draft但没有发现已有重复。
- 修法：在 `cl-story-professional.md` 的Final Coherence Check（CL-5）和Step CL-7 Refinement流程里，各加一步：**显式扫描所有paragraph之间的重复句/重复短语**（超过5个连续词的相同表达），发现后删除后出现的那个。这步要求agent明确执行，不是一笔带过的"ensure no repetition"。

---

**7. "My BA title understates my quant contribution"——自我辩护，应show don't tell**

- 根本原因：`cl-story-professional.md` 没有禁止meta-commentary类表达。
- 修法：在 `cl-story-professional.md` 加规则：禁止任何"我的title/level低估了我的贡献"类自我辩护句式。展示depth的方式是直接写具体行为（"I triage model-level discrepancies by reading the Orchestrade pricing engine source code"），让读者自己得出结论。

---

## 改哪些文件

| 文件 | 改什么 |
|------|--------|
| `.claude/agents/writing-expert.md` | 加Rule 8（story plan primacy）、Rule 9（数据自查）；加skill coherence规则 |
| `.claude/agents/cl-story-professional.md` | word target 280-310/硬上限315；narrative-not-list规则；相关性过滤规则；显式去重扫描；禁止title meta-commentary；加validate-cl-wordcount.py调用步骤 |
| `.claude/agents/cl-designer.md` | 所有350→300，更新示例JSON和脚本调用 |
| `scripts/validate-cl-wordcount.py` | 新建：统计CL draft JSON总词数，>315则非零exit |

---

## 验证方法

改完之后重跑 `/generate` for `deutsche-bank-quant-analyst`：
1. Hyde Park bullet → 必须是DCF/comps内容，不得出现ETF/AuM/Harvest Fund
2. CL词数 → 280–315词（validate-cl-wordcount.py通过）
3. CL → 无重复句；无课程名列表；无电力项目（或已被framing成相关）；无"title understates"；每段是narrative而非成就列表
