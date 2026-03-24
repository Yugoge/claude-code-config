# Plan: Restore Corrupted Files & Regenerate PDFs

## Context

The sentinel file bug (`.current_job_id`) caused cross-job contamination during concurrent sessions:
- **Commit `3c2504c`** (tempest-vane's Step 12) accidentally **modified huatai's PDFs** instead of creating tempest-vane PDFs
- Huatai's resume PDF changed from 79430→79532 bytes; CL PDF had content change at same size
- Tempest-vane PDFs were **never generated**
- Original clean huatai PDFs exist in commit `54ecdaf`

The generate.md hybrid fix (sentinel→filesystem) is already committed. Working tree is clean.

## Plan

### Step 1: Restore huatai PDFs from git history
Restore the original clean PDFs from commit `54ecdaf` (before corruption):
```bash
git checkout 54ecdaf -- data/resumes/Yuge_Tang_resume_huatai-international-ficc-quantitative-data-analyst_20260321.pdf
git checkout 54ecdaf -- data/cover_letters/Yuge_Tang_cover_letter_huatai-international-ficc-quantitative-data-analyst_20260321.pdf
```

### Step 2: Regenerate tempest-vane resume from existing work files
Tempest-vane has complete work files through step 9 (final bullets) and step 15 (CL final JSON), but is missing:
- `10_resume_final_*.json` (assembled resume)
- `11_resume_final_*.html` (HTML template)
- `16_cl_final_*.html` (CL HTML template)
- Both PDFs

**2a.** Assemble resume from final bullets:
```bash
source venv/bin/activate
python3 scripts/assemble_resume.py \
  data/work/03_design_spec_tempest-vane-quant-analyst_20260321.json \
  data/work \
  data/work/09_bullets_final_tempest-vane-quant-analyst_20260321 \
  data/work/10_resume_final_tempest-vane-quant-analyst_20260321.json
```

**2b.** Apply resume HTML template:
```bash
python3 scripts/apply_resume_template.py \
  data/work/10_resume_final_tempest-vane-quant-analyst_20260321.json \
  data/work/11_resume_final_tempest-vane-quant-analyst_20260321.html \
  kellogg
```

**2c.** Apply cover letter HTML template:
```bash
python3 scripts/apply_cover_letter_template.py \
  data/work/15_cl_final_tempest-vane-quant-analyst_20260321.json \
  data/work/02_job_data_tempest-vane-quant-analyst_20260321.json \
  data/work/10_resume_final_tempest-vane-quant-analyst_20260321.json \
  data/work/16_cl_final_tempest-vane-quant-analyst_20260321.html \
  standard
```

### Step 3: Generate tempest-vane PDFs
```bash
python3 scripts/convert_to_pdf.py \
  data/work/11_resume_final_tempest-vane-quant-analyst_20260321.html \
  data/resumes/Yuge_Tang_resume_tempest-vane-quant-analyst_20260321.pdf

python3 scripts/convert_to_pdf.py \
  data/work/16_cl_final_tempest-vane-quant-analyst_20260321.html \
  data/cover_letters/Yuge_Tang_cover_letter_tempest-vane-quant-analyst_20260321.pdf
```

### Step 4: Cleanup
- Delete orphaned `.current_job_id` file (if it exists)
- Delete obsolete `scripts/refactor-generate-state-paths.py` (if it exists)

### Step 5: Commit
Single commit with all changes:
- Restored huatai PDFs (from git history)
- New tempest-vane resume/CL PDFs + work files
- Cleanup of orphaned files

## Verification
1. Verify huatai resume PDF size matches original (79430 bytes)
2. Open both tempest-vane PDFs to confirm they render correctly
3. Verify no remaining `.current_job_id` file
4. `git status` confirms clean working tree after commit

## Critical Files
- `scripts/assemble_resume.py` — resume assembly from bullets
- `scripts/apply_resume_template.py` — HTML template application
- `scripts/apply_cover_letter_template.py` — CL HTML template
- `scripts/convert_to_pdf.py` — HTML→PDF via pyppeteer
- `data/work/03_design_spec_tempest-vane-quant-analyst_20260321.json` — resume design spec
- `data/work/09_bullets_final_tempest-vane-quant-analyst_20260321/` — 8 final bullet files
- `data/work/15_cl_final_tempest-vane-quant-analyst_20260321.json` — CL final content
