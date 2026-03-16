## Proposal: Scheduled Prefect runs for opportunity scanners

We want periodic opportunity scans across key universes using the Prefect batch runner:
- forex majors/minors
- Binance crypto spot/perp majors/minors
- market risk proxy basket (`market_risk`)

This change package adds a simple deployment script and batch specs so operators can register schedules against a Prefect server.

Operational expectation:
- Default schedules run `pipeline_mode=data` only; matrix/analytics outputs are regenerated via `pipeline_mode=analytics` (or by scheduling `pipeline_mode=both`).
