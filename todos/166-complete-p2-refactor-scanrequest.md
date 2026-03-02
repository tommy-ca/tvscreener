---
status: complete
priority: p2
issue_id: "166"
tags: [architecture, refactoring, dataclass]
dependencies: []
---

# Refactor ScanRequest God Object

Split the 60+ field `ScanRequest` dataclass into smaller, specialized components.

## Problem Statement

The `ScanRequest` object has become a "God Object" with over 60 fields covering asset selection, scoring configuration, risk parameters, and output formatting. This makes the code difficult to maintain, test, and evolve. It also complicates the API documentation and validation logic.

## Findings

- `ScanRequest` (likely in `tvscreener/models/scan.py` or similar) contains a flat structure of unrelated parameters.
- Validation logic is scattered or overly complex due to the number of fields.

## Proposed Solutions

### Option 1: Logical Component Splitting

**Approach:** Split `ScanRequest` into four nested dataclasses:
1. `AssetSelection`: Filters, universes, symbols.
2. `ScoringConfig`: Models, weights, parameters.
3. `RiskConfig`: Stops, sizing, constraints.
4. `OutputConfig`: Formatting, destinations, sorting.

**Pros:**
- Improved modularity and readability.
- Easier to validate individual components.
- Better type hinting and autocomplete.

**Cons:**
- Breaking change for existing callers (requires migration).

**Effort:** 4-6 hours

**Risk:** Medium (due to breaking changes)

---

### Option 2: Incremental Component Extraction

**Approach:** Keep `ScanRequest` but start moving fields into the new components and providing properties for backward compatibility.

**Pros:**
- Non-breaking for existing callers.
- Allows for gradual migration.

**Cons:**
- Temporary increased complexity during the transition.
- Harder to enforce the new structure.

**Effort:** 6-8 hours

**Risk:** Low

## Recommended Action

**Option 1 with backward compatibility properties.**

## Technical Details

**Affected files:**
- `tvscreener/lib/orchestrator.py`: `ScanRequest` definition and `ScreenerController` implementation.
- `tvscreener/mcp/tools.py`: Updated to use nested structure.
- `tests/unit/test_opportunity_helpers.py`: Updated to match new structure.
- `tests/unit/test_cli_filters.py`: Updated mock to use nested access.

## Resources

- [Dataclasses Documentation](https://docs.python.org/3/library/dataclasses.html)
- [Composition over Inheritance](https://en.wikipedia.org/wiki/Composition_over_inheritance)

## Acceptance Criteria

- [x] `ScanRequest` refactored into `AssetSelection`, `ScoringConfig`, `RiskConfig`, and `OutputConfig`.
- [x] No more than 15 fields in any individual dataclass.
- [x] Updated validation logic for each component.
- [x] All scanner tests pass with the new structure.
- [x] Documentation (OpenAPI/Swagger) reflects the new nested structure.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo for refactoring the `ScanRequest` god object.
- Defined the four target components for splitting.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Refactored `ScanRequest` in `tvscreener/lib/orchestrator.py` into `AssetSelection`, `ScoringConfig`, `RiskConfig`, and `OutputConfig`.
- Updated `ScreenerController` to use nested access.
- Added backward compatibility properties for frequently used fields.
- Updated `mcp/tools.py` and unit tests.
- Verified all tests pass.

**Learnings:**
- God objects often emerge from organic growth and require periodic "pruning" into logical components.
- Using properties for backward compatibility eases migration in high-impact refactors.

