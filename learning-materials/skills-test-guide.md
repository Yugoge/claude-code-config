# Claude Code Office Skills 测试指南

> 如何测试和使用已安装的 PPTX、DOCX、XLSX、PDF Skills
> 创建日期: 2025-12-27

---

## ✅ Skills 安装状态

### 已安装的 Skills

位置：`~/.claude/skills/`

```
.claude/skills/
├── docx/                    # Word 文档 skill
│   ├── SKILL.md            # Skill 定义
│   ├── docx-js.md          # JavaScript API 文档
│   └── LICENSE.txt
├── pptx/                    # PowerPoint skill
│   ├── SKILL.md
│   ├── html2pptx.md
│   ├── css.md
│   ├── ooxml.md
│   └── LICENSE.txt
├── xlsx/                    # Excel skill
│   ├── SKILL.md
│   ├── recalc.py
│   └── LICENSE.txt
├── pdf/                     # PDF skill
│   ├── SKILL.md
│   ├── FORMS.md
│   ├── REFERENCE.md
│   └── LICENSE.txt
├── frontend-design/         # 前端设计 skill
│   ├── SKILL.md
│   └── LICENSE.txt
└── product-self-knowledge/  # 产品知识 skill
    └── SKILL.md
```

### Skills 验证

所有 SKILL.md 文件都包含正确的 YAML frontmatter：

```yaml
---
name: pptx
description: "Presentation creation, editing, and analysis..."
license: Proprietary. LICENSE.txt has complete terms
---
```

---

## 🧪 测试方法

### 方法 1: 直接对话测试（推荐）

Claude Code 会**自动识别并激活** skills，你只需要用自然语言描述需求：

#### 测试 DOCX Skill

```
你: 帮我创建一个会议纪要文档，包含：
   - 标题："2025年第一季度团队会议"
   - 日期、参会人员
   - 3个讨论议题
   - 行动项表格

Claude: 我会使用 DOCX skill 创建这个文档...
```

#### 测试 PPTX Skill

```
你: 帮我做一个产品介绍 PPT，5 页：
   - 封面
   - 产品概述
   - 核心功能（3个）
   - 价格方案
   - 联系方式

Claude: 我会使用 PPTX skill 创建演示文稿...
```

#### 测试 XLSX Skill

```
你: 创建一个销售数据表格，包含：
   - 月份、销售额、增长率
   - 自动计算总和
   - 添加图表

Claude: 我会使用 XLSX skill 创建电子表格...
```

### 方法 2: 检查 Skills 是否被加载

运行 `/status` 命令查看 Claude Code 配置：

```bash
/status
```

查看输出中是否包含 skills 信息。

---

## 📝 DOCX Skill 使用示例

### 创建新文档

**你说**：
> "用 python-docx 创建一份项目建议书，包括标题、目标、预算表格"

**Claude 会**：
1. 自动激活 DOCX skill
2. 阅读 `docx-js.md` 了解 API
3. 创建 Python/JavaScript 脚本
4. 生成 `.docx` 文件

### 编辑现有文档

**你说**：
> "帮我修改 report.docx，把所有'2024'改成'2025'"

**Claude 会**：
1. 使用 pandoc 读取文档
2. 使用 python-docx 修改内容
3. 保存修改后的文档

### 支持的功能

- ✅ 创建新文档
- ✅ 编辑现有文档
- ✅ 添加表格、列表、图片
- ✅ 设置样式和格式
- ✅ 追踪修订（Track Changes）
- ✅ 添加评论

---

## 🎨 PPTX Skill 使用示例

### 创建新演示文稿

**你说**：
> "创建一个销售报告 PPT，包含图表和数据"

**Claude 会**：
1. 激活 PPTX skill
2. 选择合适的工作流（HTML-to-PPTX 或模板化）
3. 生成演示文稿

### 三种创建方式

#### 1. HTML-to-PPTX（从零开始）

- 适合：完全自定义设计
- 特点：使用 HTML/CSS 定义样式
- 工作流：HTML → PPTX

#### 2. 模板化创建（基于现有模板）

- 适合：有公司模板
- 特点：保留品牌一致性
- 工作流：模板 + 内容 → PPTX

#### 3. OOXML 直接编辑（精细控制）

- 适合：高级定制
- 特点：直接操作 XML
- 工作流：解包 → 编辑 XML → 打包

### 支持的功能

- ✅ 创建幻灯片
- ✅ 添加文本、图片、图表
- ✅ 应用主题和样式
- ✅ 设置动画和过渡
- ✅ 添加演讲者备注

---

## 📊 XLSX Skill 使用示例

**你说**：
> "创建一个预算表，包含收入、支出、自动计算余额"

**Claude 会**：
1. 使用 XLSX skill
2. 创建电子表格
3. 添加公式和格式化

### 支持的功能

- ✅ 创建工作簿和工作表
- ✅ 添加数据和公式
- ✅ 格式化单元格
- ✅ 创建图表
- ✅ 数据验证
- ✅ 条件格式

---

## 📄 PDF Skill 使用示例

**你说**：
> "从 document.docx 生成 PDF，并提取第1-3页的文本"

**Claude 会**：
1. 使用 PDF skill
2. 转换文档为 PDF
3. 提取指定页面文本

### 支持的功能

- ✅ 创建 PDF
- ✅ 合并/拆分 PDF
- ✅ 提取文本和表格
- ✅ 填写 PDF 表单
- ✅ 添加水印和注释

---

## 🎨 Frontend Design Skill

**你说**：
> "创建一个现代化的登录页面，包含表单和动画"

**Claude 会**：
1. 使用 Frontend Design skill
2. 生成高质量的前端代码
3. 避免通用的 AI 美学

---

## 🔧 依赖检查

### 必需的系统工具

```bash
# 检查 pandoc（用于文档转换）
pandoc --version

# 检查 LibreOffice（用于 PDF 转换）
soffice --version

# 检查 Poppler（用于 PDF 处理）
pdftoppm -v
```

### Python 包

```bash
pip list | grep -E "(python-docx|python-pptx|openpyxl)"
```

如果缺少，安装：

```bash
pip install python-docx python-pptx openpyxl
```

### Node.js 包

```bash
npm list -g | grep -E "(pptxgenjs|docx)"
```

如果缺少，安装：

```bash
npm install -g pptxgenjs docx
```

---

## 🐛 故障排查

### Skills 没有被激活

**症状**：Claude 不使用 skills，而是提示无法处理

**解决方案**：
1. 检查 `~/.claude/skills/` 目录存在
2. 验证 SKILL.md 文件格式正确
3. 确保 YAML frontmatter 没有语法错误
4. 重启 Claude Code

### 依赖缺失错误

**症状**：Skills 激活了但执行失败，提示缺少模块

**解决方案**：
```bash
# 安装 Python 依赖
pip install python-docx python-pptx openpyxl defusedxml

# 安装 Node.js 依赖
npm install -g pptxgenjs docx playwright

# 安装系统工具
sudo apt-get install pandoc libreoffice poppler-utils
```

### 文件无法打开

**症状**：生成的 .docx/.pptx 文件损坏

**解决方案**：
1. 检查生成过程是否有错误
2. 验证文件完整性：`unzip -t file.docx`
3. 重新生成文件

---

## 📚 进阶使用

### 组合使用多个 Skills

**示例**：创建完整的项目文档包

```
你: 帮我创建项目交付包：
   1. Word 文档：项目报告
   2. Excel 表格：预算明细
   3. PPT 演示：成果展示
   4. PDF：所有文档的汇总

Claude 会依次激活 DOCX、XLSX、PPTX、PDF skills
```

### 使用模板

**PPTX 模板**：
```
你: 使用 template.pptx 作为模板，创建 Q4 业绩汇报
附件：template.pptx

Claude: 我会分析模板结构，然后基于它创建新的演示文稿
```

**DOCX 模板**：
```
你: 基于 proposal-template.docx 创建客户提案
附件：proposal-template.docx

Claude: 我会保留模板样式，填充新内容
```

---

## ✅ 测试检查清单

完成以下测试，确保 skills 正常工作：

- [ ] **DOCX Skill**
  - [ ] 创建新文档
  - [ ] 编辑现有文档
  - [ ] 添加表格和列表
  - [ ] 应用样式和格式

- [ ] **PPTX Skill**
  - [ ] 从零创建演示文稿
  - [ ] 基于模板创建
  - [ ] 添加图表和图片
  - [ ] 设置主题

- [ ] **XLSX Skill**
  - [ ] 创建电子表格
  - [ ] 添加公式
  - [ ] 创建图表
  - [ ] 格式化单元格

- [ ] **PDF Skill**
  - [ ] 转换文档为 PDF
  - [ ] 提取 PDF 文本
  - [ ] 合并多个 PDF

- [ ] **组合测试**
  - [ ] 同时使用多个 skills
  - [ ] 文档格式互转
  - [ ] 批量处理文件

---

## 🎓 学习资源

### 官方文档

- **PPTX**: 阅读 `.claude/skills/pptx/SKILL.md`
- **DOCX**: 阅读 `.claude/skills/docx/SKILL.md`
- **XLSX**: 阅读 `.claude/skills/xlsx/SKILL.md`
- **PDF**: 阅读 `.claude/skills/pdf/SKILL.md`

### API 参考

- **PPTX**: `html2pptx.md`, `ooxml.md`, `css.md`
- **DOCX**: `docx-js.md`
- **XLSX**: `recalc.py`（示例脚本）
- **PDF**: `FORMS.md`, `REFERENCE.md`

### 最佳实践文档

参考之前创建的学习文档：
- `learning-materials/claude-code-office-skills-best-practices-2025.md`

---

## 💡 提示和技巧

### 1. 明确指定格式

❌ **不好**："帮我创建一个文档"
✅ **好**："帮我创建一个 Word 文档（.docx）"

### 2. 提供详细需求

❌ **不好**："做个 PPT"
✅ **好**："创建5页 PPT，主题是产品发布，包含标题页、功能介绍、价格、时间表、联系方式"

### 3. 指定样式要求

❌ **不好**："创建表格"
✅ **好**："创建蓝色主题的表格，标题行加粗，数据行斑马纹"

### 4. 利用模板

如果有公司模板，告诉 Claude：
> "使用公司标准模板创建 PPT，蓝色配色，Arial 字体"

### 5. 迭代改进

第一次生成后可以继续优化：
```
你: 创建销售报告 PPT
Claude: [生成 PPT]
你: 把第3页的图表改成饼图
Claude: [修改完成]
你: 整体换成深色主题
Claude: [应用新主题]
```

---

## 🎉 总结

你的 Claude Code 已经配置好了完整的 Office Skills：

- ✅ **6 个 Skills 已安装** - PPTX, DOCX, XLSX, PDF, Frontend Design, Product Knowledge
- ✅ **所有文件格式正确** - YAML frontmatter 验证通过
- ✅ **LICENSE 文件已同步** - 符合授权要求
- ✅ **文档完整** - 包含 API 参考和最佳实践

**下一步**：
1. 直接用自然语言测试："帮我创建一个 Word 文档"
2. 查看生成的文件
3. 根据需要迭代改进

祝使用愉快！🚀

---

**创建日期**: 2025-12-27
**作者**: Claude Code 配置助手
**版本**: 1.0.0
