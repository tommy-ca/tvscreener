---
status: complete
priority: p1
issue_id: "161"
tags: [correctness, risk-management, forex]
dependencies: []
---

# Fix Hardcoded Pip Value for JPY and Non-USD Pairs

## Problem Statement

The risk management utility `risk_utils.py` uses a hardcoded pip value of 10.0. This is incorrect for JPY pairs (which typically use 0.01 for a pip instead of 0.0001) and potentially other non-USD quote currencies. This leads to incorrect position sizing and risk calculations.

## Findings

- `risk_utils.py`: Hardcoded `10.0` value used in pip/risk calculations.
- JPY pairs (e.g., USD/JPY, EUR/JPY) require different pip value logic.
- Current logic assumes 4/5 decimal place pricing for all instruments.

## Proposed Solutions

### Option 1: Implement a Lookup Table/Dictionary

**Approach:** Create a mapping of currency pairs or quote currencies to their respective pip values.

**Pros:**
- Simple to implement.
- Fast lookup.

**Cons:**
- Needs maintenance for new instruments.

**Effort:** 1 hour

**Risk:** Low

---

### Option 2: Dynamic Pip Calculation

**Approach:** Calculate the pip value based on the number of decimal places provided by the data source or by checking the quote currency (e.g., if 'JPY' in pair, use 0.01).

**Pros:**
- More robust for wide variety of instruments.

**Cons:**
- Slightly more complex logic.

**Effort:** 2 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `risk_utils.py` - Pip calculation logic.

## Acceptance Criteria

- [x] JPY pairs calculate risk and position size correctly.
- [x] Non-USD pairs (GBP, EUR, etc.) calculate risk correctly.
- [x] Hardcoded `10.0` value is removed and replaced with dynamic/lookup logic.
- [x] Unit tests added for USD, JPY, and other major quote currencies, verified with `uv run pytest`.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo based on correctness finding in risk utilities.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Implemented `get_pip_size` utility in `risk_utils.py`.
- Updated `calculate_position_size` to handle dynamic pip sizes.
- Enhanced `RiskEngine.apply` to automatically detect pip sizes and support optional `PIP_VALUE` column.
- Added comprehensive unit tests in `tests/unit/test_risk_utils_jpy.py`.
- Verified all tests pass with `uv run pytest`.
