# Plan: Portfolio-Hedging Agent Refactor — Textbook → Scripts

## Context

The portfolio-hedging agent (`/.claude/agents/portfolio-hedging.md`, 1595 lines) has two critical problems:
1. **No data access** — `allowed-tools: Read, Write, Bash, Grep, Glob` (no WebSearch, no data-fetch scripts). It relies entirely on whatever the orchestrator feeds it, leading to stale/wrong conclusions (e.g., assumed "cutting cycle" when Fed was actually holding).
2. **Textbook formulas in prompt** — VaR, correlation, beta, HHI, stress testing are written as pseudocode examples (~600 lines). These waste tokens and produce no real calculations.

**Goal**: Convert the agent from a "textbook advisor" into a "computational analyst" with real Python scripts and self-service data access.

## Changes

### 1. Create risk calculation scripts

Create **one unified script** at `.claude/skills/risk-analysis/scripts/portfolio_risk.py` with subcommands:

```
portfolio_risk.py correlation --tickers "V,IBKR,SCHD,GLD" --period 1y --output data/risk/correlation.json
portfolio_risk.py var --portfolio portfolio/holdings.json --confidence 95 --output data/risk/var.json
portfolio_risk.py beta --tickers "V,IBKR" --benchmark SPY --period 1y --output data/risk/beta.json
portfolio_risk.py concentration --portfolio portfolio/holdings.json --output data/risk/concentration.json
portfolio_risk.py stress-test --portfolio portfolio/holdings.json --scenarios all --output data/risk/stress.json
```

Implementation:
- Use FMP historical price API for returns data (already available via `fetch_equity.py` pattern)
- `correlation`: Pearson + 60-day rolling, using `numpy.corrcoef` and `pandas.rolling().corr()`
- `var`: Parametric (normal) + historical simulation, using `numpy.percentile`
- `beta`: `scipy.stats.linregress` against benchmark
- `concentration`: HHI + sector/geography breakdown from holdings.json
- `stress-test`: Apply predefined shocks (market -20%, rates +100bp, etc.) to portfolio weights × betas

Output: JSON files in `data/risk/` that the agent reads.

**Key files to reference**:
- `.claude/skills/data-fetch/scripts/fetch_equity.py` — FMP API pattern, env loading
- `.claude/skills/macro-data-analysis/scripts/fetch_indicators.py` — FRED API pattern
- `scripts/utilities/hedging_engine.py` — existing partial correlation logic (lines 401-470)

### 2. Slim down the agent prompt

Reduce from ~1595 lines to ~400 lines by:

**Remove** (lines to delete):
- Lines 873-955: Risk Calculation Methodologies section (VaR, correlation, beta, HHI formulas) → replaced by scripts
- Lines 957-1042: Hedging Heuristics pseudo-code → replaced by scripts
- Lines 625-866: Full asset class coverage encyclopedia (equity, FI, FX, commodities, alternatives, derivatives, multi-asset, cash detailed descriptions) → agent already knows these, prompt just wastes tokens
- Lines 1043-1210: Long example JSONs (Example 1, 2, 3) → keep ONE short example, remove the other two

**Add**:
- Data Fetch Capability section (copy pattern from review.md lines 172-177)
- Risk Scripts section listing available scripts with usage
- WebSearch to `allowed-tools` for macro context verification

**Keep**:
- Mission & Core Responsibilities (lines 74-170): dedup, correlation, hedge discovery, risk aggregation, typed relations
- JSON Output Schema (lines 436-616): the structured output format
- V2 Workflow (lines 18-70): latest-strategy-only logic
- Important Rules (lines 1542-1553)
- ONE example (keep Example 3: Gold futures, remove Examples 1 & 2)

### 3. Update allowed-tools

```yaml
allowed-tools: Read, Write, Bash, Grep, Glob, WebSearch
```

Adding WebSearch so the agent can verify macro context (Fed decisions, breaking news) instead of blindly trusting orchestrator input.

### 4. Add skill README

Create `.claude/skills/risk-analysis/README.md` documenting the new skill.

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `.claude/skills/risk-analysis/scripts/portfolio_risk.py` | CREATE | Unified risk calculation script |
| `.claude/agents/portfolio-hedging.md` | EDIT | Slim prompt, add data-fetch + script references |
| `.claude/skills/risk-analysis/README.md` | CREATE | Skill documentation |

## Verification

1. Run each subcommand of `portfolio_risk.py` against the current portfolio:
   ```
   source ~/.claude/venv/bin/activate
   python3 .claude/skills/risk-analysis/scripts/portfolio_risk.py correlation --tickers "V,IBKR,SCHD,GLD" --period 1y
   python3 .claude/skills/risk-analysis/scripts/portfolio_risk.py var --portfolio portfolio/holdings.json --confidence 95
   python3 .claude/skills/risk-analysis/scripts/portfolio_risk.py concentration --portfolio portfolio/holdings.json
   ```
2. Invoke the hedging agent with the same IBKR+V question and verify it:
   - Fetches current prices itself (via data-fetch scripts)
   - Runs correlation/VaR scripts
   - Produces JSON with real numbers, not textbook estimates
3. Confirm prompt is under 500 lines (from 1595)
