# Update containers page to match latest globals.css

## Context
The containers page (`/containers`) is a design system showcase. After recent changes to globals.css (glass-button padding, glass-card-alert mint/amber), the showcase is out of sync.

## Changes

### 1. `frontend/src/app/containers-css.ts` — sync CSS_SOURCES with current globals.css
- `glass-card-alert`: update from `var(--glass-bg-alert)` to mint/amber background
- `glass-button`: add `padding`, `font-size`, `font-weight`, `line-height`
- Other entries: spot-check and align with current globals.css values

### 2. `frontend/src/app/containers/page.tsx` — remove redundant inline styles
- Button demos: remove `px-5 py-2.5 text-sm font-medium` from `.glass-button` usage (now built into the class)
- Update code snippets in demos to match
- glass-card-alert demo: add dark mode color classes (`text-brand-700 dark:text-amber-200`) to match actual dashboard usage

## Verification
- Build frontend
- Deploy
- Open https://applio.life-ai.app/containers in browser
- Verify buttons render with correct size (no inline padding needed)
- Verify glass-card-alert shows mint/amber tint
