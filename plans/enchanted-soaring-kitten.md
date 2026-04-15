# Plan: Consolidate All Inline Styles to Design System

## Context
Explore agent found 16 inline visual patterns (~60+ occurrences) across the frontend that bypass the globals.css design system. These create inconsistencies (amber vs yellow for same status), duplicate code (4 status badge dictionaries), and fight design tokens (extra borders on glass-card). This cleanup consolidates everything into globals.css.

## New CSS Classes to Add in globals.css

1. **`glass-badge-overlay`** — dark floating badge (PdfPreview zoom indicator)
2. **`glass-button:disabled`** — disabled button state (pagination)
3. **Status badge classes** — `glass-badge-status-open`, `glass-badge-status-in-progress`, `glass-badge-status-resolved`, `glass-badge-status-closed`, `glass-badge-status-running`, `glass-badge-status-completed`, `glass-badge-status-failed`

## Execution Order (16 findings, grouped into 5 batches)

### Batch 1: globals.css additions (new classes)
- Add `glass-badge-overlay`, `glass-button:disabled`, and 7 `glass-badge-status-*` classes

### Batch 2: Remove inline overrides fighting design system (Findings 2, 3, 6, 8)
- **F2**: Remove redundant `rounded-2xl` from `glass-card` usages (harmless but noisy). Remove `rounded-xl` where it fights `var(--radius-lg)` — ~26 locations
- **F3**: Remove extra `border` classes from `glass-card` usages — ~9 locations across 6 files (NewTicketForm, admin/tickets, quick-resume-result/form, LiveResumePreview)
- **F6**: Remove `hover:bg-white/20 dark:hover:bg-white/10` from advanced-options.tsx — 1 location
- **F8**: Remove dark mode overrides from LiveResumePreview.tsx — 4 inline overrides

### Batch 3: Replace inline patterns with design system classes (Findings 1, 9, 11, 12, 15)
- **F1**: GlassSelect.tsx — replace 2 inline glass patterns with `glass-card-dropdown` and `input-glass` classes. GlassSegmentedControl.tsx — replace 2 inline patterns with `glass-segmented-control` token usage
- **F9**: PdfPreview.tsx — replace `glass-badge bg-black/50 backdrop-blur-sm` with `glass-badge-overlay`
- **F11**: result/page.tsx — replace `tabCls` function with `glass-button-tab` + aria-selected
- **F12**: NavBar.tsx LocaleToggle — apply `glass-segmented-control` class to container
- **F15**: support/page.tsx — replace bare hover with `glass-menu-item`

### Batch 4: Status badge consolidation (Finding 10)
- Replace all 4 duplicated status color dictionaries with `glass-badge-status-*` classes
- Files: support/page.tsx, support/TicketDetail.tsx, admin/tickets/page.tsx, admin/tickets/AdminTicketDetail.tsx, dashboard/GenerationRow.tsx

### Batch 5: Remaining items (Findings 4, 5, 7, 13, 14, 16)
- **F4**: Replace skeleton container borders with `glass-card` in 5 loading files
- **F5**: Replace `PAG_INACTIVE`/`PAG_BTN` inline definitions with `glass-button` in dashboard/page.tsx
- **F7**: Login decorative skeletons — leave as-is (genuinely decorative, on brand gradient)
- **F13**: containers preview wrappers — leave as-is (demo page, not user-facing)
- **F14**: settings/page.tsx avatar placeholder — deduplicate by extracting shared JSX
- **F16**: `PAG_DISABLED` — use new `glass-button:disabled` + `glass-button`

## Files to Modify

### globals.css (new classes only)
- `frontend/src/app/globals.css`

### Component files (remove/replace inline styles)
- `frontend/src/components/GlassSelect.tsx`
- `frontend/src/components/GlassSegmentedControl.tsx`
- `frontend/src/components/LiveResumePreview.tsx`
- `frontend/src/components/PdfPreview.tsx`
- `frontend/src/components/NavBar.tsx`
- `frontend/src/app/generate/advanced-options.tsx`
- `frontend/src/app/generate/[id]/result/page.tsx`
- `frontend/src/app/generate/[id]/loading.tsx`
- `frontend/src/app/generate/[id]/result/loading.tsx`
- `frontend/src/app/generate/[id]/page.tsx`
- `frontend/src/app/support/page.tsx`
- `frontend/src/app/support/TicketDetail.tsx`
- `frontend/src/app/admin/tickets/page.tsx`
- `frontend/src/app/admin/tickets/AdminTicketDetail.tsx`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/dashboard/loading.tsx`
- `frontend/src/app/dashboard/GenerationRow.tsx`
- `frontend/src/app/quick-resume/quick-resume-result.tsx`
- `frontend/src/app/quick-resume/quick-resume-form.tsx`
- `frontend/src/app/support/NewTicketForm.tsx`
- `frontend/src/app/settings/page.tsx`
- `frontend/src/app/profile/[id]/page.tsx`
- `frontend/src/app/login/page.tsx`

### Skip (no changes needed)
- F7: login/page.tsx decorative skeletons — genuinely one-off on gradient bg
- F13: containers/*.tsx preview wrappers — demo page internals

## Verification
1. `cd frontend && npm run build` — TypeScript compilation passes
2. `docker compose build applio-web && docker compose up -d applio-web`
3. Playwright: visit each affected page (/, /login, /dashboard, /generate, /support, /settings, /profiles, /admin/tickets) and screenshot
4. Verify light mode + dark mode rendering
5. Check no visual regressions in glass-card borders, button states, badge colors
