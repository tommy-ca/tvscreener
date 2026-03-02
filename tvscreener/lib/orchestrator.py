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
from tvscreener.lib.lakehouse.catalog import IcebergCatalogManager
from tvscreener.lib.screeners.base import BaseOpportunityScreener
from tvscreener.lib.screeners.factory import AssetScreenerFactory
from tvscreener.lib.screeners.forex_opportunity import ContractType, ForexScreenerConfig
from tvscreener.lib.screeners.forex_strategy import (
    ForexStrategyScanner,
    StrategyConfig,
    StrategyType,
)
from tvscreener.score import ScoringConfig
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
class ScanRequest:
    """Unified scan request parameters."""

    # === Routing & Asset Selection ===
    scanner: str = "strategy"
    asset_type: str = "forex"
    universe: str | None = None
    pairs: list[str] | None = None
    timeframes: str | None = None
    contract_type: str | None = None

    # === Pre-calculated Filters ===
    min_volume: float | None = None
    max_atr: float | None = None
    min_ma_score: float | None = None
    min_roc: float | None = None

    # === Data Enrichment Options ===
    include_atr: bool = False
    include_rsi: bool = False

    # === Scoring: Opportunity Screener ===
    opportunity_trend_weight: float | None = None
    opportunity_ma_weight: float | None = None
    opportunity_osc_weight: float | None = None
    opportunity_roc_weight: float | None = None
    opportunity_timeframe_weights: str | None = None
    confluence_grade: str | None = None
    min_opportunity_confluence: int | None = None

    # === Scoring: Strategy Scanner ===
    strategy: str = "all"
    filter_direction: Direction | str | None = None  # Direction.LONG, Direction.SHORT
    min_confluence: int | None = None
    trend_threshold: float | None = None
    mr_threshold: float | None = None
    rsi_lower: float | None = None
    rsi_upper: float | None = None
    mr_signal: list[str] = field(default_factory=list)
    min_tf_alignment: int | None = None
    require_momentum: bool = False
    min_rvol: float | None = None
    require_volume_spike: bool = False
    filters: list[str] = field(default_factory=list)
    sql: str | None = None

    # === Risk Management ===
    risk_per_trade_pct: float | None = None
    atr_multiplier: float | None = None
    min_risk_reward_ratio: float | None = None
    account_balance: float | None = None
    pip_value: float | None = None

    # === Output & Control ===
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
        settings = load_settings(request.config_path)

        if request.universe is None:
            request.universe = settings.default_universe
        if request.timeframes is None:
            request.timeframes = settings.default_timeframes
        if request.contract_type is None:
            request.contract_type = settings.contract_type

        if request.contract_type is not None:
            valid_contracts = ("spot", "cfd", "spreadbet", "all")
            if request.contract_type not in valid_contracts:
                raise ConfigurationError(
                    f"Invalid contract type: {request.contract_type}. Valid options: {', '.join(valid_contracts)}"
                )

        # Scoped defaults: use opportunity settings if scanner is 'opportunity', else fallback to general
        def _resolve_val(attr: str, scanner: str) -> Any:
            # Check if request already has a value
            req_val = getattr(request, attr)
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

        request.min_volume = _resolve_val("min_volume", request.scanner)
        request.max_atr = _resolve_val("max_atr", request.scanner)
        request.min_ma_score = _resolve_val("min_ma_score", request.scanner)

        if request.min_confluence is None:
            request.min_confluence = settings.min_confluence
        if request.trend_threshold is None:
            request.trend_threshold = settings.trend_threshold
        if request.mr_threshold is None:
            request.mr_threshold = settings.mr_threshold
        if request.rsi_lower is None:
            request.rsi_lower = settings.rsi_lower
        if request.rsi_upper is None:
            request.rsi_upper = settings.rsi_upper
        if request.min_roc is None:
            request.min_roc = settings.min_roc

        # Opportunity weights
        if request.opportunity_trend_weight is None:
            request.opportunity_trend_weight = settings.opportunity.trend_weight
        if request.opportunity_ma_weight is None:
            request.opportunity_ma_weight = settings.opportunity.ma_weight
        if request.opportunity_osc_weight is None:
            request.opportunity_osc_weight = settings.opportunity.osc_weight
        if request.opportunity_roc_weight is None:
            request.opportunity_roc_weight = settings.opportunity.roc_weight
        if request.opportunity_timeframe_weights is None:
            request.opportunity_timeframe_weights = settings.opportunity.timeframe_weights

        # Risk management defaults
        if request.min_tf_alignment is None:
            request.min_tf_alignment = settings.risk.min_tf_alignment
        if request.min_rvol is None:
            request.min_rvol = settings.risk.min_rvol
        if request.risk_per_trade_pct is None:
            request.risk_per_trade_pct = settings.risk.risk_per_trade_pct
        if request.atr_multiplier is None:
            request.atr_multiplier = settings.risk.atr_multiplier
        if request.min_risk_reward_ratio is None:
            request.min_risk_reward_ratio = settings.risk.min_risk_reward_ratio
        if request.account_balance is None:
            request.account_balance = settings.risk.account_balance

        return request

    def run_scan(self, request: ScanRequest) -> int:
        """Main entry point to run a scan."""
        request = self.resolve_defaults(request)

        if request.scanner == "opportunity":
            return self.run_opportunity_scan(request)
        elif request.scanner == "strategy":
            return self.run_strategy_scan(request)
        elif request.scanner == "inspect":
            return self.run_inspect_parquet(request)
        else:
            raise ValueError(f"Unknown scanner type: {request.scanner}")

    def run_maintenance(self, args: argparse.Namespace) -> int:
        """Run lakehouse maintenance tasks."""
        if self.console:
            self.console.print("[bold cyan]Running Lakehouse Maintenance...[/bold cyan]")

        manager = IcebergCatalogManager()
        table_name = getattr(args, "table", "forex.opportunities")

        if getattr(args, "expire_snapshots", False):
            days = getattr(args, "days", 7)
            if self.console:
                self.console.print(
                    f" - Expiring snapshots older than {days} days for {table_name}..."
                )
            manager.expire_snapshots(table_name, days)

        if getattr(args, "compact", False):
            if self.console:
                self.console.print(f" - Compacting files for {table_name}...")
            manager.compact_files(table_name)

        if self.console:
            self.console.print("[bold green]Maintenance complete.[/bold green]")
        return 0

    def run_from_args(self, args: argparse.Namespace) -> int:
        """Run scan from argparse namespace."""
        command = getattr(args, "command", "scan")
        if command == "maintenance":
            return self.run_maintenance(args)

        request = ScanRequest(
            scanner=args.scanner,
            asset_type=args.asset_type,
            universe=args.universe,
            pairs=args.pairs,
            timeframes=args.timeframes,
            contract_type=args.contract_type,
            min_volume=args.min_volume,
            max_atr=args.max_atr,
            min_ma_score=args.min_ma_score,
            min_roc=args.min_roc,
            include_atr=args.include_atr,
            include_rsi=args.include_rsi,
            opportunity_trend_weight=args.opportunity_trend_weight,
            opportunity_ma_weight=args.opportunity_ma_weight,
            opportunity_osc_weight=args.opportunity_osc_weight,
            opportunity_roc_weight=args.opportunity_roc_weight,
            opportunity_timeframe_weights=args.opportunity_timeframe_weights,
            confluence_grade=args.confluence_grade,
            min_opportunity_confluence=args.min_opportunity_confluence,
            strategy=args.strategy,
            filter_direction=getattr(args, "direction", None),
            filters=getattr(args, "filter", []) or [],
            sql=getattr(args, "sql", None),
            min_confluence=args.min_confluence,
            trend_threshold=args.trend_threshold,
            mr_threshold=args.mr_threshold,
            rsi_lower=args.rsi_lower,
            rsi_upper=args.rsi_upper,
            mr_signal=args.mr_signal or [],
            min_tf_alignment=args.min_tf_alignment,
            require_momentum=args.require_momentum,
            min_rvol=args.min_rvol,
            require_volume_spike=args.require_volume_spike,
            risk_per_trade_pct=args.risk_per_trade,
            atr_multiplier=args.atr_multiplier,
            min_risk_reward_ratio=args.min_risk_reward,
            account_balance=args.account_balance,
            output=args.output,
            detailed=args.detailed,
            matrix=args.matrix,
            limit=args.limit,
            head=args.head,
            metadata_only=args.metadata_only,
            save_config=args.save_config,
            config_path=args.config,
            verbose=args.verbose,
            show_risk=getattr(args, "show_risk", False),
        )
        return self.run_scan(request)

    def run_opportunity_scan(self, request: ScanRequest) -> int:
        """Run opportunity screener and handle output."""
        results, screener = self.get_opportunity_results(request)

        metadata = self._build_opportunity_metadata(request)

        output_path = request.output
        if request.sql and not output_path:
            output_path = "exports/.cache/tvscreener_edge_cache.parquet"

        if output_path:
            self._export_results(screener, output_path, metadata)

        if request.sql:
            from tvscreener.lib.query import EdgeQueryClient

            try:
                with EdgeQueryClient() as edge_client:
                    results = edge_client.query_sql(cast(str, output_path), request.sql)

                if self.console:
                    if results.empty:
                        self.console.print("[yellow]Edge query returned 0 rows.[/yellow]")
                    else:
                        # Restore specialized view parity: pass SQL results back to renderer
                        screener.print_summary(
                            results_df=results,
                            detailed=request.detailed,
                            matrix=request.matrix,
                            limit=request.limit,
                            show_risk=request.show_risk,
                        )
                return len(results)
            except Exception as e:
                if self.console:
                    self.console.print(
                        "[red]Edge Query execution failed. Check logs for details.[/red]"
                    )
                logger.error("Edge Query execution failed: %s", e)
                return 0

        if self.console:
            screener.print_summary(
                detailed=request.detailed,
                matrix=request.matrix,
                limit=request.limit,
                show_risk=request.show_risk,
            )

        if request.save_config:
            self._maybe_save_opportunity_config(request.save_config, request)

        return len(results)

    def get_opportunity_results(
        self, request: ScanRequest
    ) -> tuple[pd.DataFrame, BaseOpportunityScreener]:
        """Run opportunity screener and return results + screener instance."""
        request = self.resolve_defaults(request)
        pairs = self.get_pairs(request.universe, request.pairs)
        timeframes = request.timeframes.split(",") if request.timeframes else ["15", "60", "240"]

        if self.console:
            self.console.print(f"[cyan]Scanning {len(pairs)} {request.asset_type} pairs...[/cyan]")

        config = self._build_opportunity_config(request)
        screener = AssetScreenerFactory.create_screener(
            asset_type=request.asset_type, symbols=pairs, timeframes=timeframes, config=config
        )

        if request.sql:
            # We record SQL and filters in metadata even if they are handled at the edge
            screener.metadata.config["sql"] = request.sql
        for f in request.filters:
            screener.metadata.config.setdefault("cli_filters", []).append(f)

        results = self._fetch_data_with_progress(screener.get_opportunities)

        if request.confluence_grade or request.min_opportunity_confluence:
            results = self._filter_by_confluence(
                results,
                grade=request.confluence_grade,
                min_confluence=request.min_opportunity_confluence,
            )

        return results, screener

    def run_strategy_scan(self, request: ScanRequest) -> int:
        """Run strategy scanner and handle output."""
        results, scanner = self.get_strategy_results(request)

        metadata = self._build_strategy_metadata(request)

        output_path = request.output
        if request.sql and not output_path:
            output_path = "exports/.cache/tvscreener_edge_cache.parquet"

        if output_path:
            self._export_results(scanner, output_path, metadata)

        if request.sql:
            from tvscreener.lib.query import EdgeQueryClient

            try:
                with EdgeQueryClient() as edge_client:
                    results = edge_client.query_sql(cast(str, output_path), request.sql)

                if self.console:
                    if results.empty:
                        self.console.print("[yellow]Edge query returned 0 rows.[/yellow]")
                    else:
                        # Restore specialized view parity: pass SQL results back to renderer
                        scanner.print_summary(
                            results_df=results,
                            detailed=request.detailed,
                            matrix=request.matrix,
                            limit=request.limit,
                            show_risk=request.show_risk,
                        )
                return len(results)
            except Exception as e:
                if self.console:
                    self.console.print(
                        "[red]Edge Query execution failed. Check logs for details.[/red]"
                    )
                logger.error(f"Edge Query execution failed: {e}")
                return 0

        if self.console:
            scanner.print_summary(
                detailed=request.detailed,
                matrix=request.matrix,
                limit=request.limit,
                show_risk=request.show_risk,
            )

        return len(results)

    def get_strategy_results(
        self, request: ScanRequest
    ) -> tuple[pd.DataFrame, ForexStrategyScanner]:
        """Run strategy scanner and return results + scanner instance."""
        request = self.resolve_defaults(request)
        pairs = self.get_pairs(request.universe, request.pairs)
        timeframes = request.timeframes.split(",") if request.timeframes else ["15", "60", "240"]

        if self.console:
            self.console.print(
                f"[cyan]Scanning {len(pairs)} {request.asset_type} pairs for {request.strategy} signals...[/cyan]"
            )

        config = self._build_strategy_config(request)
        scanner = ForexStrategyScanner(pairs=pairs, timeframes=timeframes, config=config)

        if request.sql:
            scanner._screener.metadata.config["sql"] = request.sql
        for f in request.filters:
            scanner._screener.metadata.config.setdefault("cli_filters", []).append(f)

        results = self._fetch_data_with_progress(scanner.scan)

        return results, scanner

    def run_inspect_parquet(self, request: ScanRequest) -> int:
        """Inspect a parquet file or Iceberg table."""
        from tvscreener.lib.inspect_utils import inspect_parquet
        from tvscreener.lib.query import EdgeQueryClient

        if not request.output:
            if self.console:
                self.console.print(
                    "[red]Error: Please specify a file or table to inspect using --output or -o[/red]"
                )
            return -1

        # Check if it looks like an Iceberg table identifier
        is_iceberg = (
            "." in request.output
            and not any(
                request.output.endswith(ext) for ext in [".parquet", ".csv", ".json", ".xml"]
            )
            and not Path(request.output).exists()
        )

        if request.sql:
            try:
                with EdgeQueryClient() as edge_client:
                    results = edge_client.query_sql(request.output, request.sql)

                if self.console:
                    if results.empty:
                        self.console.print("[yellow]Edge query returned 0 rows.[/yellow]")
                    else:
                        from rich.table import Table

                        table = Table(title=f"SQL Results from {request.output}")
                        for col in results.columns:
                            table.add_column(col)
                        for _, row in results.head(request.head or 10).iterrows():
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
        if request.min_ma_score is not None:
            score_filters.append(ScoreFilter("ma", request.min_ma_score))

        roc_filter = RocFilter(min_roc=request.min_roc) if request.min_roc is not None else None
        volume_filter = (
            VolumeFilter(min_volume=request.min_volume) if request.min_volume is not None else None
        )

        include_atr = request.include_atr or request.max_atr is not None or request.show_risk
        include_rsi = request.include_rsi or bool(request.mr_signal)

        scoring_config = ScoringConfig(
            trend_weight=request.opportunity_trend_weight
            if request.opportunity_trend_weight is not None
            else 0.4,
            ma_weight=request.opportunity_ma_weight
            if request.opportunity_ma_weight is not None
            else 0.3,
            osc_weight=request.opportunity_osc_weight
            if request.opportunity_osc_weight is not None
            else 0.2,
            roc_weight=request.opportunity_roc_weight
            if request.opportunity_roc_weight is not None
            else 0.1,
        )

        timeframe_weights = self._parse_timeframe_weights(request.opportunity_timeframe_weights)

        atr_filter = AtrFilter(max_atr=request.max_atr) if request.max_atr is not None else None

        return ForexScreenerConfig(
            scoring_config=scoring_config,
            timeframe_weights=timeframe_weights,
            score_filters=tuple(score_filters),
            roc_filter=roc_filter,
            volume_filter=volume_filter,
            include_atr=include_atr,
            include_rsi=include_rsi,
            atr_filter=atr_filter,
            contract_type=cast(ContractType, request.contract_type or "cfd"),
            min_rvol=request.min_rvol,
            show_risk=request.show_risk,
            risk_per_trade_pct=request.risk_per_trade_pct
            if request.risk_per_trade_pct is not None
            else 1.0,
            atr_multiplier=request.atr_multiplier if request.atr_multiplier is not None else 2.0,
            min_risk_reward_ratio=request.min_risk_reward_ratio
            if request.min_risk_reward_ratio is not None
            else 1.5,
            account_balance=request.account_balance
            if request.account_balance is not None
            else 10000.0,
            pip_value=request.pip_value if request.pip_value is not None else 10.0,
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
        strategy_name = strategy_map.get(request.strategy, "all")
        if strategy_name == "all":
            strategy_tuple = cast(tuple[StrategyType, ...], ("all",))
        else:
            strategy_tuple = (cast(StrategyType, strategy_name),)
        mr_signals = tuple(request.mr_signal) if request.mr_signal else ()

        return StrategyConfig(
            include_strategies=strategy_tuple,
            direction=request.filter_direction or Direction.ALL,
            min_confluence=request.min_confluence if request.min_confluence is not None else 1,
            trend_threshold=request.trend_threshold if request.trend_threshold is not None else 0.0,
            mr_threshold=request.mr_threshold if request.mr_threshold is not None else 0.2,
            rsi_lower=request.rsi_lower if request.rsi_lower is not None else 30.0,
            rsi_upper=request.rsi_upper if request.rsi_upper is not None else 70.0,
            min_roc=request.min_roc,
            min_volume=request.min_volume,
            max_atr=request.max_atr,
            min_ma_score=request.min_ma_score,
            mean_reversion_signals=mr_signals,
            contract_type=cast(ContractType, request.contract_type or "cfd"),
            include_atr_fields=request.include_atr
            or request.max_atr is not None
            or request.show_risk,
            include_rsi_fields=request.include_rsi or bool(request.mr_signal),
            min_tf_alignment=request.min_tf_alignment
            if request.min_tf_alignment is not None
            else 1,
            require_momentum=request.require_momentum,
            min_rvol=request.min_rvol,
            require_volume_spike=request.require_volume_spike,
            risk_per_trade_pct=request.risk_per_trade_pct
            if request.risk_per_trade_pct is not None
            else 1.0,
            atr_multiplier=request.atr_multiplier if request.atr_multiplier is not None else 2.0,
            min_risk_reward_ratio=request.min_risk_reward_ratio
            if request.min_risk_reward_ratio is not None
            else 1.5,
            account_balance=request.account_balance
            if request.account_balance is not None
            else 10000.0,
            pip_value=request.pip_value if request.pip_value is not None else 10.0,
            show_risk=request.show_risk,
        )

    def _parse_timeframe_weights(self, spec: str | None) -> dict[str, float]:
        return parse_timeframe_weights(spec, default=dict(DEFAULT_TIMEFRAME_WEIGHTS))

    def _build_opportunity_metadata(self, request: ScanRequest) -> dict[str, Any]:
        return {
            "scanner": "opportunity",
            "filters": {
                "min_volume": request.min_volume,
                "max_atr": request.max_atr,
                "min_ma_score": request.min_ma_score,
                "contract_type": request.contract_type,
                "include_atr": request.include_atr,
                "include_rsi": request.include_rsi,
            },
            "scoring_weights": {
                "trend": request.opportunity_trend_weight,
                "ma": request.opportunity_ma_weight,
                "osc": request.opportunity_osc_weight,
                "roc": request.opportunity_roc_weight,
            },
            "timeframes": request.timeframes,
            "timeframe_weights": self._parse_timeframe_weights(
                request.opportunity_timeframe_weights
            ),
        }

    def _build_strategy_metadata(self, request: ScanRequest) -> dict[str, Any]:
        return {
            "scanner": "strategy",
            "strategy": request.strategy,
            "filters": {
                "min_volume": request.min_volume,
                "max_atr": request.max_atr,
                "min_ma_score": request.min_ma_score,
                "min_confluence": request.min_confluence,
                "trend_threshold": request.trend_threshold,
                "mr_threshold": request.mr_threshold,
                "min_roc": request.min_roc,
                "filter": request.filter_direction,
            },
            "scoring_weights": {
                "trend": request.opportunity_trend_weight,
                "ma": request.opportunity_ma_weight,
                "osc": request.opportunity_osc_weight,
                "roc": request.opportunity_roc_weight,
            },
            "timeframes": request.timeframes,
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
            "min_volume": request.min_volume,
            "max_atr": request.max_atr,
            "min_ma_score": request.min_ma_score,
            "include_atr": request.include_atr,
            "include_rsi": request.include_rsi,
            "opportunity_trend_weight": request.opportunity_trend_weight,
            "opportunity_ma_weight": request.opportunity_ma_weight,
            "opportunity_osc_weight": request.opportunity_osc_weight,
            "opportunity_roc_weight": request.opportunity_roc_weight,
            "opportunity_timeframe_weights": request.opportunity_timeframe_weights,
            "contract_type": request.contract_type,
            "timeframes": request.timeframes,
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
