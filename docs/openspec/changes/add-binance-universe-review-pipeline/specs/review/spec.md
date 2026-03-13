## ADDED Requirements

### Requirement: CLI supports one-shot universe review
The system SHALL provide a CLI command to run the universe audit and DuckDB report pipelines together.

#### Scenario: Review command runs audit then report
- **GIVEN** `tvscreener-scan review binance-universes`
- **WHEN** the command runs
- **THEN** it writes an audit report under `--audit-out-dir`
- **AND** it generates a DuckDB report using that audit folder as input

#### Scenario: Strict mode fails on audit errors
- **GIVEN** `--strict`
- **WHEN** any audited universe includes one or more errors
- **THEN** the command exits non-zero

#### Scenario: Review can include extended diagnostic universes
- **GIVEN** `--include-all`
- **WHEN** the review command runs
- **THEN** it includes extended diagnostic universes (market-cap top100 and cs_momentum) in the audit and report
