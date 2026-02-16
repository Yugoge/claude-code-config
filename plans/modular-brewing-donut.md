# Timeline Calendar UX Improvements Plan

## Context

The HTML timeline calendar currently has two UX issues that reduce usability:

1. **Text overflow in short events**: When events have very short durations (e.g., 2-minute walk), the text is cut off by window edges, making it hard to read activity names.

2. **Overlapping events stack instead of displaying side-by-side**: When multiple events occur at the same time (e.g., 09:00-09:07 taxi and 09:00-10:30 attraction), they overlap with only z-index stacking for visibility. Users must click to bring events forward. This differs from popular calendar apps like Google Calendar and Apple Calendar, which display overlapping events side-by-side in columns.

The user has requested improvements inspired by Apple and Google Calendar design patterns, particularly for handling these two scenarios gracefully.

## Research Findings

Based on web research into calendar design best practices:

- **Google Calendar**: Uses equal-width columns for overlapping events (2 events = 50% each, 3 events = 33% each)
- **Apple Calendar**: Uses staggered/offset layout with partial overlap
- **CodyHouse Schedule Template**: Adaptive text handling with flexbox and overflow management
- **Best practice**: Test with real content (not Lorem ipsum) to expose text overflow issues

**Sources:**
- [Calendar UI Examples: 33 Inspiring Designs](https://www.eleken.co/blog-posts/calendar-ui)
- [Schedule Template in CSS and JavaScript | CodyHouse](https://codyhouse.co/gem/schedule-template)
- [Modern Javascript Timeline & Gantt planner | Mobiscroll](https://demo.mobiscroll.com/javascript/timeline)

## Current Implementation

**Primary file:** `/root/travel-planner/scripts/generate-html-interactive.py`

**Key implementation details (Lines 2634-2795):**

1. **Position calculation**:
   - Hour height (hH): 80px desktop, 68px mobile
   - Formula: `(hour - firstHour) * hH + (minutes / 60) * hH`
   - Minimum height: 8px (ensures clickability)

2. **Current text visibility thresholds** (Lines 2696-2705):
   ```javascript
   const tooNarrow = entryH < 16;   // Hide all text
   const showTime = entryH >= 24;   // Show time (09:00-09:30)
   const showText = entryH >= 36;   // Show activity name
   const showSubtext = entryH >= 52; // Show details/links
   ```

3. **Positioning** (Lines 2710-2727):
   - All events: `position: absolute, left: 10px, right: 10px`
   - **No column layout** - all events use full width
   - **No overlap detection** - only z-index stacking (2 default, 10 on click)

4. **Real overlap example found**:
   - Day 1, 09:00-09:07: "Taxi to Huguang Guild Hall"
   - Day 1, 09:00-10:30: "Huguang Guild Hall"
   - Currently these stack with z-index only

## Recommended Implementation Approach

### Design Decisions

1. **Overlap layout: Google Calendar style (equal-width columns)**
   - Rationale: More predictable, easier to implement, better mobile compatibility
   - Algorithm: Interval scheduling with greedy column assignment
   - Width calculation: 100% / maxColumns per conflict group

2. **Text overflow: Two-tier adaptive layout**
   - **Block height ≥ 1 line but < 36px**: Keep text inside, force single line (no wrap), use ellipsis
   - **Block height < 1 line (~20px)**: Hide all text, show only colored bar with icon/dot on left
   - **Line height calculation**: Based on font size × 1.5 (mobile: 18px, desktop: 21px)

### Implementation Steps

#### Step 1: Add Overlap Detection Algorithm

**Location:** Before Line 2595 (before TimelineView component)

Add new function `computeColumnLayout(entries)`:

```javascript
/**
 * Compute column layout for overlapping timeline entries
 * Uses interval scheduling algorithm to assign non-overlapping columns
 */
const computeColumnLayout = (entries) => {
  // Parse times into minutes since midnight
  const timeToMinutes = (timeStr) => {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  };

  const entriesWithMinutes = entries.map(e => ({
    ...e,
    _startMin: timeToMinutes(e.time.start),
    _endMin: timeToMinutes(e.time.end)
  }));

  // Check if two events overlap
  const overlaps = (e1, e2) => {
    return (e1._startMin < e2._endMin) && (e2._startMin < e1._endMin);
  };

  // Greedy column assignment
  const result = [];
  for (let i = 0; i < entriesWithMinutes.length; i++) {
    const entry = entriesWithMinutes[i];
    const conflictingEntries = result.filter(e => overlaps(e, entry));
    const occupiedCols = new Set(conflictingEntries.map(e => e._column));

    let column = 0;
    while (occupiedCols.has(column)) column++;

    entry._column = column;
    result.push(entry);
  }

  // Calculate maxColumns for each conflict group
  for (let i = 0; i < result.length; i++) {
    const entry = result[i];
    const conflictingEntries = result.filter(e => overlaps(e, entry));
    const maxCol = Math.max(entry._column, ...conflictingEntries.map(e => e._column));
    entry._maxColumns = maxCol + 1;
  }

  return result;
};
```

**Validation:** Log first entry to verify `_column` and `_maxColumns` properties exist.

#### Step 2: Integrate Column Layout

**Location:** Line 2628 (after sorting)

```javascript
// Existing line 2628
entries.sort((a, b) => a.time.start.localeCompare(b.time.start));

// NEW: Add column layout
const entriesWithLayout = computeColumnLayout(entries);
```

#### Step 3: Update Rendering with Column-Based Positioning

**Location:** Lines 2692-2727

Changes required:

1. **Update map loop** (Line 2692):
   ```javascript
   // Change from: {entries.map((entry, i) => {
   // To:
   {entriesWithLayout.map((entry, i) => {
   ```

2. **Calculate column positioning and text visibility** (after Line 2696):
   ```javascript
   // NEW: Column-based width and position
   const hasColumns = entry._maxColumns > 1;
   const colWidth = hasColumns ? (100 / entry._maxColumns) : 100;
   const colLeft = hasColumns ? (entry._column * colWidth) : 0;

   // Text visibility logic based on pixel height
   const LINE_HEIGHT_PX = sm ? 18 : 21;  // Font size × 1.5
   const hideAllText = entryH < LINE_HEIGHT_PX;           // < ~20px: Icon only
   const forceOneLine = entryH >= LINE_HEIGHT_PX && entryH < 36;  // 20-35px: Single line
   ```

3. **Update positioning styles** (Line 2710):
   ```javascript
   <div key={i} style={{
     position: 'absolute',
     top: t,
     // CHANGE: Column-based positioning
     left: hasColumns ? `calc(10px + ${colLeft}%)` : '10px',
     width: hasColumns ? `calc(${colWidth}% - 12px)` : 'calc(100% - 20px)',
     height: entryH - 4,
     padding: hideAllText ? '0 6px' : (sm ? '8px 10px' : '10px 14px'),  // CHANGE
     alignItems: hideAllText ? 'center' : 'flex-start',  // CHANGE
     overflow: 'hidden',
     // ... rest unchanged
   ```

4. **Update text rendering with conditional visibility** (Line 2735-2750):
   ```javascript
   <div style={{ flex: 1, minWidth: 0 }}>
     {/* Hide time if text is hidden */}
     {!hideAllText && showTime && <div style={{ fontSize: '11px', color: '#b4b4b4' }}>
       {entry.time.start} – {entry.time.end}
     </div>}

     {/* Hide main text if too short */}
     {!hideAllText && showText && (
       <div style={{
         fontSize: sm ? '12px' : '14px',
         fontWeight: '600',
         color: '#37352f',
         whiteSpace: 'nowrap',  // Always nowrap (handles single-line requirement)
         overflow: 'hidden',
         textOverflow: 'ellipsis'
       }}>
         {/* ... existing content ... */}
       </div>
     )}

     {/* Subtext only if tall enough */}
     {!hideAllText && showSubtext && (
       <div>
         {/* ... existing details ... */}
       </div>
     )}
   </div>
   ```

#### Step 4: Icon Visibility (No changes needed)

**Note:** The colored dot icon at `left: '-8px'` (lines 2723-2727) remains **always visible** regardless of text visibility. This ensures even very short events (< 1 line height) show a visual indicator.

When `hideAllText === true`, the event block shows:
- Colored background bar (from `typeStyle`)
- Left border (3px solid/dashed)
- Colored dot icon (8px circle at left: -8px)
- **No text content**

This provides a minimal but informative visual representation for ultra-short events.

#### Step 5: Handle Edge Cases

**A. Zero-duration events** (Line 2650):
```javascript
const hgt = (s, e) => {
  const raw = rawHgt(s, e);
  if (raw === 0) return 12; // Zero-duration marker
  return Math.max(raw, 8);
};
```

**B. 5+ overlapping events** (in computeColumnLayout):
```javascript
if (entry._maxColumns > 5) {
  console.warn(`Timeline: ${entry._maxColumns} overlapping events. Consider reviewing schedule.`);
  // Optional: cap at 5 columns for readability
}
```

**C. Mobile adjustments**: Already included in external label positioning (sm ? '100%' : 'calc(100% + 12px)')

## Critical Files to Modify

1. **`/root/travel-planner/scripts/generate-html-interactive.py`** (Lines 2590-2800)
   - Insert `computeColumnLayout` function (before Line 2595)
   - Integrate column layout (Line 2628)
   - Update rendering loop and positioning (Lines 2692-2727)
   - Add external label rendering (after Line 2792)
   - Add zero-duration handling (Line 2650)

## Verification Plan

### Manual Testing Steps

1. **Generate updated HTML**:
   ```bash
   python3 scripts/generate-html-interactive.py china-feb-15-mar-7-2026 \
     --data-dir data/agent-test-20260212-191529 \
     --output output/test-timeline-improvements.html
   ```

2. **Open in browser**: `output/test-timeline-improvements.html`

3. **Test overlapping events**:
   - Navigate to Day 1
   - Verify 09:00 taxi and Huguang Hall display **side-by-side** (not stacked)
   - Verify equal column widths (approximately 50% each)
   - Click each event to verify both are accessible

4. **Test short duration events (height >= line-height but < 36px)**:
   - Look for 5-15 minute events
   - Verify text shows **inside block** on single line with ellipsis
   - Verify time text still shows if height >= 24px

5. **Test very short blocks (< line-height ~20px)**:
   - Look for 2-minute walk events (should be < 20px height)
   - Verify **no text appears** at all
   - Verify **colored bar** with **icon/dot on left** is visible
   - Verify block is still clickable

6. **Test mobile view**:
   - Resize browser to mobile width (< 768px)
   - Verify line height threshold uses 18px instead of 21px
   - Verify columns still work correctly

7. **Test edge cases**:
   - Look for 3+ overlapping events (verify 33% width each)
   - Test zero-duration events (should show 12px marker)
   - Verify images still show when space allows

### Browser DevTools Checks

1. **Inspect overlapping events**:
   - Verify `left` property uses calc() with percentage
   - Verify `width` property matches expected column width
   - Verify `_column` and `_maxColumns` properties in React DevTools

2. **Performance check**:
   - Open Performance tab
   - Record timeline view rendering
   - Verify < 100ms render time

3. **Console check**:
   - Look for warnings about 5+ overlapping events (if applicable)
   - Verify no JavaScript errors

### Expected Behavior

**Before changes:**
- Overlapping events stack (z-index only)
- Short events show truncated text inside block with wrap
- Very short events (< 16px) show nothing

**After changes:**
- Overlapping events display side-by-side in equal columns
- Short events (>= 1 line, < 36px) show single-line text inside with ellipsis
- Very short events (< 1 line ~20px) show only colored bar + icon, no text
- All events remain clickable and interactive
- Mobile view uses 18px threshold instead of 21px

## Rollback Plan

If issues occur, revert by:
1. Remove `computeColumnLayout` call (Line 2629)
2. Change `entriesWithLayout.map` back to `entries.map` (Line 2692)
3. Restore `left: '10px', right: '10px'` (Line 2711)
4. Remove external label conditional block

All changes are isolated to TimelineView component (Lines 2590-2800).

## Performance & Complexity

- **Algorithm complexity**: O(n²) per day where n = events (typically 10-30, acceptable)
- **Rendering impact**: Minimal (added CSS calc(), ~10-20 extra divs for labels)
- **No breaking changes**: All existing features preserved (clicks, hovers, type styling, images)

## Future Enhancements (Out of Scope)

- Drag-and-drop event rescheduling
- Customizable column width ratios (e.g., main event 60%, travel 20%)
- Vertical text for very narrow columns
- Tooltip hover for truncated text
- Smart label collision detection
