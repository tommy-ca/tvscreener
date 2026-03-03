---
status: complete
priority: p2
issue_id: "187"
tags: [architecture, refactoring, medallion, pipeline]
dependencies: []
---

# Simplify "Bureaucratic" Pipeline Abstractions

## Problem Statement

The `pipeline.py` file contains stateless `Ingestor`, `Standardizer`, and `Scorer` classes that only serve to call private methods on the screener. This represents unnecessary enterprise "framework contamination", complicating the architecture without adding functional value or reusability.

## Findings

- `Ingestor`, `Standardizer`, and `Scorer` in `pipeline.py` act as hollow abstractions.
- These classes only exist to pass state back to private methods on `BaseOpportunityScreener`.
- The pipeline execution could be simplified into a procedural flow directly inside the screener base class.

## Proposed Solutions

### Option 1: Procedural Medallion Execution

**Approach:** Delete the `Ingestor`, `Standardizer`, and `Scorer` classes. Move the Medallion execution logic (Bronze/Silver/Gold flow) directly into procedural methods within `BaseOpportunityScreener`.

**Pros:**
- Greatly simplifies the codebase by removing "bureaucratic" abstractions.
- Reduces cognitive load for developers navigating the architecture.
- Improves code readability by keeping related Medallion logic consolidated.

**Cons:**
- Requires refactoring how pipelines are initialized and invoked.

**Effort:** 2-3 hours
**Risk:** Low / Medium (Requires ensuring all screener subclasses adapt to the streamlined flow)

## Recommended Action

Implement Option 1. Delete the redundant stateless classes and refactor the orchestration into `BaseOpportunityScreener`.

## Technical Details

**Affected files:**
- `tvscreener/pipeline.py` (Delete or strip out hollow classes)
- `tvscreener/screener/base.py` (Move execution logic here)

**Related components:**
- Medallion pipeline execution
- All screener subclasses inheriting from `BaseOpportunityScreener`

## Resources

- General code hygiene and YAGNI (You Aren't Gonna Need It) principles

## Acceptance Criteria

- [ ] `Ingestor`, `Standardizer`, and `Scorer` classes are removed.
- [ ] Procedural Medallion execution logic is embedded directly in `BaseOpportunityScreener`.
- [ ] Pipeline runs seamlessly from end to end.
- [ ] Tests pass when executing `uv run pytest`.

## Work Log

### 2026-03-03 - Initial Creation

**By:** Claude Code

**Actions:**
- Created todo from issue findings.
