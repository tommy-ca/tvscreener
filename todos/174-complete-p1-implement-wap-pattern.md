---
status: complete
priority: p1
issue_id: "174"
tags: [architecture, medallion, health, reliability]
dependencies: ["173", "147"]
---

# Implement Write-Audit-Publish (WAP) Pattern

## Problem Statement
Currently, data is written to Iceberg immediately after processing. If a bug exists in the scoring logic, invalid signals are committed. We need a "Circuit Breaker" to prevent corrupt data from reaching the Gold layer.

## Findings
- WAP Pattern: `Compute -> Audit -> Publish`.
- For a local CLI, an in-memory audit via Pandera before `write_iceberg` is sufficient.

## Proposed Solutions
1. **Audit Hook**: Wire `_validate_health()` into `BaseOpportunityScreener._resume_or_run`.
2. **Commit Blocker**: If `_validate_health()` raises an error, the Iceberg commit is skipped, and the CLI exits with an error.

## Recommended Action
Integrate the health check as a mandatory pre-commit hook in the Medallion pipeline.

## Acceptance Criteria
- [ ] `_validate_health` runs after every compute stage.
- [ ] Invalid data prevents Iceberg persistence.
- [ ] Audit results are logged to the console in verbose mode.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Data Cleansing and Validation" audit.
