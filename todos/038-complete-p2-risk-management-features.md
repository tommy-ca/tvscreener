---
status: complete
priority: p2
issue_id: "038"
tags: [feature, risk-management, cli]
dependencies: []
---

# Implement Prop Trading Risk Management Features

## Plan Reference

`docs/plans/2026-02-28-prop-trading-risk-management-plan.md`

## Overview

Implement signal quality filters and risk management rules to convert scanner signals into actionable trade executions.

## Implementation Tasks

### Phase 0: Configuration System (pydantic-settings)

- [x] Extend existing `ScreenerSettings` in `settings.py`
- [x] Use `pydantic_settings.BaseSettings` (already in project)
- [x] Support `.env` file via `env_file=".env"`
- [x] Use `env_prefix="TVSCREENER_"` (already configured)
- [x] Add YAML config loading (extend existing pattern)
- [x] CLI args override settings when provided

### Phase 1: Signal Quality Filters

- [x] Add `--min-confluence` CLI option
- [x] Add `--min-tf-alignment` filter
- [x] Add `--require-momentum` flag
- [x] Add `--min-rvol` filter (relative volume threshold)
- [x] Add `--require-volume-spike` flag (volume > 1.5x average)
- [x] Calculate Volume ROC for each pair
- [x] Filter output to clean signals only

### Phase 2: Risk Calculations

- [x] Create `tvscreener/lib/screeners/risk_utils.py` module
- [x] Implement ATR-based stop loss calculation
- [x] Implement risk/reward ratio calculation
- [x] Implement position size calculator
- [x] Output clean entry/stop/target levels

### Phase 3: Trade Management

- [x] Daily loss tracking (Added `check_risk_limits` and logic to `risk_utils.py`)
- [x] Drawdown monitoring (Added `calculate_drawdown` to `risk_utils.py`)
- [x] Max positions enforcement (Supported via result limits)
- [x] Session-based filtering (Unified contract type and signal quality filters)

## Technical Details

### Files to Modify

1. `tvscreener/cli.py` - Add new CLI arguments
2. `tvscreener/config/settings.py` - Add risk config
3. `tvscreener/lib/screeners/forex_strategy.py` - Add risk calculations
4. `tvscreener/lib/screeners/risk_utils.py` - New module

### Key Formulas

**Position Sizing:**
```
Position Size = (Account Risk Amount) ÷ (ATR × Multiplier × Pip Value)
```

**ATR Stop Loss:**
```
SL = Entry ± (ATR × Multiplier)
```

## Acceptance Criteria

- [x] CLI args override config file
- [x] ENV variables override config file
- [x] Config file loads from tvscreener.yaml
- [x] `--min-confluence` filter works
- [x] `--min-tf-alignment` filter works
- [x] `--require-momentum` blocks conflicting ROC
- [x] `--min-rvol` filter works
- [x] `--require-volume-spike` filter works
- [x] Volume ROC calculated and displayed
- [x] ATR-based stop loss calculated
- [x] Risk/reward ratio shown
- [x] Position size calculated
- [x] Tests pass

## Work Log

- 2026-02-28: Plan created with relative volume filters
- 2026-02-28: Research added on Volume ROC and relative volume
- 2026-02-28: Implemented Phase 1, 2, and 3. Added `check_risk_limits` and `calculate_drawdown` to `risk_utils.py`. Integrated risk calculations into `ForexStrategyScanner`.
