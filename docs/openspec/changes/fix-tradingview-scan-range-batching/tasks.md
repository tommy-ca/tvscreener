## Tasks

## 1. Specs
- [x] 1.1 Add requirement: explicit tickers imply range sized to tickers (unless user overrides range)
- [x] 1.2 Add scenario-based regression test requirement

## 2. Implementation
- [x] 2.1 Track whether range is default vs user-set
- [x] 2.2 Auto-size `range` in `Screener.get()` when `symbols.tickers` is provided

## 3. Tests
- [x] 3.1 Add a unit test that inspects the outgoing payload range for 200 tickers

## 4. Verification (rerun data + analytics pipelines)
- [x] 4.1 Rerun a data pipeline that batches >150 tickers (forex `universe=all`) and confirm no truncation
- [x] 4.2 Rerun an analytics pipeline from Iceberg outputs and confirm artifacts/render parity
- [ ] 4.3 Rerun via Prefect workflows:
  - use `--runner export` to create a `PipelineRunSpec`
  - run with `workflows/prefect/run_flow.py` and confirm artifacts exist under `artifacts/runs/<params_hash>/`
