## MODIFIED Requirements

### Requirement: Matrix view includes screener snapshot time
When rendering a matrix view from Iceberg-backed analytics data, the system SHALL display a snapshot time so the
output is self-describing in logs and screenshots.

#### Scenario: Opportunity matrix shows snapshot label from `fetched_at_utc`
- **GIVEN** an analytics run loads opportunities from `tvscreener.signals_latest`
- **AND** the dataframe includes a `fetched_at_utc` column
- **WHEN** the system renders the confluence matrix view (`--matrix`)
- **THEN** the matrix title includes `Snapshot: <ts> UTC` or `Snapshot: <min>..<max> UTC`

#### Scenario: Strategy matrix shows snapshot label from the underlying snapshot dataframe
- **GIVEN** a strategy analytics run loads `tvscreener.signals_latest` as its input dataframe
- **WHEN** the system renders the strategy matrix view (`--matrix`)
- **THEN** the matrix title includes the same snapshot label derived from that dataframe’s `fetched_at_utc`

#### Scenario: Missing `fetched_at_utc` does not break rendering
- **GIVEN** the dataframe does not include `fetched_at_utc`
- **WHEN** the matrix view is rendered
- **THEN** the matrix view renders normally without a snapshot label

