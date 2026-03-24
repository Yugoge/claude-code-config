# Fix: Three-Statement Reconciliation (三表联动)

## Context
The three financial statements (Income Statement, Balance Sheet, Cash Flow) are currently computed independently. While IS net income and CF net operating cash flow happen to be numerically equal (both exclude financing), the Balance Sheet is disconnected — it just shows raw cash balances from `monthly.endBalance` with no connection to IS or CF.

**Goal**: Make the three statements properly articulate:
1. IS Net Income = CF Net Operating Cash Flow (already true, just make explicit)
2. BS should show: Opening Net Worth + IS Net Income + CF Net Financing = Closing Net Worth
3. CF Opening Balance = Previous period's BS Closing Balance
4. CF Closing Balance = Opening + Net Change (derived, not looked up)

## Current State Analysis

**What's already correct:**
- IS excludes financing (Bank Transfers, Currency Exchange, Cash Withdrawal) via `isFinancingTransaction()`
- CF splits operating vs financing correctly using same filter
- IS Net Income = CF Net Operating (identical transaction filter)

**What's broken:**
- BS `buildBalanceSheet()` (line 162-183): Just returns `monthly.endBalance` as cash/assets/netWorth. No connection to IS/CF.
- CF closing balance (line 214): Looked up from `monthly.endBalance` instead of derived from opening + net change.
- No cross-validation between statements.

## Changes

### 1. `report-aggregation.ts` — Fix `buildBalanceSheet()`

Current: Takes only `monthly` + `columns`, returns independent snapshots.

New: Takes `transactions` + `monthly` + `columns`, computes:
```
For each period:
  openingNetWorth = previous period's closingNetWorth (or first monthly.endBalance minus first period's net change)
  operatingCashFlow = IS net income (revenue - expenses, excl financing)
  financingCashFlow = financing inflows - outflows
  closingNetWorth = openingNetWorth + operatingCashFlow + financingCashFlow
```

Output adds new rows:
```
ASSETS
  Cash & Bank Accounts          (= closingNetWorth, derived)
  Total Assets

LIABILITIES
  Total Liabilities             (= 0)

EQUITY
  Opening Net Worth
  + Net Income (from IS)        (= operating cash flow)
  + Net Financing               (= financing cash flow)
  Closing Net Worth             (= opening + netIncome + netFinancing)
```

This makes BS explicitly show how IS and CF drive net worth changes.

### 2. `report-aggregation.ts` — Fix `buildCashFlowStatement()` closing balance

Current (line 214): `closingBalance = monthsInPeriod[monthsInPeriod.length - 1]?.endBalance ?? 0`
New: `closingBalance = openingBalance + netOperating + netFinancing` (derived from cash flows, not looked up)

Keep opening balance logic as-is (look up from prior month's endBalance), but derive closing from it.

### 3. `BalanceSheet.tsx` — Pass transactions, update table rows

Current: Only passes `monthly` to `buildBalanceSheet()`.
New: Also pass `transactions`. Update `tableRows` to include the new Equity section rows.

### 4. `budget.ts` — Update `BalanceSheetSnapshot` type

Add fields:
```typescript
export interface BalanceSheetSnapshot {
  period: PeriodColumn;
  cashBalance: number;
  totalAssets: number;
  totalLiabilities: number;
  netWorth: number;
  openingNetWorth: number;
  netIncome: number;       // from IS (operating cash flow)
  netFinancing: number;    // from CF (financing cash flow)
}
```

## File Summary
| Action | File |
|--------|------|
| Modify | `frontend/src/lib/report-aggregation.ts` (buildBalanceSheet, buildCashFlowStatement) |
| Modify | `frontend/src/components/reports/BalanceSheet.tsx` (pass transactions, new equity rows) |
| Modify | `frontend/src/types/budget.ts` (BalanceSheetSnapshot) |

## Reconciliation Logic (三表联动)
```
IS:  Net Income = Revenue - Expenses (excl financing)
CF:  Net Operating = Income - Expenses (excl financing) = IS Net Income
CF:  Net Change = Net Operating + Net Financing
CF:  Closing = Opening + Net Change
BS:  Closing Net Worth = Opening Net Worth + Net Income + Net Financing
BS:  Closing Net Worth = CF Closing Balance
```

## Verification
1. `npx tsc --noEmit` — zero errors
2. `npm run build` — success
3. Browser QA on Reports page:
   - BS Closing Net Worth for each period = CF Closing Balance
   - BS Net Income row = IS Net Income row (same numbers)
   - BS Opening + Net Income + Net Financing = Closing (each period)
   - CF Closing = Opening + Net Change (each period)
4. Deploy and verify live
