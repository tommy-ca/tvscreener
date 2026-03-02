---
status: complete
priority: p2
issue_id: "112"
tags: [security, parser, code-review]
dependencies: ["105"]
---

# MTF Expression Parser Lacks SQL Injection Guards

## Problem Statement

`MTFExpressionParser.parse()` in `parser.py` only translates timeframe prefixes (`1H:RSI` -> `RSI_60`). It performs zero sanitization of the rest of the expression. The result is interpolated directly into SQL via `SELECT * FROM df WHERE {sql_expr}`. Users can inject semicolons, COPY statements, etc.

Additionally, the plan called for `pyparsing` for nested boolean logic, but the implementation uses regex which cannot handle parenthesized expressions.

## Findings

- `tvscreener/lib/screeners/parser.py:40` — Regex pattern only matches `TF:FACTOR`, passes everything else verbatim
- `tvscreener/lib/orchestrator.py:327,379` — Parser output interpolated directly into SQL string
- Exploit: `--filter "1H:RSI > 0; COPY (SELECT * FROM df) TO '/tmp/exfil.csv' --"`
- Regex `\b([A-Za-z0-9]+):([A-Za-z0-9_]+)\b` cannot handle nested `(A AND (B OR C))` correctly

## Proposed Solutions

### Option 1: Add Input Validation (Quick)

**Approach:** Reject expressions containing semicolons, `--`, `/*`, and DDL keywords (COPY, INSTALL, LOAD, CALL, CREATE, DROP, ALTER, ATTACH).

**Effort:** 15 minutes
**Risk:** Low

### Option 2: Implement pyparsing AST (Comprehensive)

**Approach:** Replace regex with pyparsing as the plan specified. Build a proper AST that only generates safe SQL.

**Effort:** 2-3 hours
**Risk:** Medium

## Recommended Action

**Option 1 — Quick input validation.** Reject expressions containing semicolons, `--`, `/*`, and DDL keywords. Combine with #105 sandbox for defense in depth. Defer pyparsing to a future iteration.

## Acceptance Criteria

- [ ] Semicolons in filter expressions are rejected
- [ ] DDL keywords (COPY, INSTALL, etc.) are rejected
- [ ] Nested parenthesized expressions work correctly
- [ ] Existing filter tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (security-sentinel, python-reviewer)
