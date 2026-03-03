#!/usr/bin/env python3
"""Orchestrator for screener execution and configuration."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml

from tvscreener.config.loader import load_settings
from tvscreener.config.universe import FOREX_UNIVERSE, AssetUniverse, ConfigurationError
from tvscreener.constants.commodity import COMMODITY_UNIVERSE
from tvscreener.constants.crypto import CRYPTO_UNIVERSE
from tvscreener.constants.forex import (
    DEFAULT_FOREX_PAIRS,
    DEFAULT_TIMEFRAME_WEIGHTS,
    FOREX_MAJORS,
    FOREX_MINORS,
)
from tvscreener.constants.stocks import STOCK_UNIVERSE
from tvscreener.core.enums import Direction
from tvscreener.filter import AtrFilter, RocFilter, ScoreFilter, VolumeFilter
from tvscreener.lib.lakehouse import get_manager
from tvscreener.lib.screeners.base import BaseOpportunityScreener
from tvscreener.lib.screeners.factory import AssetScreenerFactory
from tvscreener.lib.screeners.forex_opportunity import ContractType, ForexScreenerConfig
from tvscreener.lib.screeners.forex_strategy import (
    ForexStrategyScanner,
    StrategyConfig,
    StrategyType,
)
from tvscreener.score import ScoringConfig as ScoreWeights
from tvscreener.util import parse_timeframe_weights, validate_path

if TYPE_CHECKING:
    import pandas as pd
    from rich.console import Console

logger = logging.getLogger(__name__)

UNIVERSE_MAP: dict[str, AssetUniverse] = {
    "forex": FOREX_UNIVERSE,
    "stocks": STOCK_UNIVERSE,
    "commodity": COMMODITY_UNIVERSE,
    "crypto": CRYPTO_UNIVERSE,
}


@dataclass
class AssetSelection:
    """Routing and asset selection parameters."""

    scanner: str = "strategy"
    strategy: str = "all"
    asset_type: str = "forex"
    universe: str | None = None
    pairs: list[str] | None = None
    timeframes: str | None = None
    contract_type: str | None = None
    min_volume: float | None = None
    max_atr: float | None = None
    min_ma_score: float | None = None
    min_roc: float | None = None
    min_rvol: float | None = None
    require_volume_spike: bool = False
    include_atr: bool = False
    include_rsi: bool = False


@dataclass
class ScoringConfig:
    """Scoring and signal configuration parameters."""

    # Opportunity Screener Weights
    opportunity_trend_weight: float | None = None
    opportunity_ma_weight: float | None = None
    opportunity_osc_weight: float | None = None
    opportunity_roc_weight: float | None = None
    opportunity_timeframe_weights: str | None = None

    # Strategy Scanner Parameters
    filter_direction: Direction | str | None = None  # Direction.LONG, Direction.SHORT
    min_confluence: int | None = None
    trend_threshold: float | None = None
    mr_threshold: float | None = None
    rsi_lower: float | None = None
    rsi_upper: float | None = None
    mr_signal: list[str] = field(default_factory=list)
    min_tf_alignment: int | None = None
    require_momentum: bool = False


@dataclass
class RiskConfig:
    """Risk management parameters."""

    risk_per_trade_pct: float | None = None
    atr_multiplier: float | None = None
    min_risk_reward_ratio: float | None = None
    account_balance: float | None = None
    pip_value: float | None = None


@dataclass
class OutputConfig:
    """Output formatting and control parameters."""

    output: str | None = None
    detailed: bool = False
    matrix: bool = False
    limit: int | None = None
    show_risk: bool = False
    head: int | None = None
    metadata_only: bool = False
    save_config: str | None = None
    config_path: str | None = None
    verbose: bool = False
    sql: str | None = None
    sql_params: dict[str, Any] = field(default_factory=dict)
    filters: list[str] = field(default_factory=list)
    confluence_grade: str | None = None
    min_opportunity_confluence: int | None = None


@dataclass
class ScanRequest:
    """Unified scan request parameters using nested components."""

    assets: AssetSelection = field(default_factory=AssetSelection)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # Backward compatibility properties for most common fields
    @property
    def scanner(self) -> str:
        return self.assets.scanner

    @property
    def asset_type(self) -> str:
        return self.assets.asset_type

    @property
    def sql(self) -> str | None:
        return self.output.sql

    @property
    def strategy(self) -> str:
        return self.assets.strategy


class ScreenerController:
    """Handles the execution lifecycle of scanners."""

    def __init__(self, console: Console | None = None):
        self.console = console

    def get_universe(self, asset_type: str) -> AssetUniverse:
        """Get universe config by asset type with validation."""
        if asset_type not in UNIVERSE_MAP:
            raise ConfigurationError(
                f"Unknown asset type: {asset_type}. Valid options: {', '.join(UNIVERSE_MAP.keys())}"
            )
        return UNIVERSE_MAP[asset_type]

    def get_pairs(self, universe: str | None, specific: list[str] | None) -> list[str]:
        """Resolve pairs based on universe or specific list."""
        if specific:
            return specific
        if universe == "majors":
            return FOREX_MAJORS
        elif universe == "minors":
            return FOREX_MINORS
        return DEFAULT_FOREX_PAIRS

    def resolve_defaults(self, request: ScanRequest) -> ScanRequest:
        """Fill in missing parameters from settings."""
        settings = load_settings(request.output.config_path)

        if request.assets.universe is None:
            request.assets.universe = settings.default_universe
        if request.assets.timeframes is None:
            request.assets.timeframes = settings.default_timeframes
        if request.assets.contract_type is None:
            request.assets.contract_type = settings.contract_type

        if request.assets.contract_type is not None:
            valid_contracts = ("spot", "cfd", "spreadbet", "all")
            if request.assets.contract_type not in valid_contracts:
                raise ConfigurationError(
                    f"Invalid contract type: {request.assets.contract_type}. Valid options: {', '.join(valid_contracts)}"
                )

        # Scoped defaults: use opportunity settings if scanner is 'opportunity', else fallback to general
        def _resolve_val(attr: str, scanner: str) -> Any:
            # Determine which component the attribute belongs to
            # This is a bit tricky with nested structure, so we check them manually or use a map
            # For simplicity in this refactor, we'll just check where the field currently lives

            # Check all components
            for component in [request.assets, request.scoring, request.risk, request.output]:
                if hasattr(component, attr):
                    req_val = getattr(component, attr)
                    if req_val is not None:
                        return req_val

            # Determine potential override from settings
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
        # Filtering (min_rvol) happens in EdgeQueryClient after ingestion so pipelines stay raw
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

        if request.assets.scanner == "opportunity":
            return self.run_opportunity_scan(request)
        elif request.assets.scanner == "strategy":
            return self.run_strategy_scan(request)
        elif request.assets.scanner == "inspect":
            return self.run_inspect_parquet(request)
        else:
            raise ValueError(f"Unknown scanner type: {request.assets.scanner}")

    def run_maintenance(self, args: argparse.Namespace) -> int:
        """Run lakehouse maintenance tasks."""
        if self.console:
            self.console.print("[bold cyan]Running Lakehouse Maintenance...[/bold cyan]")

        manager = get_manager()
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
        """Run an Edge SQL query on a table (Todo 144)."""
        from tvscreener.lib.query import EdgeQueryClient

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
                    if out_path.suffix == ".csv":
                        df.to_csv(out_path, index=False)
                    else:
                        df.to_parquet(out_path, index=False)
                    if self.console:
                        self.console.print(f"[green]Saved to {out_path}[/green]")

                return len(df)
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Query failed: {e}[/red]")
            logger.error("Edge Query failed: %s", e)
            return -1

    def run_from_args(self, args: argparse.Namespace) -> int:
        """Run scan from argparse namespace."""
        command = getattr(args, "command", "scan")
        if command == "maintenance":
            return self.run_maintenance(args)
        if command == "query":
            return self.run_query(args)

        matrix_mode = args.matrix
        detailed_mode = args.detailed
        if not (matrix_mode or detailed_mode):
            matrix_mode = True

        request = ScanRequest(
            assets=AssetSelection(
                scanner=args.scanner,
                strategy=args.strategy,
                asset_type=args.asset_type,
                universe=args.universe,
                pairs=args.pairs,
                timeframes=args.timeframes,
                contract_type=args.contract_type,
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

    def run_opportunity_scan(self, request: ScanRequest) -> int:
        """Run opportunity screener and handle output."""
        results, screener = self.get_opportunity_results(request)

        metadata = self._build_opportunity_metadata(request)

        if request.output.output:
            self._export_results(screener, request.output.output, metadata)

        if self.console:
            if results.empty:
                self.console.print("[yellow]No results found matching criteria.[/yellow]")
            else:
                # Restore specialized view parity: pass SQL/Filtered results back to renderer
                screener.print_summary(
                    results_df=results,
                    detailed=request.output.detailed,
                    matrix=request.output.matrix,
                    limit=request.output.limit,
                    show_risk=request.output.show_risk,
                )

        if request.output.save_config:
            self._maybe_save_opportunity_config(request.output.save_config, request)

        return len(results)

    def get_opportunity_results(
        self, request: ScanRequest
    ) -> tuple[pd.DataFrame, BaseOpportunityScreener]:
        """Run opportunity screener and return results + screener instance."""
        request = self.resolve_defaults(request)
        pairs = self.get_pairs(request.assets.universe, request.assets.pairs)
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        if self.console:
            self.console.print(
                f"[cyan]Scanning {len(pairs)} {request.assets.asset_type} pairs...[/cyan]"
            )

        config = self._build_opportunity_config(request)
        screener = AssetScreenerFactory.create_screener(
            asset_type=request.assets.asset_type,
            symbols=pairs,
            timeframes=timeframes,
            config=config,
        )

        results = self._fetch_data_with_progress(screener.get_opportunities)

        if request.output.sql or request.output.filters:
            from tvscreener.lib.query import EdgeQueryClient

            try:
                with EdgeQueryClient() as edge_client:
                    # Apply SQL if provided
                    if request.output.sql:
                        results = edge_client.query_sql(
                            results, request.output.sql, params=request.output.sql_params
                        )
                        screener.metadata.config["sql"] = request.output.sql

                    # Apply additional filters if provided
                    if request.output.filters:
                        for f in request.output.filters:
                            results = edge_client.query_sql(results, f"SELECT * FROM df WHERE {f}")
                            screener.metadata.config.setdefault("cli_filters", []).append(f)
            except Exception as e:
                logger.error("Failed to apply edge filters: %s", e)
                # Keep original results if filtering fails

        if request.output.confluence_grade or request.output.min_opportunity_confluence:
            results = self._filter_by_confluence(
                results,
                grade=request.output.confluence_grade,
                min_confluence=request.output.min_opportunity_confluence,
            )

        return results, screener

    def run_strategy_scan(self, request: ScanRequest) -> int:
        """Run strategy scanner and handle output."""
        results, scanner = self.get_strategy_results(request)

        metadata = self._build_strategy_metadata(request)

        if request.output.output:
            self._export_results(scanner, request.output.output, metadata)

        if self.console:
            if results.empty:
                self.console.print("[yellow]No signals found matching criteria.[/yellow]")
            else:
                scanner.print_summary(
                    results_df=results,
                    detailed=request.output.detailed,
                    matrix=request.output.matrix,
                    limit=request.output.limit,
                    show_risk=request.output.show_risk,
                )

        return len(results)

    def get_strategy_results(
        self, request: ScanRequest
    ) -> tuple[pd.DataFrame, ForexStrategyScanner]:
        """Run strategy scanner and return results + scanner instance."""
        request = self.resolve_defaults(request)
        pairs = self.get_pairs(request.assets.universe, request.assets.pairs)
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        if self.console:
            self.console.print(
                f"[cyan]Scanning {len(pairs)} {request.assets.asset_type} pairs for {request.assets.strategy} signals...[/cyan]"
            )

        config = self._build_strategy_config(request)
        scanner = ForexStrategyScanner(pairs=pairs, timeframes=timeframes, config=config)

        results = self._fetch_data_with_progress(scanner.scan)

        if request.output.sql or request.output.filters:
            from tvscreener.lib.query import EdgeQueryClient

            try:
                with EdgeQueryClient() as edge_client:
                    # Apply SQL if provided
                    if request.output.sql:
                        results = edge_client.query_sql(
                            results, request.output.sql, params=request.output.sql_params
                        )
                        scanner._screener.metadata.config["sql"] = request.output.sql

                    # Apply additional filters if provided
                    if request.output.filters:
                        for f in request.output.filters:
                            results = edge_client.query_sql(results, f"SELECT * FROM df WHERE {f}")
                            scanner._screener.metadata.config.setdefault("cli_filters", []).append(
                                f
                            )
            except Exception as e:
                logger.error("Failed to apply edge filters: %s", e)

        return results, scanner

    def run_inspect_parquet(self, request: ScanRequest) -> int:
        """Inspect a parquet file or Iceberg table."""
        from tvscreener.lib.inspect_utils import inspect_parquet
        from tvscreener.lib.query import EdgeQueryClient

        if not request.output.output:
            if self.console:
                self.console.print(
                    "[red]Error: Please specify a file or table to inspect using --output or -o[/red]"
                )
            return -1

        # Check if it looks like an Iceberg table identifier
        is_iceberg = (
            "." in request.output.output
            and not any(
                request.output.output.endswith(ext) for ext in [".parquet", ".csv", ".json", ".xml"]
            )
            and not Path(request.output.output).exists()
        )

        if request.output.sql:
            try:
                with EdgeQueryClient() as edge_client:
                    results = edge_client.query_sql(
                        request.output.output, request.output.sql, params=request.output.sql_params
                    )

                if self.console:
                    if results.empty:
                        self.console.print("[yellow]Edge query returned 0 rows.[/yellow]")
                    else:
                        from rich.table import Table

                        table = Table(title=f"SQL Results from {request.output.output}")
                        for col in results.columns:
                            table.add_column(col)
                        for _, row in results.head(request.output.head or 10).iterrows():
                            table.add_row(*[str(val) for val in row])
                        self.console.print(table)
                return len(results)
            except Exception as e:
                if self.console:
                    self.console.print(f"[red]Edge Query execution failed: {e}[/red]")
                logger.error(f"Edge Query execution failed: {e}")
                return 0

        if not is_iceberg:
            # Security: Validate path before inspection
            try:
                validated_path = self._validate_path(request.output.output)
            except ValueError as e:
                if self.console:
                    self.console.print(f"[red]Error: {e}[/red]")
                return -1

            inspect_parquet(
                path=str(validated_path),
                head=request.output.head or 10,
                metadata_only=request.output.metadata_only,
            )
        else:
            if self.console:
                self.console.print(
                    f"[cyan]Inspecting Iceberg Table: {request.output.output}[/cyan]"
                )
                try:
                    with EdgeQueryClient() as edge_client:
                        # Simple preview for Iceberg
                        results = edge_client.query_sql(
                            request.output.output,
                            f"SELECT * FROM df LIMIT {request.output.head or 10}",
                        )
                        from rich.table import Table

                        table = Table(title=f"Preview of {request.output.output}")
                        for col in results.columns:
                            table.add_column(col)
                        for _, row in results.iterrows():
                            table.add_row(*[str(val) for val in row])
                        self.console.print(table)
                except Exception as e:
                    self.console.print(f"[red]Failed to inspect Iceberg table: {e}[/red]")
        return 0

        if not is_iceberg:
            # Security: Validate path before inspection
            try:
                validated_path = self._validate_path(request.output)
            except ValueError as e:
                if self.console:
                    self.console.print(f"[red]Error: {e}[/red]")
                return -1

            inspect_parquet(
                path=str(validated_path),
                head=request.head or 10,
                metadata_only=request.metadata_only,
            )
        else:
            if self.console:
                self.console.print(f"[cyan]Inspecting Iceberg Table: {request.output}[/cyan]")
                try:
                    with EdgeQueryClient() as edge_client:
                        # Simple preview for Iceberg
                        results = edge_client.query_sql(
                            request.output, f"SELECT * FROM df LIMIT {request.head or 10}"
                        )
                        from rich.table import Table

                        table = Table(title=f"Preview of {request.output}")
                        for col in results.columns:
                            table.add_column(col)
                        for _, row in results.iterrows():
                            table.add_row(*[str(val) for val in row])
                        self.console.print(table)
                except Exception as e:
                    self.console.print(f"[red]Failed to inspect Iceberg table: {e}[/red]")
        return 0

    def _fetch_data_with_progress(self, fetch_func: Any) -> Any:
        """Helper to run a fetch function with rich progress bar if console is available."""
        if self.console:
            from rich.progress import Progress, SpinnerColumn, TextColumn

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                progress.add_task("Fetching data...", total=None)
                return fetch_func()
        else:
            return fetch_func()

    def _ensure_parent_exists(self, path: Path) -> None:
        """Ensure the parent directory of a path exists."""
        parent = path.parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    def _export_results(self, scanner: Any, output: str, metadata: dict[str, Any]) -> None:
        """Helper to handle exporting results to various formats."""
        try:
            output_path = self._validate_path(output)
            self._ensure_parent_exists(output_path)
        except ValueError as e:
            if self.console:
                self.console.print(f"[red]Error: {e}[/red]")
            return

        output_lower = str(output_path).lower()

        if output_lower.endswith(".csv"):
            scanner.export(str(output_path), "csv", include_index=False, metadata=metadata)
        elif output_lower.endswith(".json"):
            scanner.export(str(output_path), "json", orient="records", metadata=metadata)
        elif output_lower.endswith(".parquet"):
            scanner.export(str(output_path), "parquet", include_index=False, metadata=metadata)
        elif output_lower.endswith(".xml"):
            scanner.export(str(output_path), "xml", include_index=False, metadata=metadata)
        else:
            if self.console:
                self.console.print(f"[yellow]Unknown output format: {output}[/yellow]")
            return

        if self.console:
            self.console.print(f"[green]Saved to {output_path}[/green]")

    def _build_opportunity_config(self, request: ScanRequest) -> ForexScreenerConfig:
        score_filters = []
        if request.assets.min_ma_score is not None:
            score_filters.append(ScoreFilter("ma", request.assets.min_ma_score))

        roc_filter = (
            RocFilter(min_roc=request.assets.min_roc)
            if request.assets.min_roc is not None
            else None
        )
        volume_filter = (
            VolumeFilter(min_volume=request.assets.min_volume)
            if request.assets.min_volume is not None
            else None
        )

        include_atr = (
            request.assets.include_atr
            or request.assets.max_atr is not None
            or request.output.show_risk
        )
        include_rsi = request.assets.include_rsi or bool(request.scoring.mr_signal)

        scoring_config = ScoreWeights(
            trend_weight=request.scoring.opportunity_trend_weight
            if request.scoring.opportunity_trend_weight is not None
            else 0.4,
            ma_weight=request.scoring.opportunity_ma_weight
            if request.scoring.opportunity_ma_weight is not None
            else 0.3,
            osc_weight=request.scoring.opportunity_osc_weight
            if request.scoring.opportunity_osc_weight is not None
            else 0.2,
            roc_weight=request.scoring.opportunity_roc_weight
            if request.scoring.opportunity_roc_weight is not None
            else 0.1,
        )

        timeframe_weights = self._parse_timeframe_weights(
            request.scoring.opportunity_timeframe_weights
        )

        atr_filter = (
            AtrFilter(max_atr=request.assets.max_atr)
            if request.assets.max_atr is not None
            else None
        )

        return ForexScreenerConfig(
            scoring_config=scoring_config,
            timeframe_weights=timeframe_weights,
            score_filters=tuple(score_filters),
            roc_filter=roc_filter,
            volume_filter=volume_filter,
            include_atr=include_atr,
            include_rsi=include_rsi,
            atr_filter=atr_filter,
            contract_type=cast(ContractType, request.assets.contract_type or "cfd"),
            min_rvol=request.assets.min_rvol,
            show_risk=request.output.show_risk,
            risk_per_trade_pct=request.risk.risk_per_trade_pct
            if request.risk.risk_per_trade_pct is not None
            else 1.0,
            atr_multiplier=request.risk.atr_multiplier
            if request.risk.atr_multiplier is not None
            else 2.0,
            min_risk_reward_ratio=request.risk.min_risk_reward_ratio
            if request.risk.min_risk_reward_ratio is not None
            else 1.5,
            account_balance=request.risk.account_balance
            if request.risk.account_balance is not None
            else 10000.0,
            pip_value=request.risk.pip_value if request.risk.pip_value is not None else 10.0,
        )

    def _build_strategy_config(self, request: ScanRequest) -> StrategyConfig:
        strategy_map = {
            "trend": "trend_following",
            "mean_reversion": "mean_reversion",
            "hybrid": "hybrid",
            "breakout": "breakout",
            "confluence": "confluence",
            "all": "all",
        }
        strategy_name = strategy_map.get(request.assets.strategy, "all")
        if strategy_name == "all":
            strategy_tuple = cast(tuple[StrategyType, ...], ("all",))
        else:
            strategy_tuple = (cast(StrategyType, strategy_name),)
        mr_signals = tuple(request.scoring.mr_signal) if request.scoring.mr_signal else ()

        return StrategyConfig(
            include_strategies=strategy_tuple,
            direction=request.scoring.filter_direction or Direction.ALL,
            min_confluence=request.scoring.min_confluence
            if request.scoring.min_confluence is not None
            else 1,
            trend_threshold=request.scoring.trend_threshold
            if request.scoring.trend_threshold is not None
            else 0.0,
            mr_threshold=request.scoring.mr_threshold
            if request.scoring.mr_threshold is not None
            else 0.2,
            rsi_lower=request.scoring.rsi_lower if request.scoring.rsi_lower is not None else 30.0,
            rsi_upper=request.scoring.rsi_upper if request.scoring.rsi_upper is not None else 70.0,
            min_roc=request.assets.min_roc,
            min_volume=request.assets.min_volume,
            max_atr=request.assets.max_atr,
            min_ma_score=request.assets.min_ma_score,
            mean_reversion_signals=mr_signals,
            contract_type=cast(ContractType, request.assets.contract_type or "cfd"),
            include_atr_fields=request.assets.include_atr
            or request.assets.max_atr is not None
            or request.output.show_risk,
            include_rsi_fields=request.assets.include_rsi or bool(request.scoring.mr_signal),
            min_tf_alignment=request.scoring.min_tf_alignment
            if request.scoring.min_tf_alignment is not None
            else 1,
            require_momentum=request.scoring.require_momentum,
            min_rvol=request.assets.min_rvol,
            require_volume_spike=request.assets.require_volume_spike,
            risk_per_trade_pct=request.risk.risk_per_trade_pct
            if request.risk.risk_per_trade_pct is not None
            else 1.0,
            atr_multiplier=request.risk.atr_multiplier
            if request.risk.atr_multiplier is not None
            else 2.0,
            min_risk_reward_ratio=request.risk.min_risk_reward_ratio
            if request.risk.min_risk_reward_ratio is not None
            else 1.5,
            account_balance=request.risk.account_balance
            if request.risk.account_balance is not None
            else 10000.0,
            pip_value=request.risk.pip_value if request.risk.pip_value is not None else 10.0,
            show_risk=request.output.show_risk,
        )

    def _parse_timeframe_weights(self, spec: str | None) -> dict[str, float]:
        return parse_timeframe_weights(spec, default=dict(DEFAULT_TIMEFRAME_WEIGHTS))

    def _build_opportunity_metadata(self, request: ScanRequest) -> dict[str, Any]:
        return {
            "scanner": "opportunity",
            "filters": {
                "min_volume": request.assets.min_volume,
                "max_atr": request.assets.max_atr,
                "min_ma_score": request.assets.min_ma_score,
                "contract_type": request.assets.contract_type,
                "include_atr": request.assets.include_atr,
                "include_rsi": request.assets.include_rsi,
            },
            "scoring_weights": {
                "trend": request.scoring.opportunity_trend_weight,
                "ma": request.scoring.opportunity_ma_weight,
                "osc": request.scoring.opportunity_osc_weight,
                "roc": request.scoring.opportunity_roc_weight,
            },
            "timeframes": request.assets.timeframes,
            "timeframe_weights": self._parse_timeframe_weights(
                request.scoring.opportunity_timeframe_weights
            ),
        }

    def _build_strategy_metadata(self, request: ScanRequest) -> dict[str, Any]:
        return {
            "scanner": "strategy",
            "strategy": request.assets.strategy,
            "filters": {
                "min_volume": request.assets.min_volume,
                "max_atr": request.assets.max_atr,
                "min_ma_score": request.assets.min_ma_score,
                "min_confluence": request.scoring.min_confluence,
                "trend_threshold": request.scoring.trend_threshold,
                "mr_threshold": request.scoring.mr_threshold,
                "min_roc": request.assets.min_roc,
                "filter": request.scoring.filter_direction,
            },
            "scoring_weights": {
                "trend": request.scoring.opportunity_trend_weight,
                "ma": request.scoring.opportunity_ma_weight,
                "osc": request.scoring.opportunity_osc_weight,
                "roc": request.scoring.opportunity_roc_weight,
            },
            "timeframes": request.assets.timeframes,
        }

    def _filter_by_confluence(
        self,
        df: pd.DataFrame,
        grade: str | None = None,
        min_confluence: int | None = None,
    ) -> pd.DataFrame:
        """Filter DataFrame by confluence grade or minimum score."""
        if df.empty:
            return df

        if grade:
            grade_order = {"A+": 6, "A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
            min_grade_value = grade_order.get(grade, 0)
            df = df[df["GRADE"].map(grade_order).fillna(0) >= min_grade_value]

        if min_confluence is not None:
            df = df[df["TOTAL_CONFLUENCE"] >= min_confluence]

        return df

    def _validate_path(self, path_str: str, base_dir: Path | None = None) -> Path:
        """
        Internal wrapper for path validation.
        Uses the robust utility function from util.py.
        """
        return validate_path(path_str, base_dir=base_dir)

    def _maybe_save_opportunity_config(self, path: str, request: ScanRequest) -> None:
        payload = {
            "min_volume": request.assets.min_volume,
            "max_atr": request.assets.max_atr,
            "min_ma_score": request.assets.min_ma_score,
            "include_atr": request.assets.include_atr,
            "include_rsi": request.assets.include_rsi,
            "opportunity_trend_weight": request.scoring.opportunity_trend_weight,
            "opportunity_ma_weight": request.scoring.opportunity_ma_weight,
            "opportunity_osc_weight": request.scoring.opportunity_osc_weight,
            "opportunity_roc_weight": request.scoring.opportunity_roc_weight,
            "opportunity_timeframe_weights": request.scoring.opportunity_timeframe_weights,
            "contract_type": request.assets.contract_type,
            "timeframes": request.assets.timeframes,
        }
        try:
            validated_path = self._validate_path(path)
        except ValueError as e:
            logger.error("Cannot save config: %s", e)
            return

        directory = validated_path.parent
        if directory and not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
        with open(validated_path, "w") as fh:
            yaml.safe_dump(payload, fh)
        logger.info("Saved opportunity config to %s", validated_path)
