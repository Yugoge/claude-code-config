# Claude Code PPT/Word 文档 Skills 配置最佳实践 (2025)

> 全面学习指南：如何配置和使用 Claude Code 的 PPTX 和 DOCX Skills
> Last Updated: 2025-12-27

---

## 📋 目录

1. [Agent Skills 标准概述](#agent-skills-标准概述)
2. [SKILL.md 文件格式规范](#skillmd-文件格式规范)
3. [PPTX Skill 最佳实践](#pptx-skill-最佳实践)
4. [DOCX Skill 最佳实践](#docx-skill-最佳实践)
5. [MCP 服务器集成](#mcp-服务器集成)
6. [上下文窗口管理](#上下文窗口管理)
7. [故障排查指南](#故障排查指南)
8. [快速开始指南](#快速开始指南)
9. [最佳实践检查清单](#最佳实践检查清单)
10. [生产级配置示例](#生产级配置示例)
11. [2025 新特性](#2025-新特性)

---

## 🎯 Agent Skills 标准概述

### 什么是 Agent Skills？

Agent Skills 是一种标准化的方式，用于扩展 AI 代理的能力。2025年12月，OpenAI 采用了这一标准，使其成为跨平台的通用解决方案。

### 核心特点

- **标准化格式**: 使用 YAML frontmatter 的 Markdown 文件
- **跨平台兼容**: 支持 Claude、ChatGPT 和其他 AI 平台
- **官方规范**: [agentskills.io](https://agentskills.io)
- **开源生态**: [github.com/anthropics/skills](https://github.com/anthropics/skills)

### 支持的文档类型

- **PPTX**: PowerPoint 演示文稿创建和编辑
- **DOCX**: Word 文档创建和编辑（支持追踪修订）
- **XLSX**: Excel 电子表格（公式、格式化）
- **PDF**: PDF 文件操作和提取

---

## 📄 SKILL.md 文件格式规范

### 基本结构

```markdown
---
name: skill-name
description: Brief description (max 1024 chars)
version: 1.0.0
author: Your Name
tags:
  - pptx
  - documents
  - presentation
---

# Skill Title

## Overview
Detailed explanation of what this skill does...

## Workflow
Step-by-step instructions...

## Examples
Concrete usage examples...
```

### YAML Frontmatter 验证规则

#### 必填字段

- **name**:
  - 最大 64 字符
  - 仅小写字母、数字、连字符
  - 不能包含 XML 标签
  - 不能使用保留字

- **description**:
  - 最大 1024 字符
  - 不能为空
  - 不能包含 XML 标签
  - 简洁描述技能功能

#### 可选字段

- **version**: 语义化版本号 (如 1.0.0)
- **author**: 作者信息
- **tags**: 标签数组，用于分类
- **requires**: 依赖的其他 skills 或工具

### 文件大小建议

**重要**: 保持 SKILL.md 主体内容 **少于 500 行**，以获得最佳性能。

如果内容超过 500 行：
1. 拆分为多个文件
2. 使用渐进式披露模式
3. 将详细文档移到外部文件

---

## 🎨 PPTX Skill 最佳实践

### 三种核心工作流

#### 1. HTML-to-PPTX 转换 (推荐用于新建)

**适用场景**: 从零创建演示文稿

**工作流程**:
```bash
# 1. 使用 pptx-js 库创建 HTML 结构
npm install pptx-js

# 2. 编写 HTML 内容
cat > content.html <<EOF
<div class="slide">
  <h1>Title Slide</h1>
  <p>Subtitle</p>
</div>
EOF

# 3. 转换为 PPTX
node convert-to-pptx.js content.html output.pptx
```

**优势**:
- 简单直观的 HTML 语法
- 支持丰富的样式
- 适合批量生成

**最佳实践**:
- 使用语义化 HTML 标签
- 保持样式一致性
- 利用模板减少重复代码

#### 2. OOXML 直接操作 (用于精细控制)

**适用场景**: 需要精确控制 PowerPoint 内部结构

**工作流程**:
```bash
# 1. 解包 PPTX (实际上是 ZIP 文件)
unzip template.pptx -d unpacked/

# 2. 编辑 XML 文件
vim unpacked/ppt/slides/slide1.xml

# 3. 验证 XML
python ooxml/scripts/validate.py unpacked/

# 4. 重新打包
cd unpacked && zip -r ../modified.pptx *
```

**优势**:
- 最大灵活性
- 可访问所有 PowerPoint 功能
- 适合复杂自动化

**注意事项**:
- 必须验证 XML 语法
- 保持 XML 命名空间正确
- 小心处理关系文件 (rels)

#### 3. 模板化创建 (最高效)

**适用场景**: 基于已有模板批量生成演示文稿

**设置步骤**:
```python
from pptx import Presentation

# 1. 加载模板
prs = Presentation('template.pptx')

# 2. 添加幻灯片
slide_layout = prs.slide_layouts[1]
slide = prs.slides.add_slide(slide_layout)

# 3. 填充内容
title = slide.shapes.title
title.text = "New Slide Title"

# 4. 保存
prs.save('output.pptx')
```

**模板最佳实践**:
- 附加 .pptx 模板文件给 Claude
- 明确指示使用模板的布局和颜色
- 布局和颜色通常会保留（但不保证 100%）
- 内部验证 1-2 个模式以确保稳定性

### 文件大小和规模限制

| 限制类型 | 数值 | 说明 |
|---------|------|------|
| 最大文件大小 | 30MB | 上传+下载总和 |
| 实际容量 | 取决于 token 限制 | 受上下文长度影响 |
| 推荐幻灯片数 | 10-100 | 适合业务材料 |
| 内部验证 | 1-2 个模式 | 确保稳定性 |

### 设计原则

1. **一致性优先**
   - 使用统一的字体和配色
   - 保持幻灯片布局一致
   - 标准化间距和对齐

2. **内容层次**
   - 标题使用 H1-H3
   - 要点使用列表
   - 强调使用粗体/颜色

3. **视觉优化**
   - 避免过度拥挤
   - 使用高质量图片
   - 保持文字可读性

### 故障排查

**问题**: PPTX 文件损坏
```bash
# 解决方案：验证 ZIP 结构
unzip -t output.pptx
```

**问题**: 布局错乱
```bash
# 解决方案：检查 slideLayout 引用
grep -r "slideLayout" unpacked/ppt/_rels/
```

**问题**: 文件过大
```bash
# 解决方案：压缩图片
python -m pptx.util.compress_images input.pptx output.pptx
```

---

## 📝 DOCX Skill 最佳实践

### 四种核心工作流

#### 1. docx-js 创建新文档 (推荐)

**适用场景**: 从零创建 Word 文档

**完整步骤**:
```javascript
const { Document, Packer, Paragraph, TextRun } = require("docx");
const fs = require("fs");

// 1. 创建文档
const doc = new Document({
  sections: [{
    properties: {},
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: "Hello World",
            bold: true,
            size: 28
          })
        ]
      })
    ]
  }]
});

// 2. 导出为 .docx
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("output.docx", buffer);
});
```

**必读文件**: `docx-js.md` (~500 行)
- **重要**: 必须完整阅读，不能设置范围限制
- 包含详细语法、格式化规则和最佳实践
- 理解所有功能和边界情况

#### 2. python-docx 编辑现有文档

**适用场景**: 修改已有的 Word 文档

**工作流程**:
```python
from docx import Document

# 1. 打开文档
doc = Document('existing.docx')

# 2. 修改段落
for para in doc.paragraphs:
    if "old text" in para.text:
        para.text = para.text.replace("old text", "new text")

# 3. 添加新段落
doc.add_paragraph('New content', style='BodyText')

# 4. 保存
doc.save('modified.docx')
```

**关键要点**:
- 始终先读取文件
- 保留原有格式
- 谨慎处理样式

#### 3. 追踪修订工作流 (高级)

**适用场景**: 需要文档版本控制和审阅

**编辑工作流**:
```bash
# 1. 解包 DOCX
python ooxml/scripts/unpack.py input.docx unpacked_dir/

# 2. 编辑 word/document.xml
vim unpacked_dir/word/document.xml

# 3. 立即验证
python ooxml/scripts/validate.py unpacked_dir/

# 4. 仅在验证通过后重新打包
python ooxml/scripts/pack.py unpacked_dir/ output.docx
```

**验证流程**:
```bash
# XML 语法验证
xmllint --noout unpacked_dir/word/document.xml

# 关系验证
python ooxml/scripts/check_rels.py unpacked_dir/
```

**追踪修订查看**:
```bash
# 转换为 Markdown 保留追踪修订
pandoc --track-changes=all input.docx -o output.md

# 提取纯文本（忽略追踪修订）
pandoc --track-changes=reject input.docx -o clean.md
```

#### 4. 纯文本提取

**适用场景**: 只需要读取文档内容

**简单方法**:
```bash
# 使用 pandoc
pandoc input.docx -t plain -o output.txt

# 使用 python-docx
python -c "from docx import Document; print('\n'.join([p.text for p in Document('input.docx').paragraphs]))"
```

### 文档编辑最佳实践

#### 创建 vs 编辑决策树

```
是否有现有文档？
├─ 否 → 使用 docx-js (创建工作流)
└─ 是 → 需要什么操作？
    ├─ 简单文本替换 → python-docx
    ├─ 复杂 OOXML 操作 → 解包/编辑/验证/打包
    ├─ 读取内容 → pandoc 转 markdown
    └─ 审阅修订 → pandoc --track-changes=all
```

#### 验证检查清单

- [ ] XML 语法正确
- [ ] 命名空间保持一致
- [ ] 关系文件 (*.rels) 完整
- [ ] 内容类型正确
- [ ] 文件可在 Word 中打开

### 格式化最佳实践

```python
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# 1. 设置标题
heading = doc.add_heading('Main Title', level=1)
heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

# 2. 设置段落格式
para = doc.add_paragraph('Body text')
run = para.runs[0]
run.font.name = 'Arial'
run.font.size = Pt(12)
run.font.color.rgb = RGBColor(0, 0, 0)

# 3. 添加表格
table = doc.add_table(rows=3, cols=3)
table.style = 'Light Grid Accent 1'

# 4. 保存
doc.save('formatted.docx')
```

---

## 🔌 MCP 服务器集成

### 什么是 MCP？

**Model Context Protocol (MCP)** 允许 Claude Code 连接外部工具和数据源。

### PPTX MCP 服务器配置

#### 安装 PowerPoint MCP Server

```bash
# 1. 克隆仓库
git clone https://github.com/socamalo/PPT_MCP_Server.git
cd PPT_MCP_Server

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 Claude Code
cat >> ~/.config/claude/mcp_config.json <<EOF
{
  "mcpServers": {
    "pptx-automation": {
      "command": "python",
      "args": ["/path/to/PPT_MCP_Server/server.py"],
      "env": {}
    }
  }
}
EOF
```

#### 使用示例

```python
# Claude 可以调用 MCP 工具
# 创建演示文稿
await mcp.call_tool("create_presentation", {
  "title": "Sales Report",
  "template": "corporate"
})

# 添加幻灯片
await mcp.call_tool("add_slide", {
  "layout": "title_and_content",
  "title": "Q4 Results",
  "content": ["Revenue up 15%", "New customers: 500"]
})
```

### DOCX MCP 服务器配置

#### 安装 Document Operations MCP

```bash
# 1. 安装服务器
npm install -g @alejandroballesteros/document-operations

# 2. 配置 Claude Code
cat >> ~/.config/claude/mcp_config.json <<EOF
{
  "mcpServers": {
    "document-ops": {
      "command": "npx",
      "args": ["-y", "@alejandroballesteros/document-operations"],
      "env": {}
    }
  }
}
EOF
```

#### 使用示例

```javascript
// 读取 Word 文档
const content = await mcp.call_tool("read_docx", {
  "path": "/path/to/document.docx"
});

// 修改内容
await mcp.call_tool("write_docx", {
  "path": "/path/to/output.docx",
  "content": modifiedContent
});
```

### tfriedel/claude-office-skills 集成

这是最全面的 Office 技能包，包含所有文档类型。

#### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/tfriedel/claude-office-skills.git
cd claude-office-skills

# 2. 复制到 Claude Code skills 目录
cp -r public/pptx ~/.claude/skills/
cp -r public/docx ~/.claude/skills/
cp -r public/xlsx ~/.claude/skills/
cp -r public/pdf ~/.claude/skills/

# 3. 安装依赖
cd ~/.claude/skills/pptx && npm install
cd ~/.claude/skills/docx && pip install -r requirements.txt
```

#### 目录结构

```
~/.claude/skills/
├── pptx/
│   ├── SKILL.md          # PPTX 技能定义
│   ├── scripts/
│   │   ├── html2pptx.js
│   │   └── validate.py
│   └── templates/
├── docx/
│   ├── SKILL.md          # DOCX 技能定义
│   ├── scripts/
│   │   ├── pack.py
│   │   ├── unpack.py
│   │   └── validate.py
│   └── ooxml/
└── xlsx/
    └── SKILL.md
```

### MCP 最佳实践

1. **环境隔离**
   - 为每个 MCP 服务器使用独立的虚拟环境
   - 避免依赖冲突

2. **错误处理**
   - 始终检查工具调用返回值
   - 实现重试机制

3. **性能优化**
   - 缓存常用模板
   - 批量操作减少 MCP 调用

4. **安全考虑**
   - 验证文件路径
   - 限制文件大小
   - 扫描恶意内容

---

## 💾 上下文窗口管理

### 上下文限制

Claude Code 的上下文窗口有限，大型文档可能超出限制。

### 管理策略

#### 1. 使用 `less` 命令（Linux/Mac）

```bash
# 分页查看大文件
less large-document.md

# 导航命令
# Space: 下一页
# b: 上一页
# /pattern: 搜索
# q: 退出
```

#### 2. 使用 `more` 命令

```bash
# 简单分页
more document.txt
```

#### 3. 分块读取

```python
# Python 脚本分块读取
def read_in_chunks(file_path, chunk_size=1000):
    with open(file_path, 'r') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

# 使用
for chunk in read_in_chunks('large.docx', 1000):
    process(chunk)
```

#### 4. 渐进式披露

在 SKILL.md 中使用：

```markdown
# Main Instructions

Brief overview...

<details>
<summary>Advanced Configuration</summary>

Detailed content that's hidden by default...
</details>
```

### 优化技巧

- **分离参考文档**: 将详细 API 文档放在外部文件
- **使用摘要**: 为长文档提供执行摘要
- **按需加载**: 只在需要时读取完整内容
- **压缩格式**: 使用 JSON 或 YAML 代替冗长的文本

---

## 🔍 故障排查指南

### 常见问题和解决方案

#### 1. PPTX 文件无法打开

**症状**: PowerPoint 报告文件损坏

**诊断**:
```bash
# 检查 ZIP 结构
unzip -t corrupted.pptx

# 查看错误详情
unzip -v corrupted.pptx
```

**解决方案**:
```bash
# 重新打包
cd unpacked_dir
zip -r ../fixed.pptx * -x "*.DS_Store"
```

#### 2. DOCX 格式丢失

**症状**: 打开文档后格式消失

**诊断**:
```bash
# 检查 styles.xml
unzip -p document.docx word/styles.xml | xmllint --format -
```

**解决方案**:
```python
# 使用 python-docx 保留格式
from docx import Document

doc = Document('template.docx')
# 基于模板创建，保留样式
```

#### 3. 中文乱码

**症状**: 中文显示为乱码或方块

**解决方案**:
```python
# 确保使用 UTF-8 编码
from docx import Document

doc = Document()
para = doc.add_paragraph('中文内容')
run = para.runs[0]
run.font.name = 'Microsoft YaHei'  # 使用支持中文的字体
doc.save('chinese.docx')
```

#### 4. 图片显示问题

**症状**: 图片无法显示或位置错误

**解决方案**:
```python
from docx import Document
from docx.shared import Inches

doc = Document()
doc.add_picture('image.png', width=Inches(2))
doc.save('with_image.docx')
```

#### 5. Skills 未激活

**症状**: Claude 不使用 PPTX/DOCX skills

**诊断**:
```bash
# 检查 skills 目录
ls -la ~/.claude/skills/

# 验证 SKILL.md 格式
head -20 ~/.claude/skills/pptx/SKILL.md
```

**解决方案**:
```bash
# 确保 YAML frontmatter 正确
cat ~/.claude/skills/pptx/SKILL.md | grep -A 5 "^---"

# 重启 Claude Code
```

### 调试技巧

#### 启用详细日志

```bash
# 设置环境变量
export CLAUDE_DEBUG=1
export CLAUDE_LOG_LEVEL=debug

# 运行 Claude Code
claude-code
```

#### 验证 OOXML 结构

```bash
# 解压并验证所有 XML
unzip document.docx -d temp/
find temp/ -name "*.xml" -exec xmllint --noout {} \;
```

#### 测试 MCP 连接

```bash
# 手动测试 MCP 服务器
python mcp_server.py --test

# 检查 MCP 配置
cat ~/.config/claude/mcp_config.json | jq .
```

---

## 🚀 快速开始指南

### 30 分钟入门 PPTX Skill

#### 步骤 1: 安装依赖 (5 分钟)

```bash
# 安装 Node.js 和 Python
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs python3 python3-pip

# 安装 Office 库
npm install -g pptx-js
pip3 install python-pptx
```

#### 步骤 2: 创建 SKILL.md (10 分钟)

```bash
mkdir -p ~/.claude/skills/pptx
cat > ~/.claude/skills/pptx/SKILL.md <<'EOF'
---
name: pptx-creator
description: Create PowerPoint presentations from templates or scratch
version: 1.0.0
tags:
  - pptx
  - presentation
---

# PowerPoint Creation Skill

## Overview
This skill helps create professional PowerPoint presentations.

## Workflow
1. Identify presentation requirements
2. Choose template or create from scratch
3. Generate HTML structure
4. Convert to PPTX using pptx-js
5. Validate output

## Example
User: "Create a 5-slide sales presentation"
Assistant: I'll create a sales presentation with:
- Title slide
- Overview
- Product features
- Pricing
- Call to action
EOF
```

#### 步骤 3: 测试 (10 分钟)

创建测试脚本：

```javascript
// test-pptx.js
const pptxgen = require("pptxgenjs");

let pres = new pptxgen();
let slide = pres.addSlide();

slide.addText("Hello World", {
  x: 1,
  y: 1,
  fontSize: 48,
  color: "0088CC",
  bold: true
});

pres.writeFile("test-output.pptx");
console.log("✅ PPTX created successfully!");
```

运行测试：

```bash
node test-pptx.js
open test-output.pptx  # Mac
xdg-open test-output.pptx  # Linux
```

#### 步骤 4: 在 Claude Code 中使用 (5 分钟)

```
你: 使用 pptx-creator skill 创建一个包含 3 张幻灯片的产品介绍
Claude: 我将使用 PPTX skill 创建产品介绍演示文稿...
```

### 30 分钟入门 DOCX Skill

#### 步骤 1: 安装依赖 (5 分钟)

```bash
# 安装 Python DOCX 库
pip3 install python-docx pandoc

# 安装 pandoc
sudo apt-get install pandoc  # Linux
brew install pandoc          # Mac
```

#### 步骤 2: 创建 SKILL.md (10 分钟)

```bash
mkdir -p ~/.claude/skills/docx
cat > ~/.claude/skills/docx/SKILL.md <<'EOF'
---
name: docx-editor
description: Create and edit Word documents with formatting
version: 1.0.0
tags:
  - docx
  - word
  - documents
---

# Word Document Editor Skill

## Overview
Create and edit professional Word documents.

## Workflows

### Creation
1. Use docx-js for new documents
2. Apply formatting and styles
3. Add tables, images, lists
4. Export to .docx

### Editing
1. Open existing document with python-docx
2. Modify content
3. Preserve formatting
4. Save changes

## Example
User: "Create a project proposal document"
Assistant: I'll create a structured proposal with:
- Cover page
- Executive summary
- Project details
- Budget table
- Timeline
EOF
```

#### 步骤 3: 测试 (10 分钟)

创建测试脚本：

```python
# test-docx.py
from docx import Document
from docx.shared import Inches, Pt

doc = Document()

# 添加标题
heading = doc.add_heading('测试文档', 0)

# 添加段落
doc.add_paragraph('这是一个测试段落。')

# 添加表格
table = doc.add_table(rows=3, cols=3)
table.style = 'Light Grid Accent 1'

# 保存
doc.save('test-output.docx')
print("✅ DOCX created successfully!")
```

运行测试：

```bash
python3 test-docx.py
xdg-open test-output.docx
```

#### 步骤 4: 在 Claude Code 中使用 (5 分钟)

```
你: 使用 docx-editor skill 创建一份会议纪要
Claude: 我将创建一份结构化的会议纪要文档...
```

---

## ✅ 最佳实践检查清单

### 配置阶段

- [ ] SKILL.md 包含有效的 YAML frontmatter
- [ ] `name` 字段符合命名规则（小写、64 字符内）
- [ ] `description` 简洁明确（1024 字符内）
- [ ] 主体内容少于 500 行
- [ ] 包含清晰的工作流说明
- [ ] 提供具体使用示例
- [ ] 所有依赖已安装
- [ ] MCP 服务器配置正确

### 开发阶段

- [ ] 优先使用官方 Anthropic skills
- [ ] 在生产环境固定版本号
- [ ] 实现错误处理和验证
- [ ] 测试各种边界情况
- [ ] 文档化所有配置选项
- [ ] 使用版本控制管理 skills

### PPTX 特定

- [ ] 选择合适的工作流（HTML/OOXML/模板）
- [ ] 验证 ZIP 结构完整性
- [ ] 测试在实际 PowerPoint 中打开
- [ ] 优化文件大小（<30MB）
- [ ] 使用一致的设计主题
- [ ] 保持幻灯片数量合理（<100）

### DOCX 特定

- [ ] 区分创建 vs 编辑工作流
- [ ] 始终验证 XML 语法
- [ ] 使用 pandoc 处理追踪修订
- [ ] 测试中文字体支持
- [ ] 保留原有格式和样式
- [ ] 验证文档可在 Word 中打开

### 性能优化

- [ ] 使用渐进式披露减少上下文
- [ ] 缓存常用模板
- [ ] 批量处理多个操作
- [ ] 监控文件大小
- [ ] 优化图片压缩

### 安全考虑

- [ ] 验证文件路径和权限
- [ ] 限制文件大小上传
- [ ] 扫描潜在恶意内容
- [ ] 使用环境变量存储敏感信息
- [ ] 实现访问控制

---

## 📦 生产级配置示例

### 完整 PPTX SKILL.md

```markdown
---
name: enterprise-pptx
description: Enterprise-grade PowerPoint presentation creator with template support, brand guidelines, and validation
version: 2.0.0
author: Your Organization
tags:
  - pptx
  - presentation
  - enterprise
requires:
  - pptx-js@^1.0.0
  - python-pptx@^0.6.21
---

# Enterprise PowerPoint Creation Skill

## Overview

Professional PowerPoint presentation creation with:
- Brand guideline compliance
- Template-based workflows
- Quality validation
- Multi-language support

## Prerequisites

```bash
npm install pptx-js
pip install python-pptx Pillow
```

## Workflows

### 1. Template-Based Creation (Recommended)

**When to use**: Creating presentations based on company templates

**Process**:
```python
from pptx import Presentation

# Load template
prs = Presentation('templates/corporate-template.pptx')

# Add slides
title_slide_layout = prs.slide_layouts[0]
slide = prs.slides.add_slide(title_slide_layout)
title = slide.shapes.title
subtitle = slide.placeholders[1]

title.text = "Q4 Business Review"
subtitle.text = "Executive Summary"

# Save with metadata
prs.core_properties.author = "Claude AI"
prs.core_properties.comments = "Auto-generated presentation"
prs.save('output/q4-review.pptx')
```

**Validation**:
```bash
python scripts/validate-pptx.py output/q4-review.pptx
```

### 2. HTML-to-PPTX Conversion

**When to use**: Dynamic content generation

**Process**:
```javascript
const pptxgen = require("pptxgenjs");

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Claude AI";

// Slide 1: Title
let slide1 = pres.addSlide();
slide1.addText("Company Overview", {
  x: 0.5,
  y: 1.0,
  fontSize: 44,
  color: "003366",
  bold: true
});

// Slide 2: Content
let slide2 = pres.addSlide();
slide2.addText("Key Metrics", { x: 0.5, y: 0.5, fontSize: 28 });
slide2.addTable([
  ["Metric", "Q3", "Q4"],
  ["Revenue", "$1.2M", "$1.5M"],
  ["Customers", "500", "650"]
], { x: 1, y: 1.5, w: 8, h: 2 });

pres.writeFile("dynamic-report.pptx");
```

### 3. OOXML Direct Manipulation (Advanced)

**When to use**: Complex customization beyond API capabilities

**Process**:
```bash
#!/bin/bash
# Extract PPTX
unzip -q template.pptx -d work/

# Modify XML
python scripts/modify-slide.py work/ppt/slides/slide1.xml

# Validate XML
xmllint --noout work/ppt/slides/slide1.xml

# Repackage
cd work && zip -r ../modified.pptx * && cd ..

# Validate final output
python scripts/validate-pptx.py modified.pptx
```

## Brand Guidelines

### Colors (RGB)

- Primary Blue: `003366`
- Secondary Gray: `666666`
- Accent Orange: `FF6600`
- Background: `FFFFFF`

### Fonts

- Headings: Arial Bold, 44pt
- Subheadings: Arial, 28pt
- Body: Arial, 18pt

### Layout Standards

- Title slides: Layout 0
- Content slides: Layout 1
- Section dividers: Layout 2
- Margins: 0.5 inches all sides

## Validation Rules

```python
# scripts/validate-pptx.py
import zipfile
import xml.etree.ElementTree as ET

def validate_pptx(filename):
    checks = []

    # Check 1: Valid ZIP
    try:
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            checks.append(("ZIP structure", True))
    except:
        checks.append(("ZIP structure", False))
        return checks

    # Check 2: Required files present
    required = ['[Content_Types].xml', 'ppt/presentation.xml']
    for req in required:
        checks.append((f"File: {req}", req in zip_ref.namelist()))

    # Check 3: Brand colors used
    # ... additional validation

    return checks
```

## Error Handling

```python
import logging

def safe_create_presentation(config):
    try:
        prs = Presentation(config['template'])
        # ... creation logic
        prs.save(config['output'])
        logging.info(f"✅ Created: {config['output']}")
        return True
    except FileNotFoundError:
        logging.error(f"❌ Template not found: {config['template']}")
        return False
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return False
```

## Examples

### Example 1: Sales Report

**User**: "Create a Q4 sales report presentation"

**Process**:
1. Load `templates/sales-template.pptx`
2. Add title slide with "Q4 Sales Report"
3. Add executive summary slide
4. Add 3 metric slides (revenue, customers, growth)
5. Add conclusion slide
6. Validate brand compliance
7. Save as `q4-sales-report.pptx`

### Example 2: Product Launch

**User**: "Create a product launch deck with 8 slides"

**Process**:
1. Use HTML-to-PPTX for dynamic content
2. Slides: Title, Problem, Solution, Features, Demo, Pricing, Timeline, CTA
3. Include product images from `assets/`
4. Apply brand colors and fonts
5. Validate and export

## Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| File won't open | `unzip -t file.pptx` | Repackage with correct structure |
| Layout broken | Check `slideLayout` refs | Use template layouts |
| Images missing | Check `ppt/_rels/` | Update relationship files |
| Large file size | Check embedded media | Compress images first |

## Performance Tips

- Pre-compress images to <500KB
- Limit to <100 slides for optimal performance
- Cache templates for reuse
- Batch similar operations

## Version History

- **2.0.0** (2025-12): Added brand guidelines, validation
- **1.5.0** (2025-10): Multi-language support
- **1.0.0** (2025-08): Initial release
```

### 完整 DOCX SKILL.md

```markdown
---
name: enterprise-docx
description: Enterprise Word document creator with templates, track changes, and compliance validation
version: 2.0.0
author: Your Organization
tags:
  - docx
  - word
  - documents
  - enterprise
requires:
  - python-docx@^0.8.11
  - pandoc@^2.19
---

# Enterprise Word Document Editor Skill

## Overview

Professional Word document creation and editing with:
- Template-based creation
- Track changes support
- Style compliance
- Multi-format export

## Prerequisites

```bash
pip install python-docx
sudo apt-get install pandoc  # or brew install pandoc
```

## Decision Tree

```
Do you have an existing document?
├─ NO → Creation Workflow
│   ├─ Simple document → docx-js
│   └─ Complex document → python-docx with template
└─ YES → Editing Workflow
    ├─ Simple text changes → python-docx
    ├─ Track changes needed → OOXML editing
    ├─ Extract text only → pandoc
    └─ Complex OOXML ops → Unpack/Edit/Validate/Pack
```

## Workflows

### 1. Creation with python-docx (Recommended)

**When to use**: Creating new structured documents

```python
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def create_business_document(title, content):
    # Load template for styles
    doc = Document('templates/business-template.docx')

    # Title page
    title_para = doc.add_heading(title, 0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Metadata
    doc.core_properties.author = "Claude AI"
    doc.core_properties.title = title

    # Content sections
    for section in content:
        doc.add_heading(section['heading'], level=1)
        for para_text in section['paragraphs']:
            para = doc.add_paragraph(para_text)
            # Apply company style
            run = para.runs[0]
            run.font.name = 'Calibri'
            run.font.size = Pt(11)

    # Footer with page numbers
    section = doc.sections[0]
    footer = section.footer
    footer.paragraphs[0].text = f"Generated by Claude AI"

    return doc

# Usage
content = [
    {
        'heading': 'Executive Summary',
        'paragraphs': ['Key findings...', 'Recommendations...']
    }
]
doc = create_business_document("Annual Report", content)
doc.save('annual-report.docx')
```

### 2. Editing with Track Changes

**When to use**: Collaborative editing with version control

```bash
#!/bin/bash
# edit-with-tracking.sh

INPUT="original.docx"
OUTPUT="revised.docx"
TEMP_DIR="temp_docx"

# 1. Unpack
python ooxml/scripts/unpack.py "$INPUT" "$TEMP_DIR/"

# 2. Edit document.xml
python scripts/add-tracked-change.py "$TEMP_DIR/word/document.xml"

# 3. Validate immediately
if python ooxml/scripts/validate.py "$TEMP_DIR/"; then
    echo "✅ Validation passed"
else
    echo "❌ Validation failed - stopping"
    exit 1
fi

# 4. Repack only if validated
python ooxml/scripts/pack.py "$TEMP_DIR/" "$OUTPUT"

echo "✅ Created: $OUTPUT"
```

**View tracked changes**:
```bash
# Convert to Markdown with all changes
pandoc --track-changes=all original.docx -o changes.md

# Accept all changes
pandoc --track-changes=accept original.docx -o clean.docx

# Reject all changes
pandoc --track-changes=reject original.docx -o rejected.docx
```

### 3. Template-Based Creation

**When to use**: Consistent formatting across documents

```python
from docx import Document

def create_from_template(template_path, data):
    doc = Document(template_path)

    # Replace placeholders
    for para in doc.paragraphs:
        for key, value in data.items():
            if f"{{{key}}}" in para.text:
                para.text = para.text.replace(f"{{{key}}}", value)

    # Replace in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for key, value in data.items():
                    if f"{{{key}}}" in cell.text:
                        cell.text = cell.text.replace(f"{{{key}}}", value)

    return doc

# Usage
data = {
    'client_name': 'Acme Corp',
    'project_name': 'Website Redesign',
    'start_date': '2025-01-15'
}
doc = create_from_template('templates/proposal.docx', data)
doc.save('acme-proposal.docx')
```

### 4. Text Extraction

**When to use**: Reading document content

```bash
# Method 1: pandoc (recommended)
pandoc document.docx -t plain -o output.txt

# Method 2: python-docx
python -c "
from docx import Document
doc = Document('document.docx')
for para in doc.paragraphs:
    print(para.text)
"
```

## Style Guidelines

### Company Styles

```python
from docx.shared import Pt, RGBColor

# Heading 1
heading1_font = {
    'name': 'Calibri',
    'size': Pt(16),
    'bold': True,
    'color': RGBColor(0, 51, 102)  # Company blue
}

# Body Text
body_font = {
    'name': 'Calibri',
    'size': Pt(11),
    'color': RGBColor(0, 0, 0)
}

# Apply to paragraph
def apply_heading1_style(paragraph):
    run = paragraph.runs[0]
    run.font.name = heading1_font['name']
    run.font.size = heading1_font['size']
    run.font.bold = heading1_font['bold']
    run.font.color.rgb = heading1_font['color']
```

### Table Formatting

```python
from docx import Document

doc = Document()
table = doc.add_table(rows=4, cols=3)

# Apply built-in style
table.style = 'Light Grid Accent 1'

# Custom cell formatting
for row in table.rows:
    for cell in row.cells:
        # Set cell padding
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        # Font size
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.size = Pt(10)
```

## Validation

```python
# scripts/validate-docx.py
import zipfile
import xml.etree.ElementTree as ET

def validate_docx(filename):
    results = []

    # 1. Valid ZIP structure
    try:
        with zipfile.ZipFile(filename, 'r') as zf:
            results.append(("ZIP structure", True))

            # 2. Required files
            required = ['[Content_Types].xml', 'word/document.xml']
            for req in required:
                results.append((f"File: {req}", req in zf.namelist()))

            # 3. XML syntax
            try:
                content = zf.read('word/document.xml')
                ET.fromstring(content)
                results.append(("XML syntax", True))
            except ET.ParseError:
                results.append(("XML syntax", False))

    except zipfile.BadZipFile:
        results.append(("ZIP structure", False))

    return results

# Usage
results = validate_docx('document.docx')
for check, passed in results:
    status = "✅" if passed else "❌"
    print(f"{status} {check}")
```

## Chinese Language Support

```python
from docx import Document
from docx.shared import Pt

doc = Document()

# Add Chinese content
para = doc.add_paragraph('这是中文内容测试')
run = para.runs[0]

# Use Chinese-compatible fonts
run.font.name = 'Microsoft YaHei'  # Windows
# or 'SimSun', 'SimHei', 'FangSong'

run.font.size = Pt(12)

doc.save('chinese-document.docx')
```

## Error Handling

```python
import logging
from docx import Document

logging.basicConfig(level=logging.INFO)

def safe_edit_document(input_path, output_path, modifications):
    try:
        # Load document
        doc = Document(input_path)
        logging.info(f"✅ Loaded: {input_path}")

        # Apply modifications
        for mod in modifications:
            mod(doc)

        # Save
        doc.save(output_path)
        logging.info(f"✅ Saved: {output_path}")

        return True

    except FileNotFoundError:
        logging.error(f"❌ File not found: {input_path}")
        return False
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return False

# Usage
def add_summary(doc):
    doc.add_heading('Summary', level=1)
    doc.add_paragraph('This is a summary.')

success = safe_edit_document(
    'input.docx',
    'output.docx',
    [add_summary]
)
```

## Examples

### Example 1: Meeting Minutes

**User**: "Create meeting minutes for today's team sync"

```python
from docx import Document
from datetime import datetime

doc = Document('templates/meeting-minutes.docx')

# Header
doc.add_heading('Team Sync Meeting Minutes', 0)
doc.add_paragraph(f'Date: {datetime.now().strftime("%Y-%m-%d")}')

# Attendees
doc.add_heading('Attendees', level=1)
doc.add_paragraph('• John Doe\n• Jane Smith\n• Bob Johnson')

# Agenda items
doc.add_heading('Discussion Items', level=1)
doc.add_paragraph('1. Project status update\n2. Upcoming deadlines\n3. Resource allocation')

# Action items
doc.add_heading('Action Items', level=1)
table = doc.add_table(rows=3, cols=3)
table.style = 'Light Grid Accent 1'
headers = ['Task', 'Owner', 'Due Date']
for i, header in enumerate(headers):
    table.rows[0].cells[i].text = header

doc.save('meeting-minutes-2025-12-27.docx')
```

### Example 2: Proposal Document

**User**: "Create a project proposal with executive summary, timeline, and budget"

```python
from docx import Document
from docx.shared import Inches

doc = Document('templates/proposal.docx')

# Cover page
doc.add_heading('Project Proposal', 0)
doc.add_paragraph('Website Redesign Initiative')

# Executive Summary
doc.add_page_break()
doc.add_heading('Executive Summary', 1)
doc.add_paragraph('This proposal outlines...')

# Timeline
doc.add_heading('Project Timeline', 1)
# Add Gantt chart image
doc.add_picture('images/timeline.png', width=Inches(6))

# Budget
doc.add_heading('Budget Breakdown', 1)
table = doc.add_table(rows=5, cols=3)
table.style = 'Medium Grid 1 Accent 1'
# Populate budget table...

doc.save('website-redesign-proposal.docx')
```

## Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Encoding errors | Check file encoding | Use UTF-8 encoding |
| Missing styles | Check template | Load proper template |
| Formatting lost | Check XML structure | Use python-docx API |
| Images not showing | Check `word/_rels/` | Fix relationship files |
| Large file size | Check embedded media | Compress images |

## Performance Tips

- Reuse `Document()` objects for batches
- Pre-load templates once
- Compress images before embedding (<500KB)
- Use styles instead of direct formatting
- Limit document to <200 pages for optimal performance

## Version History

- **2.0.0** (2025-12): Track changes, validation, Chinese support
- **1.5.0** (2025-10): Template system
- **1.0.0** (2025-08): Initial release
```

---

## 🎁 2025 新特性

### 1. Agent Skills 标准统一 (2025年12月)

**重大更新**: OpenAI 采用 Agent Skills 标准

- **跨平台兼容**: Skills 可在 Claude、ChatGPT 等平台使用
- **官方规范**: [agentskills.io](https://agentskills.io)
- **生态系统**: 更多第三方 skills 共享

### 2. Claude Code Checkpoints (2025年11月)

**自动保存点**: 防止长会话丢失工作

```bash
# 启用 checkpoints
export CLAUDE_ENABLE_CHECKPOINTS=1

# 查看保存点
ls ~/.claude/checkpoints/

# 恢复到保存点
claude-code --restore-checkpoint <checkpoint-id>
```

### 3. Skills API v2

**增强的 API 控制**:

```python
# 以编程方式管理 skills
from claude import SkillsAPI

api = SkillsAPI()

# 列出已安装的 skills
skills = api.list_skills()

# 安装新 skill
api.install_skill('pptx-creator', version='2.0.0')

# 激活/停用
api.toggle_skill('pptx-creator', enabled=True)
```

### 4. VS Code Extension

**集成开发环境支持**:

- 在 VS Code 中直接编辑 SKILL.md
- 语法高亮和自动补全
- 实时验证和错误检测

```bash
# 安装 VS Code 扩展
code --install-extension anthropic.claude-skills
```

### 5. Desktop Extensions

**扩展 Claude Desktop**:

- 拖放文件到 Claude 自动应用 skills
- 右键菜单快速生成文档
- 系统托盘快捷方式

### 6. 改进的上下文管理

**智能内容分页**:

- 自动检测大文件
- 建议使用 `less`/`more`
- 渐进式加载策略

### 7. 多语言文档支持增强

**更好的国际化**:

- 改进的中文字体处理
- RTL 语言支持（阿拉伯语、希伯来语）
- Unicode 表情符号支持

### 8. 协作功能

**团队 Skills 共享**:

```bash
# 发布 skill 到团队仓库
claude-skills publish --team my-org/pptx-creator

# 从团队安装
claude-skills install --team my-org/pptx-creator
```

---

## 📚 延伸阅读

### 官方文档

- [Claude Code 文档](https://docs.claude.com/claude-code)
- [Agent Skills 规范](https://agentskills.io)
- [Anthropic Skills 仓库](https://github.com/anthropics/skills)

### 社区资源

- [Awesome Claude Skills](https://github.com/travisvn/awesome-claude-skills)
- [Claude Skills 插件市场](https://claude-plugins.dev)
- [MCP 服务器集合](https://mcpservers.org)

### 第三方工具

- [tfriedel/claude-office-skills](https://github.com/tfriedel/claude-office-skills)
- [PowerPoint MCP Server](https://github.com/socamalo/PPT_MCP_Server)
- [Document Operations MCP](https://github.com/alejandroballesteros/document-operations)

### Python 库文档

- [python-pptx 文档](https://python-pptx.readthedocs.io/)
- [python-docx 文档](https://python-docx.readthedocs.io/)
- [pandoc 手册](https://pandoc.org/MANUAL.html)

### JavaScript 库文档

- [pptxgenjs 文档](https://gitbrent.github.io/PptxGenJS/)
- [docx.js 文档](https://docx.js.org/)

---

## 💡 下一步行动

1. **选择你的用例**: PPTX 还是 DOCX？
2. **跟随快速开始**: 30 分钟设置和测试
3. **自定义 SKILL.md**: 根据你的需求调整
4. **集成 MCP 服务器**: 扩展功能
5. **分享给团队**: 协作使用 skills

---

## 🤝 贡献和反馈

发现问题或有改进建议？

- 在 [GitHub](https://github.com/anthropics/skills/issues) 提交问题
- 贡献你的 skills 到社区
- 分享你的最佳实践

---

**创建日期**: 2025-12-27
**最后更新**: 2025-12-27
**版本**: 1.0.0
**作者**: Claude Code 学习助手

---

*此文档基于 2025年12月的最新信息编写，随着 Agent Skills 生态系统的发展可能需要更新。*
