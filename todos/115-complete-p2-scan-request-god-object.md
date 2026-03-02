---
status: complete
priority: p2
issue_id: "115"
tags: [architecture, maintainability, code-review]
dependencies: []
---

# ScanRequest God Object With 40+ Fields

## Problem Statement

`ScanRequest` dataclass in `orchestrator.py` has 40+ flat fields mixing routing, filters, scoring, risk, strategy, and output concerns. Every new parameter requires changes in 4+ places: ScanRequest, cli.py argparse, resolve_defaults(), config builder, and MCP tools.

## Findings

- `tvscreener/lib/orchestrator.py:54-118` — 65-line flat dataclass
- `tvscreener/lib/orchestrator.py:145-217` — 70-line `resolve_defaults()` with manual None checks
- Fields span 6 concern areas: routing(2), symbol resolution(4), filters(4), scoring(7), strategy(13), risk(5), output(10)

## Proposed Solutions

### Option 1: Decompose into Nested Dataclasses

**Approach:** Create `FilterParams`, `RiskParams`, `StrategyParams`, `OutputParams` sub-dataclasses.

**Effort:** 2-3 hours
**Risk:** Medium (touches many call sites)

### Option 2: Keep Flat, Document Sections

**Approach:** Add section comments and a builder pattern.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Option 2 — Keep flat, add section comments + builder.** Decomposition is high-risk for a feature branch. Add clear section comments and a builder/factory method to reduce call-site complexity. Revisit decomposition post-merge.

## Acceptance Criteria

- [ ] Adding a new parameter requires changes in <= 2 files
- [ ] resolve_defaults() is simplified

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (architecture-strategist, python-reviewer, code-simplicity-reviewer)
