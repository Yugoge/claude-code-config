# Sidebar Collapse Toggle + Drag-Drop Overlay Centering

## Context

Two UX improvements for the web chat interface:
1. The left sidebar (session list) is always visible on tablet/desktop with no way to collapse it — user wants a toggle to collapse/expand
2. The drag-drop glassmorphism "Drop files here" overlay centers relative to the full viewport (`position: fixed`), but should center relative to the chat area only (excluding sidebar)

## Changes

### Step 1: Add `sidebarCollapsed` to LocalSettings

**File**: `sources/sync/localSettings.ts`

- Add `sidebarCollapsed: z.boolean()` to `LocalSettingsSchema`
- Add default `sidebarCollapsed: false` to `localSettingsDefaults`

Device-specific (not synced) — different screen sizes may want different states.

### Step 2: Wire collapse in SidebarNavigator + expand button

**File**: `sources/components/SidebarNavigator.tsx`

- Import `useLocalSettingMutable('sidebarCollapsed')`
- When `sidebarCollapsed && showPermanentDrawer`: use hidden drawer config (width: 0, display: none)
- Render a small expand button (chevron-forward icon) at top-left of content area when collapsed
- On press: `setSidebarCollapsed(false)`

### Step 3: Add collapse button in SidebarView header

**File**: `sources/components/SidebarView.tsx`

- Add a collapse button (`chevron-back` icon) in the header right icon group
- On press: calls `useLocalSettingMutable('sidebarCollapsed')` setter to `true`
- Web-only visibility (Platform.OS === 'web')

### Step 4: Fix drag-drop overlay centering

**File**: `sources/components/AgentInput.tsx` (line ~598)

Change the outer overlay from `position: 'fixed'` (full viewport) to `position: 'absolute'` within the chat content area. Since AgentInput is rendered inside the chat area (not sidebar), absolute positioning will center the "Drop files here" text relative to the chat area only.

Ensure the parent container has `position: 'relative'` if needed.

## Files Modified

| # | File | Action |
|---|------|--------|
| 1 | `localSettings.ts` | Add `sidebarCollapsed` boolean field |
| 2 | `SidebarNavigator.tsx` | Wire collapse state + render expand button when collapsed |
| 3 | `SidebarView.tsx` | Add collapse toggle button in header |
| 4 | `AgentInput.tsx` | Change overlay from `fixed` to `absolute` positioning |

## Verification

1. Typecheck: `cd /root/happy && npx tsc -p packages/happy-app/tsconfig.json --noEmit`
2. Build web: build and deploy to test
3. Test sidebar toggle: click collapse → sidebar hides, chat expands. Click expand → sidebar returns.
4. Test drag-drop: drag file over chat → "Drop files here" centers in chat area, not full viewport
5. Test persistence: collapse sidebar, reload → stays collapsed
