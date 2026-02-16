# Plan: Split utils.py into Independent Modules

## Goal
Split `scripts/utils.py` (593 lines) into 7 focused modules. Each script has ONE independent responsibility. Delete utils.py after split.

## New Files

### 1. `scripts/config.py` (~30 lines)
**Source**: utils.py lines 31-58
**Contents**: All constants (A4_HEIGHT_PT, PAGE_MARGIN_PT, VIEWPORT_*, PROJECT_ROOT, DATA_DIR, *_TEMPLATES_DIR, etc.) + directory creation
**Imports needed**: `os`, `pathlib.Path`
**Imported by**: All other new modules that need paths

### 2. `scripts/resume_loader.py` (~20 lines)
**Source**: utils.py lines 64-78
**Contents**: `load_resume_data()`
**Imports needed**: `logging`, `yaml`, `config.DATA_DIR`
**Imported by**: apply_resume_template.py

### 3. `scripts/page_height.py` (~115 lines)
**Source**: utils.py lines 84-192
**Contents**: `_proper_page_height()` (rename to `check_page_height()` — no underscore, it's a public function now)
**Imports needed**: `logging`, `os`, `config.A4_HEIGHT_PT`, `config.PAGE_MARGIN_PT`, `config.VIEWPORT_*`, `config.MAX_LINES_PER_PAGE`, `config.MIN_LINES_PER_PAGE`
**Note**: `asyncio`, `platform`, `pyppeteer`, `BeautifulSoup` are imported inside the function already
**Imported by**: check_page_height.py

### 4. `scripts/line_width.py` (~140 lines)
**Source**: utils.py lines 198-331
**Contents**: `_extract_line_width_from_template()` (rename to `extract_line_width()`)
**Imports needed**: `logging`, `os`, `re`, `config.RESUME_TEMPLATES_DIR`
**Imported by**: check_all_text_line_widths.py, simulate_layout.py

### 5. `scripts/pdf_converter.py` (~130 lines)
**Source**: utils.py lines 334-459
**Contents**: `_convert_to_pdf()` (rename to `convert_to_pdf()`) + `_convert_fallback()` (keep private)
**Imports needed**: `logging`, `os`, `datetime`, `pathlib.Path`, `config.RESUME_DATA_DIR`, `config.COVER_LETTER_DATA_DIR`, `config.VIEWPORT_*`
**Imported by**: convert_to_pdf.py

### 6. `scripts/mustache.py` (~95 lines)
**Source**: utils.py lines 465-555
**Contents**: `process_mustache_template()`
**Imports needed**: `re`
**Imported by**: apply_resume_template.py, simulate_layout.py

### 7. `scripts/manifest_helpers.py` (~40 lines)
**Source**: utils.py lines 561-593
**Contents**: `load_json()`, `extract_char_limit()`, `extract_ats_keywords()`, `find_story_plan()`
**Imports needed**: `json`, `sys`, `pathlib.Path`
**Imported by**: generate_bullet_manifest.py, generate_revision_manifest.py

## Importer Updates (8 files)

### apply_resume_template.py
```python
# OLD: from utils import DATA_DIR, RESUME_TEMPLATES_DIR, load_resume_data, process_mustache_template
# NEW:
from config import DATA_DIR, RESUME_TEMPLATES_DIR
from resume_loader import load_resume_data
from mustache import process_mustache_template
```

### apply_cover_letter_template.py
```python
# OLD: from utils import COVER_LETTER_TEMPLATES_DIR
# NEW:
from config import COVER_LETTER_TEMPLATES_DIR
```

### convert_to_pdf.py
```python
# OLD: from utils import _convert_to_pdf, RESUME_DATA_DIR, COVER_LETTER_DATA_DIR
# NEW:
from config import RESUME_DATA_DIR, COVER_LETTER_DATA_DIR
from pdf_converter import convert_to_pdf
```
Note: rename `_convert_to_pdf` → `convert_to_pdf` (public now)

### check_page_height.py
```python
# OLD: from utils import _proper_page_height
# NEW:
from page_height import check_page_height
```
Note: rename `_proper_page_height` → `check_page_height` (public now)

### check_all_text_line_widths.py
```python
# OLD: from utils import _extract_line_width_from_template
# NEW:
from line_width import extract_line_width
```
Note: rename `_extract_line_width_from_template` → `extract_line_width` (public now)

### simulate_layout.py
```python
# OLD: from utils import _extract_line_width_from_template, process_mustache_template
# NEW:
from line_width import extract_line_width
from mustache import process_mustache_template
```

### generate_bullet_manifest.py
```python
# OLD: from utils import load_json, extract_char_limit, extract_ats_keywords, find_story_plan
# NEW:
from manifest_helpers import load_json, extract_char_limit, extract_ats_keywords, find_story_plan
```

### generate_revision_manifest.py
```python
# OLD: from utils import load_json, extract_char_limit, extract_ats_keywords, find_story_plan
# NEW:
from manifest_helpers import load_json, extract_char_limit, extract_ats_keywords, find_story_plan
```

## Function Renames (now public, no underscore)
- `_proper_page_height()` → `check_page_height()`
- `_extract_line_width_from_template()` → `extract_line_width()`
- `_convert_to_pdf()` → `convert_to_pdf()`

## Verification
```bash
cd /root/application-assistant/scripts && source ../venv/bin/activate

# Syntax check all new modules
python -m py_compile config.py
python -m py_compile resume_loader.py
python -m py_compile page_height.py
python -m py_compile line_width.py
python -m py_compile pdf_converter.py
python -m py_compile mustache.py
python -m py_compile manifest_helpers.py

# Import check all 8 consumers
python -c "from config import DATA_DIR, RESUME_TEMPLATES_DIR; print('config OK')"
python -c "from resume_loader import load_resume_data; print('resume_loader OK')"
python -c "from page_height import check_page_height; print('page_height OK')"
python -c "from line_width import extract_line_width; print('line_width OK')"
python -c "from pdf_converter import convert_to_pdf; print('pdf_converter OK')"
python -c "from mustache import process_mustache_template; print('mustache OK')"
python -c "from manifest_helpers import load_json, extract_char_limit, extract_ats_keywords, find_story_plan; print('manifest_helpers OK')"

# Verify utils.py is deleted
test ! -f utils.py && echo "utils.py deleted OK"

# Line count check
wc -l config.py resume_loader.py page_height.py line_width.py pdf_converter.py mustache.py manifest_helpers.py
```

## Delete
- `scripts/utils.py` — delete after all new modules and importer updates verified
