---
status: complete
priority: p1
issue_id: "173"
tags: [validation, medallion, pandera, health]
dependencies: ["143"]
---

# Implement Layered Pandera Schemas for Medallion Health

## Problem Statement
To ensure data integrity across the Medallion pipeline, we need strict schema enforcement at each stage. Without validation, silent failures or TradingView API changes can "poison" the Iceberg tables with corrupt data.

## Findings
- Pandera is excellent for vectorized validation of Arrow-backed DataFrames.
- We need three distinct schemas to handle the evolution from raw to scored data.

## Proposed Solutions
1. **BronzeSchema**: Validates raw capture (supports raw API names).
2. **SilverSchema**: Strict. Enforces canonical names and non-nullable technical columns.
3. **GoldSchema**: Validates derived features and risk metadata.

## Recommended Action
Implement the contract classes in `tvscreener/lib/lakehouse/health.py` and enforce them during stage transitions.

## Acceptance Criteria
- [ ] Pandera schemas defined for all 3 Medallion layers.
- [ ] Validates types, required columns, and value ranges (e.g., scoring in [-1, 1]).
- [ ] Fails loudly with descriptive error messages on validation breach.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Data Cleansing and Validation" audit.
