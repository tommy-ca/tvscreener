# Service-Oriented Architecture (Decomposition)

To satisfy the **Single Responsibility Principle (SRP)** and improve testability, the monolithic `ScreenerController` is being decomposed into specialized, stateless services.

## 1. UniverseResolver
**Responsibility**: Ticker and asset discovery.
- Resolves asset types (`forex`, `crypto`, `stock`) and their aliases.
- Handles universe-level filtering (e.g., `majors`, `minors`, `top100`).
- Orchestrates dynamic universe resolution (e.g., Binance API constraints).
- **Interface**:
  ```python
  def resolve_tickers(self, asset_type: str, universe: str | None = None, specific: list[str] | None = None) -> list[str]: ...
  ```

## 2. ConfigFactory
**Responsibility**: Configuration mapping.
- Translates the external `ScanRequest` (or CLI args) into engine-specific configuration objects (`ForexScreenerConfig`, `StrategyConfig`).
- Enforces validation and default precedence rules.
- **Interface**:
  ```python
  def build_config(self, request: ScanRequest) -> BaseScreenerConfig: ...
  ```

## 3. ExportService
**Responsibility**: Unified IO and Artifact Management.
- Provides consistent writing for all supported formats (CSV, JSON, Parquet, XML).
- Handles metadata injection and `MetadataEncoder` serialization.
- Ensures parent directory integrity and path validation.
- **Interface**:
  ```python
  def export(self, df: pd.DataFrame, path: Path, metadata: dict[str, Any], format: str) -> None: ...
  ```

## 4. ScanWorkflow (Coordinator)
**Responsibility**: Lifecycle Orchestration.
- Orchestrates the sequence: `Resolver -> Factory -> Execution -> Filtering -> Export`.
- Manages progress bars and console logging.
- Captures and persists confluence matrices (`matrix.txt`) to artifact directories.
- Handles optional Table Artifact publication (`results_top_rows.json`, `results_grade_summary.json`) for in-browser review.
- **Interface**:
  ```python
  def run_opportunity_scan(self, request: ScanRequest) -> int: ...
  def run_strategy_scan(self, request: ScanRequest) -> int: ...
  def run_inspect(self, request: ScanRequest) -> int: ...
  ```

## 5. MaintenanceService
**Responsibility**: Repository and Artifact Lifecycle.
- Migrates legacy artifacts from `artifacts/prefect/` to `artifacts/runs/`.
- Prunes old artifacts based on retention policies.
- Coordinates with `LakehouseManager` for table-level maintenance (expiry, compaction).
- **Interface**:
  ```python
  def migrate_artifacts(self, base_dir: Path) -> dict[str, int]: ...
  def prune_artifacts(self, base_dir: Path, older_than_days: int = 30) -> int: ...
  ```

## 6. ReportingService
**Responsibility**: Audits, Reports, and Reviews.
- Executes universe audits and generates structured status reports.
- Handles legacy report generation via DuckDB.
- Coordinates audit+report review pipelines.
- **Interface**:
  ```python
  def run_audit(self, args: argparse.Namespace) -> int: ...
  def run_report(self, args: argparse.Namespace) -> int: ...
  def run_review(self, args: argparse.Namespace) -> int: ...
  ```

## 7. CommandRegistry (CLI)
**Responsibility**: Declarative Subcommand Routing.
- Replaces the `argparse` switch-case in `scan.py`.
- Maps subcommand strings to specialized handler methods.
