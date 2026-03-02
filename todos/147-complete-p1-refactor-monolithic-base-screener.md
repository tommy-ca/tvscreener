---
status: complete
priority: p1
issue_id: "147"
tags: [architecture, medallion, pipeline]
dependencies: ["146", "135"]
---

# Refactor Monolithic Base Screener into Medallion Stages

## Problem Statement
`base.py` currently executes ingestion, standardization, and scoring in one continuous block. This is not "Lakehouse-ready" and lacks checkpointing.

## Findings
- `get_opportunities()` is the entry point for scanning.
- We need distinct commits for `Bronze`, `Silver`, and `Gold` layers.

## Proposed Solutions
1. **Medallion Logic**: refactor `get_opportunities` to use checkpointed stages:
   - **Stage 1 (Bronze)**: API -> `_ingest()` -> Write raw TV schema to `tvscreener.bronze`.
   - **Stage 2 (Silver)**: `_standardize()` -> Read `bronze`, deduplicate, normalize columns (`trend_{tf}`), fill nulls -> Write to `tvscreener.silver`.
   - **Stage 3 (Gold)**: `_score()` -> Read `silver`, compute indicators/scores/risk -> Write to `tvscreener.gold`.
2. **Backend Agnosticism**: Use `narwhals` for all Stage 2 and Stage 3 transformations.

## Recommended Action
Implement the stage-based pipeline in `BaseOpportunityScreener`.

## Acceptance Criteria
- [ ] `_fetch_all_data` persists raw data to `tvscreener.bronze`.
- [ ] `_standardize` produces a clean dataset in `tvscreener.silver` with canonical column names.
- [ ] `_rank_opportunities` and strategy signals are persisted to `tvscreener.gold`.
- [ ] Pipeline can skip `Stage 1` if recent `Bronze` data exists in the Iceberg table.
- [ ] All transformation logic is backend-agnostic (Pandas/Polars) via Narwhals.

## Work Log
### 2026-03-02 - Task Created
- Part of Iceberg Lakehouse migration.
