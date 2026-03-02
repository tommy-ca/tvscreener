---
status: complete
priority: p1
issue_id: "070"
tags: [strategy, orchestrator, display]
dependencies: []
---

# Unify print_summary() signature across scanners

## Problem Statement

The opportunity scanner's `print_summary(detailed, matrix)` and the strategy scanner's `print_summary(limit)` have incompatible signatures. The orchestrator (`run_strategy_scan()` at orchestrator.py:314) calls `scanner.print_summary()` without passing `detailed` or `matrix`, so these CLI flags are silently ignored for strategy scans.

## Findings

- `ForexOpportunityScreener.print_summary(detailed: bool = False, matrix: bool = False)`
- `ForexStrategyScanner.print_summary(limit: int = 20)`
- `BaseOpportunityScreener.print_summary(**kwargs)` — abstract, accepts any kwargs
- Orchestrator calls:
  - Opportunity: `screener.print_summary(detailed=request.detailed, matrix=request.matrix)` ✅
  - Strategy: `scanner.print_summary()` ❌ — doesn't pass flags

## Proposed Solutions

### Option 1: Update strategy scanner signature to match (Recommended)

**Approach:** Change `ForexStrategyScanner.print_summary()` to accept `detailed` and `matrix` kwargs (with defaults=False). Update the orchestrator to pass these through.

**Pros:**
- Simple, targeted fix
- Enables todos 068 and 069 to work end-to-end

**Cons:**
- `limit` parameter still strategy-only (minor inconsistency)

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Update both `ForexStrategyScanner.print_summary()` signature and `ScreenerController.run_strategy_scan()` to pass `detailed`/`matrix`.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_strategy.py:645` — update `print_summary()` signature
- `tvscreener/lib/orchestrator.py:314` — pass `detailed=request.detailed, matrix=request.matrix`

## Acceptance Criteria

- [x] `ForexStrategyScanner.print_summary()` accepts `detailed` and `matrix` kwargs
- [x] Orchestrator passes `detailed` and `matrix` to strategy scanner
- [x] `--detailed` and `--matrix` CLI flags affect strategy output
- [x] Default behavior (no flags) unchanged
- [x] All existing tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Identified signature mismatch between opportunity and strategy scanners
- Traced orchestrator call paths for both scanners

### 2026-03-01 - Resolution

**By:** Antigravity

**Actions:**
- Updated `ForexStrategyScanner.print_summary()` signature in `forex_strategy.py` to accept `detailed` and `matrix`.
- Updated `ScreenerController.run_strategy_scan()` in `orchestrator.py` to pass `detailed` and `matrix` flags.
- Verified unit and functional tests pass.
- Marked todo as complete.
