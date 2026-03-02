---
status: completed
priority: p3
issue_id: "087"
tags: [simplification, configuration]
dependencies: []
---

# Simplification: Configuration hierarchy depth

Flatten configuration layers and remove redundant prefixes.

## Problem Statement

The configuration system has multiple layers (YAML, ENV, CLI, Pydantic defaults) and significant internal nesting (e.g., many fields in `ScreenerSettings` have the `opportunity_` prefix). This depth makes it difficult to trace the final value of a setting and increases maintenance overhead.

## Findings

- **Files:** `tvscreener/config/settings.py`, `tvscreener/config/loader.py`
- `ScreenerSettings` currently mixes general settings with screener-specific settings using prefixes.
- Some settings are duplicated between "general" and "opportunity" versions (e.g., `min_volume` vs `opportunity_min_volume`).

## Proposed Solutions

### Option 1: Flatten and Unify

**Approach:** Flatten the settings into a single logical structure or use clear sub-models (Pydantic nested classes) instead of string prefixes.

**Pros:**
- Better IDE auto-completion
- Easier to audit configuration files
- Reduces "magic" naming conventions

**Cons:**
- May require breaking changes to ENV variable names if they follow the old prefix

**Effort:** 2-3 hours

**Risk:** Medium (must ensure all consumers of settings are updated)

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/config/settings.py`
- `tvscreener/config/loader.py`
- `tvscreener/core/base.py`
- `tvscreener/lib/screeners/forex_opportunity.py`

## Acceptance Criteria

- [x] Configuration layers are flattened where possible
- [x] Redundant `opportunity_` prefixes removed or moved to sub-models
- [x] ENV variable mapping remains consistent or is clearly documented as changed

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Audited `ScreenerSettings` for redundancy
- Identified prefix duplication

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Refactored `ScreenerSettings` to use nested `OpportunitySettings` and `RiskSettings` models.
- Removed redundant prefixes (`opportunity_`, `risk_`) from field names in nested models.
- Updated `load_settings` in `loader.py` to handle the new nested structure while maintaining backward compatibility for flat YAML/ENV.
- Updated `orchestrator.py` to use the new nested attribute access.
- Updated `tvscreener.yaml` to follow the new nested logical structure.
- Updated `DummySettings` in unit tests to match the new structure.
- Added `pip_value` to `ScreenerConfig` in `base.py` for better risk management consistency.

---
