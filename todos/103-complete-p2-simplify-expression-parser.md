---
status: complete
priority: p2
issue_id: "103"
tags: [simplicity, refactor, mtf]
dependencies: []
---

# Simplify MTF Expression Parser (Drop PyParsing)

## Problem Statement
The plan proposed using `pyparsing` to build an AST parser to handle nested boolean logic (e.g., `(1D:RSI < 30 OR 4H:TREND > 0)`). This is a massive over-engineering violation because DuckDB's SQL engine already parses boolean logic perfectly.

## Findings
- Code Simplicity Reviewer correctly identified that we do not need to parse the AST. We only need to translate the *variable names* (e.g., `1D:RSI` -> `RSI_1440`). 
- A simple regex string substitution accomplishes this in 3 lines of code without adding any external dependencies.

## Proposed Solutions

### Option 1: Regex String Substitution
**Approach:** 
Drop the `pyparsing` requirement. Implement `MTFExpressionParser` using `re.sub` to dynamically map `{TIMEFRAME}:{FACTOR}` shorthand to valid SQL column names `{FACTOR}_{MINUTES}`, leaving the parentheses and AND/OR keywords intact for DuckDB to parse natively.

## Acceptance Criteria
- [x] `MTFExpressionParser` translates `1D:RSI < 30 AND (4H:TREND > 0)` to `RSI_1440 < 30 AND (TREND_240 > 0)`.
- [x] No AST parsing dependencies (`pyparsing`, `lark`, etc.) are added to the project.

## Work Log

### 2026-03-01 - Verification Session

**By:** Claude Code

**Actions:**
- Reviewed `tvscreener/lib/screeners/parser.py` to confirm it uses `re.compile` and `re.sub` for string replacement.
- Grepped the project for `pyparsing` and confirmed no references exist outside of markdown documentation and this todo.
- Verified no AST dependencies were added.

**Learnings:**
- Subagent successfully implemented the regex-based `MTFExpressionParser` without relying on `pyparsing`.