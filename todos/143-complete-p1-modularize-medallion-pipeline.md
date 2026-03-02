---
status: complete
priority: p1
issue_id: "143"
tags: [architecture, narwhals, pipeline]
dependencies: ["135", "142"]
---

# Modularize Medallion Pipeline (Bronze/Silver/Gold)

## Problem Statement
The current scanner logic (`base.py`) is monolithic. It fetches, standardizes, and scores in a single execution flow. This prevents re-running specific stages (e.g., re-scoring without re-fetching) and makes the system fragile.

## Findings
- `_fetch_all_data` handles ingestion and some standardization.
- `get_opportunities` coordinates the whole flow.
- Narwhals abstraction (Task 135) provides the necessary compute agnosticism.

## Proposed Solutions
1. **Pipeline Decoupling**: Split `BaseOpportunityScreener` into three distinct stages:
   - `Ingestor (Bronze)`: API -> Delta.
   - `Standardizer (Silver)`: Delta -> Narwhals -> Delta.
   - `Scorer (Gold)`: Delta -> Narwhals -> Delta.
2. **Orchestration**: Update `ScreenerController` to allow running specific pipeline segments.

## Recommended Action
Refactor `base.py` to use a checkpointed Medallion approach. Each stage reads from the previous stage's Delta table and writes to its own.

## Acceptance Criteria
- [ ] Pipeline can be resumed from `Silver` if `Gold` fails.
- [ ] Every stage is backend-agnostic (Pandas/Polars) via Narwhals.
- [ ] Log output clearly indicates Medallion state transitions.

## Work Log
### 2026-03-02 - Task Created
- Transitioning to Lakehouse Medallion Pipeline.
