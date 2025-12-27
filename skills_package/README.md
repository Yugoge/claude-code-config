# Claude Skills Package for Claude Code

这是Claude AI使用的完整技能包，包含6个核心技能模块。

## 📁 包含的技能

### 1. **xlsx** - Excel技能
- 创建和编辑Excel文件（.xlsx, .xlsm, .csv, .tsv）
- 支持复杂公式、格式化、数据分析和可视化
- 包含`recalc.py`脚本用于重新计算公式

### 2. **docx** - Word文档技能
- 创建、编辑和分析Word文档
- 支持跟踪修改、批注、格式保留和文本提取

### 3. **pptx** - PowerPoint技能
- 创建和编辑演示文稿
- 支持布局、添加批注和演讲者备注

### 4. **pdf** - PDF技能
- PDF文档的提取、创建、合并和拆分
- 处理表单和批量操作

### 5. **frontend-design** - 前端设计技能
- 创建独特的生产级前端界面
- 生成创意、精美的代码

### 6. **product-self-knowledge** - 产品知识技能
- Anthropic产品的权威参考
- 关于Claude.ai、Claude Code和Claude API的准确信息

## 🚀 在Claude Code中使用

### 方法1：单独导入技能
1. 在Claude Code中创建新的Custom Skill
2. 复制对应文件夹中的`SKILL.md`内容
3. 粘贴到技能编辑器
4. 保存并启用

### 方法2：批量导入
1. 解压`skills_package.zip`
2. 将每个文件夹中的`SKILL.md`创建为独立技能
3. 对于xlsx技能，还需要包含`recalc.py`脚本

## 📝 每个技能的主要功能

### Excel (xlsx)
```python
# 核心原则：使用公式而非硬编码
sheet['B10'] = '=SUM(B2:B9)'  # ✅ 正确
sheet['B10'] = 1234  # ❌ 错误

# 金融模型颜色标准
- 蓝色：输入值
- 黑色：公式
- 绿色：内部链接
- 红色：外部链接
```

### Word (docx)
```python
# 支持跟踪修改和批注
from docx import Document
doc = Document()
doc.add_paragraph('内容')
doc.save('output.docx')
```

### PowerPoint (pptx)
```python
# 创建演示文稿
from pptx import Presentation
prs = Presentation()
slide = prs.slides.add_slide(layout)
```

### PDF
```python
# 使用pypdf处理PDF
import pypdf
reader = pypdf.PdfReader('input.pdf')
```

## ⚠️ 重要提示

1. **Excel公式重算**：创建Excel文件后必须运行`recalc.py`
2. **格式标准**：金融模型必须遵循颜色编码标准
3. **错误检查**：确保所有公式无错误（#REF!, #DIV/0!等）
4. **版权声明**：部分技能包含专有许可，请查看各自的LICENSE.txt

## 📊 技能优先级

处理文档时的技能选择顺序：
1. 优先使用专门的技能（xlsx用于Excel，docx用于Word）
2. 对于数据分析，优先使用pandas
3. 对于格式化和公式，使用openpyxl
4. 对于可视化，结合matplotlib和Excel图表

## 💡 最佳实践

1. **始终阅读技能文档**：在开始任务前先读取相关SKILL.md
2. **使用动态公式**：避免硬编码计算结果
3. **保持专业格式**：遵循行业标准的颜色和格式规范
4. **测试验证**：使用recalc.py验证Excel公式
5. **错误处理**：检查并修复所有公式错误

## 🔧 技术要求

- Python 3.x
- openpyxl（Excel）
- python-docx（Word）
- python-pptx（PowerPoint）
- pypdf（PDF）
- pandas（数据分析）
- LibreOffice（Excel公式重算）

---

**版本**：2024年11月
**来源**：Claude AI /mnt/skills/public/
