# Extensions Guide

The `tvscreener-ext` package provides advanced orchestration, edge analytics, and lakehouse integration for the core `tvscreener` library.

## Key Features

- **Service-Oriented Architecture**: Modular components for universe resolution, configuration, and export.
- **Medallion Lakehouse**: Local Iceberg storage for raw (Bronze), standardized (Silver), and scored (Gold) data.
- **Edge Analytics**: Lightning-fast DuckDB queries on local datasets.
- **Workflow Orchestration**: Support for Local and Prefect-based execution of complex scan batches.

## CLI Usage

The primary entry point for extensions is `tvscreener-ext-scan`.

### Running a Scan

Run a strategy scan locally:

```bash
uv run tvscreener-ext-scan scan --runner local --asset-type forex --universe majors
```

### Lakehouse Maintenance

Expire snapshots or compact tables:

```bash
uv run tvscreener-ext-scan maintenance --expire-snapshots --days 7 --table tvscreener.gold
```

Migrate legacy artifacts from `artifacts/prefect/` to `artifacts/runs/`:

```bash
uv run tvscreener-ext-scan maintenance --migrate-artifacts
```

### Edge SQL Queries

Query any Iceberg table directly using SQL:

```bash
uv run tvscreener-ext-scan query tvscreener.gold --sql "SELECT * FROM df WHERE trend_score > 0.8"
```

## Programmatic Usage

### ScreenerController

The `ScreenerController` is the high-level facade for all extension operations.

```python
from tvscreener_ext.orchestrator import ScreenerController
from tvscreener_ext.models import ScanRequest, AssetSelection

controller = ScreenerController()

# Resolve a universe to tickers
tickers = controller.get_pairs(asset_type="crypto", universe="binance_spot_top100")

# Run a full scan workflow
request = ScanRequest(
    assets=AssetSelection(scanner="opportunity", asset_type="forex", universe="majors")
)
controller.run_scan(request)
```

### Services

For granular control, you can use the underlying services directly:

- `UniverseResolver`: Resolve asset types and universe aliases.
- `ConfigFactory`: Map requests to internal configurations.
- `ExportService`: Unified IO for CSV, JSON, Parquet, and XML.
- `ScanWorkflow`: Coordinate the end-to-end scan lifecycle.

## Artifacts & Discovery

All runs produce a deterministic set of artifacts under `artifacts/runs/<params_hash>/`:

- `run_spec.json`: The full configuration used for the run.
- `run_result.json`: A summary of the execution outcome (success, count, errors).
- `results.parquet`: The raw data retrieved/processed.
- `matrix.txt`: (Optional) The text-based confluence matrix for console display.

The `run_result.json` file serves as the machine-discoverable contract for that execution.
