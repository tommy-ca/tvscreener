# Tasks: Prefect scheduled opportunity runs

- [x] Add batch specs for crypto majors/minors and market risk proxy
- [x] Add a deployment helper to register cron schedules
- [x] Document how to start server + worker and apply schedules
- [x] Validate forex majors/minors data-only deployment produces run artifacts and tvscreener.runs rows
- [x] Validate Binance crypto majors/minors data-only deployment produces run artifacts and tvscreener.runs rows
- [x] Validate market risk proxy data-only deployment produces run artifacts and tvscreener.runs rows
- [x] Fail scheduled data runs on Iceberg persistence errors (strict persist)
- [x] Re-validate data freshness then rerender analytics matrices (forex, crypto spot/perp, market risk)
- [x] Register scheduled deployments against a Prefect work pool (worker-based schedules)
- [x] Validate worker execution via `prefect deployment run --watch` for each scheduled data deployment
