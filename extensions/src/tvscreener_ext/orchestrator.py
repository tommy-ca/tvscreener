#!/usr/bin/env python3
"""Orchestrator for screener execution and configuration."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tvscreener_ext.config import load_settings
from tvscreener_ext.config.universe import AssetUniverse, ConfigurationError
from tvscreener_ext.lakehouse import get_manager
from tvscreener_ext.models import (
    AssetSelection,
    OutputConfig,
    RiskConfig,
    ScanRequest,
    ScoringConfig,
)
from tvscreener_ext.screeners.registry import ScreenerFamilyRegistry
from tvscreener_ext.services.config import ConfigFactory
from tvscreener_ext.services.export import ExportService
from tvscreener_ext.services.maintenance import MaintenanceService
from tvscreener_ext.services.reporting import ReportingService
from tvscreener_ext.services.universe import UniverseResolver
from tvscreener_ext.services.workflow import ScanWorkflow
from tvscreener_ext.utils.logic import (
    canonicalize_asset_type,
    validate_path,
)

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
        request.assets.asset_type = canonicalize_asset_type(request.assets.asset_type)
        settings = load_settings(request.output.config_path)

        if request.assets.universe is None:
            request.assets.universe = settings.default_universe

        if request.assets.timeframes is None:
            request.assets.timeframes = settings.default_timeframes
        if request.assets.contract_type is None:
            request.assets.contract_type = settings.contract_type

        # Default instrument type for crypto universes
        if (
            request.assets.asset_type == "crypto"
            and getattr(request.assets, "instrument_type", None) is None
        ):
            if request.assets.universe and "perp" in request.assets.universe:
                request.assets.instrument_type = "perp"
            else:
                request.assets.instrument_type = "spot"

        if request.assets.contract_type is not None:
            valid_contracts = ("spot", "cfd", "spreadbet", "all")
            if request.assets.contract_type not in valid_contracts:
                raise ConfigurationError(
                    f"Invalid contract type: {request.assets.contract_type}. Valid options: {', '.join(valid_contracts)}"
                )

        # Scoped defaults: use opportunity settings if scanner is 'opportunity', else fallback to general
        def _resolve_val(attr: str, scanner: str) -> Any:
            # Check components
            for component in [request.assets, request.scoring, request.risk, request.output]:
                if hasattr(component, attr):
                    req_val = getattr(component, attr)
                    if req_val is not None:
                        return req_val

            # Potential override from settings
            settings_val = None
            if scanner == "opportunity":
                settings_val = getattr(settings.opportunity, attr, None)

            # Fallback to top-level settings
            if settings_val is None:
                settings_val = getattr(settings, attr, None)

            return settings_val

        request.assets.min_volume = _resolve_val("min_volume", request.assets.scanner)
        request.assets.max_atr = _resolve_val("max_atr", request.assets.scanner)
        request.assets.min_ma_score = _resolve_val("min_ma_score", request.assets.scanner)

        if request.scoring.min_confluence is None:
            request.scoring.min_confluence = settings.min_confluence
        if request.scoring.trend_threshold is None:
            request.scoring.trend_threshold = settings.trend_threshold
        if request.scoring.mr_threshold is None:
            request.scoring.mr_threshold = settings.mr_threshold
        if request.scoring.rsi_lower is None:
            request.scoring.rsi_lower = settings.rsi_lower
        if request.scoring.rsi_upper is None:
            request.scoring.rsi_upper = settings.rsi_upper
        if request.assets.min_roc is None:
            request.assets.min_roc = settings.min_roc

        # Opportunity weights
        if request.scoring.opportunity_trend_weight is None:
            request.scoring.opportunity_trend_weight = settings.opportunity.trend_weight
        if request.scoring.opportunity_ma_weight is None:
            request.scoring.opportunity_ma_weight = settings.opportunity.ma_weight
        if request.scoring.opportunity_osc_weight is None:
            request.scoring.opportunity_osc_weight = settings.opportunity.osc_weight
        if request.scoring.opportunity_roc_weight is None:
            request.scoring.opportunity_roc_weight = settings.opportunity.roc_weight
        if request.scoring.opportunity_timeframe_weights is None:
            request.scoring.opportunity_timeframe_weights = settings.opportunity.timeframe_weights

        # Risk management defaults
        if request.scoring.min_tf_alignment is None:
            request.scoring.min_tf_alignment = settings.risk.min_tf_alignment

        if request.risk.risk_per_trade_pct is None:
            request.risk.risk_per_trade_pct = settings.risk.risk_per_trade_pct
        if request.risk.atr_multiplier is None:
            request.risk.atr_multiplier = settings.risk.atr_multiplier
        if request.risk.min_risk_reward_ratio is None:
            request.risk.min_risk_reward_ratio = settings.risk.min_risk_reward_ratio
        if request.risk.account_balance is None:
            request.risk.account_balance = settings.risk.account_balance

        return request

    def run_scan(self, request: ScanRequest) -> int:
        """Main entry point to run a scan."""
        request = self.resolve_defaults(request)
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

    def run_from_args(self, args: argparse.Namespace) -> int:
        """Run scan from argparse namespace."""
        get_manager(getattr(args, "config", None))

        command = getattr(args, "command", "scan")
        if command == "maintenance":
            return self.run_maintenance(args)
        if command == "query":
            return self.run_query(args)
        if command == "audit":
            return self.run_audit(args)
        if command == "report":
            return self.run_report(args)
        if command == "review":
            return self.run_review(args)

        matrix_mode = getattr(args, "matrix", True)
        detailed_mode = getattr(args, "detailed", False)

        request = ScanRequest(
            assets=AssetSelection(
                scanner=args.scanner,
                pipeline=getattr(args, "pipeline", "both"),
                strategy=args.strategy,
                asset_type=args.asset_type,
                universe=args.universe,
                pairs=args.pairs,
                timeframes=args.timeframes,
                contract_type=args.contract_type,
                instrument_type=getattr(args, "instrument_type", None),
                min_volume=args.min_volume,
                max_atr=args.max_atr,
                min_ma_score=args.min_ma_score,
                min_roc=args.min_roc,
                min_rvol=args.min_rvol,
                require_volume_spike=args.require_volume_spike,
                include_atr=args.include_atr,
                include_rsi=args.include_rsi,
            ),
            scoring=ScoringConfig(
                opportunity_trend_weight=args.opportunity_trend_weight,
                opportunity_ma_weight=args.opportunity_ma_weight,
                opportunity_osc_weight=args.opportunity_osc_weight,
                opportunity_roc_weight=args.opportunity_roc_weight,
                opportunity_timeframe_weights=args.opportunity_timeframe_weights,
                filter_direction=getattr(args, "direction", None),
                min_confluence=args.min_confluence,
                trend_threshold=args.trend_threshold,
                mr_threshold=args.mr_threshold,
                rsi_lower=args.rsi_lower,
                rsi_upper=args.rsi_upper,
                mr_signal=args.mr_signal or [],
                min_tf_alignment=args.min_tf_alignment,
                require_momentum=args.require_momentum,
            ),
            risk=RiskConfig(
                risk_per_trade_pct=args.risk_per_trade,
                atr_multiplier=args.atr_multiplier,
                min_risk_reward_ratio=args.min_risk_reward,
                account_balance=args.account_balance,
            ),
            output=OutputConfig(
                output=args.output,
                detailed=detailed_mode,
                matrix=matrix_mode,
                limit=args.limit,
                head=args.head,
                metadata_only=args.metadata_only,
                save_config=args.save_config,
                config_path=args.config,
                verbose=args.verbose,
                show_risk=getattr(args, "show_risk", False),
                sql=getattr(args, "sql", None),
                sql_params=getattr(args, "sql_params", {}),
                filters=getattr(args, "filter", []) or [],
                confluence_grade=args.confluence_grade,
                min_opportunity_confluence=args.min_opportunity_confluence,
            ),
        )

        return self.run_scan(request)

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
        request = self.resolve_defaults(request)
        return self._workflow.run_opportunity_scan(request)

    def run_strategy_scan(self, request: ScanRequest) -> int:
        """Run strategy scanner and handle output."""
        request = self.resolve_defaults(request)
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
