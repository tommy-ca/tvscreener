#!/usr/bin/env python3
"""Orchestrator for screener execution and configuration."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from tvscreener_ext.config.universe import AssetUniverse
from tvscreener_ext.models import ScanRequest
from tvscreener_ext.screeners.registry import ScreenerFamilyRegistry
from tvscreener_ext.services.config import ConfigFactory
from tvscreener_ext.services.export import ExportService
from tvscreener_ext.services.maintenance import MaintenanceService
from tvscreener_ext.services.reporting import ReportingService
from tvscreener_ext.services.universe import UniverseResolver
from tvscreener_ext.services.workflow import ScanWorkflow
from tvscreener_ext.utils.logic import validate_path

if TYPE_CHECKING:
    from rich.console import Console

import logging

logger = logging.getLogger(__name__)


class ScreenerController:
    """Handles the execution lifecycle of scanners."""

    def __init__(self, console: Console | None = None):
        self.console = console
        self._universe_resolver = UniverseResolver()
        self._export_service = ExportService()
        self._config_factory = ConfigFactory()
        self._maintenance_service = MaintenanceService()
        self._reporting_service = ReportingService(
            resolver=self._universe_resolver, console=self.console
        )
        self._workflow = ScanWorkflow(
            resolver=self._universe_resolver,
            factory=self._config_factory,
            exporter=self._export_service,
            console=self.console,
        )
        self._family_registry = ScreenerFamilyRegistry()
        self._family_registry.register("opportunity", self.run_opportunity_scan)
        self._family_registry.register("strategy", self.run_strategy_scan)
        self._family_registry.register("inspect", self.run_inspect_parquet)

    def get_universe(self, asset_type: str) -> AssetUniverse:
        """Get universe config by asset type with validation."""
        return self._universe_resolver.get_universe_config(asset_type)

    def get_pairs(
        self,
        asset_type: str,
        universe: str | None,
        specific: list[str] | None,
        *,
        instrument_type: str | None = None,
    ) -> list[str]:
        """Resolve symbols based on asset type, universe selector, or explicit list."""
        return self._universe_resolver.resolve_tickers(
            asset_type, universe, specific, instrument_type=instrument_type
        )

    def resolve_defaults(self, request: ScanRequest) -> ScanRequest:
        """Fill in missing parameters from settings."""
        return self._config_factory.normalize_request(request)

    def run_scan(self, request: ScanRequest) -> int:
        """Main entry point to run a scan."""
        request = self._config_factory.normalize_request(request)
        return self._family_registry.run(request.assets.scanner, request)

    def run_maintenance(self, args: argparse.Namespace) -> int:
        """Run repository and lakehouse maintenance tasks."""
        if self.console:
            self.console.print("[bold cyan]Running Maintenance...[/bold cyan]")

        # 1. Artifact Migration
        if getattr(args, "migrate_artifacts", False):
            if self.console:
                self.console.print(" - Migrating legacy artifacts to artifacts/runs/...")
            res = self._maintenance_service.migrate_artifacts(Path.cwd())
            if self.console:
                self.console.print(
                    f"   [green]Migrated: {res['migrated']}[/green], "
                    f"[yellow]Skipped: {res['skipped']}[/yellow], "
                    f"[red]Errors: {res['errors']}[/red]"
                )

        # 2. Artifact Pruning
        if getattr(args, "prune_artifacts", False):
            days = getattr(args, "prune_days", 30)
            if self.console:
                self.console.print(f" - Pruning artifacts older than {days} days...")
            count = self._maintenance_service.prune_artifacts(Path.cwd(), older_than_days=days)
            if self.console:
                self.console.print(f"   [green]Pruned {count} artifact directories.[/green]")

        # 3. Lakehouse Maintenance
        from tvscreener_ext.lakehouse import get_manager

        manager = get_manager(getattr(args, "config", None))
        table_name = getattr(args, "table", "forex.opportunities")

        if getattr(args, "expire_snapshots", False):
            days = getattr(args, "days", 7)
            if self.console:
                self.console.print(
                    f" - Expiring snapshots older than {days} days for {table_name}..."
                )
            manager.maintenance(table_name, "expire_snapshots", older_than_days=days)

        if getattr(args, "compact", False):
            if self.console:
                self.console.print(f" - Compacting files for {table_name}...")
            manager.maintenance(table_name, "compact")

        if self.console:
            self.console.print("[bold green]Maintenance complete.[/bold green]")
        return 0

    def run_query(self, args: argparse.Namespace) -> int:
        """Run an Edge SQL query on a table."""
        from tvscreener_ext.query import EdgeQueryClient

        table = args.table
        sql = getattr(args, "sql", "SELECT * FROM df")
        snapshot_id = getattr(args, "snapshot_id", None)
        limit = getattr(args, "head", 10)

        if self.console:
            msg = f"[cyan]Querying {table}[/cyan]"
            if snapshot_id:
                msg += f" [dim](Snapshot: {snapshot_id})[/dim]"
            self.console.print(msg)

        try:
            with EdgeQueryClient() as client:
                df = client.query_sql(table, sql, snapshot_id=snapshot_id)

                if self.console:
                    if df.empty:
                        self.console.print("[yellow]Query returned no results.[/yellow]")
                    else:
                        from rich.table import Table

                        title = f"SQL Results: {table}"
                        if snapshot_id:
                            title += f" @ {snapshot_id}"
                        rich_table = Table(title=title)

                        for col in df.columns:
                            rich_table.add_column(str(col))

                        for _, row in df.head(limit).iterrows():
                            rich_table.add_row(*[str(val) for val in row])

                        self.console.print(rich_table)
                        self.console.print(
                            f"\n[dim]Showing {len(df.head(limit))} of {len(df)} results[/dim]"
                        )

                if getattr(args, "output", None):
                    out_path = Path(args.output)
                    metadata = {"command": "query", "table": table, "sql": sql}
                    self._export_service.export_dataframe(
                        df, str(out_path), metadata, label="query_results"
                    )

                return len(df)
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Query failed: {e}[/red]")
            logger.error("Edge Query failed: %s", e)
            return -1

    def run_audit(self, args: argparse.Namespace) -> int:
        """Run audits and write structured reports."""
        return self._reporting_service.run_audit(args)

    def run_report(self, args: argparse.Namespace) -> int:
        """Generate DuckDB reports."""
        return self._reporting_service.run_report(args)

    def run_review(self, args: argparse.Namespace) -> int:
        """Run audit + report pipeline."""
        return self._reporting_service.run_review(args)

    def run_opportunity_scan(self, request: ScanRequest) -> int:
        """Run opportunity screener and handle output."""
        return self._workflow.run_opportunity_scan(request)

    def run_strategy_scan(self, request: ScanRequest) -> int:
        """Run strategy scanner and handle output."""
        return self._workflow.run_strategy_scan(request)

    def run_inspect_parquet(self, request: ScanRequest) -> int:
        """Inspect a parquet file or Iceberg table."""
        return self._workflow.run_inspect(request)

    def _validate_path(self, path_str: str, base_dir: Path | None = None) -> Path:
        return validate_path(path_str, base_dir=base_dir)

    def _maybe_save_opportunity_config(self, path: str, request: ScanRequest) -> None:
        return self._workflow._maybe_save_opportunity_config(path, request)

    def _parse_timeframe_weights(self, spec: str | None) -> dict[str, float]:
        return self._config_factory._parse_timeframe_weights(spec)
