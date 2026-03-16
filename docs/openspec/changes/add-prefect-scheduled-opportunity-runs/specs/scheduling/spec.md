## ADDED Requirements

### Requirement: Scheduled runs cover key universes
The system SHOULD support scheduled execution of opportunity data pipelines for:
- forex majors/minors
- Binance crypto spot/perp majors/minors
- market risk proxy basket

#### Scenario: Prefect cron triggers periodic batch runs
- **GIVEN** a Prefect deployment exists for `workflows/prefect/run_batch.py:run_batch`
- **WHEN** cron schedules are registered
- **THEN** Prefect creates flow runs periodically with deterministic `PipelineRunSpec` artifacts under `artifacts/runs/`
