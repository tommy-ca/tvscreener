#!/usr/bin/env python3
"""Orchestrator for screener execution and configuration."""

from __future__ import annotations

import argparse
import logging
import os
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
from tvscreener.constants.market_risk import (
    MARKET_RISK_FUTURES_TICKERS,
    MARKET_RISK_PROXY_TICKERS,
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
from tvscreener.lib.screeners.registry import ScreenerFamilyRegistry
from tvscreener.score import ScoringConfig as ScoreWeights
from tvscreener.util import canonicalize_asset_type, parse_timeframe_weights, validate_path

if TYPE_CHECKING:
    import pandas as pd
    from rich.console import Console

logger = logging.getLogger(__name__)

UNIVERSE_MAP: dict[str, AssetUniverse] = {
    "forex": FOREX_UNIVERSE,
    "stock": STOCK_UNIVERSE,
    "crypto": CRYPTO_UNIVERSE,
    "futures": COMMODITY_UNIVERSE,
    # Aliases for CLI/backwards compatibility
    "stocks": STOCK_UNIVERSE,
    "commodity": COMMODITY_UNIVERSE,
}


@dataclass
class AssetSelection:
    """Routing and asset selection parameters."""

    scanner: str = "strategy"
    pipeline: str = "both"  # data | analytics | both
    strategy: str = "all"
    asset_type: str = "forex"
    universe: str | None = None
    pairs: list[str] | None = None
    timeframes: str | None = None
    contract_type: str | None = None
    instrument_type: str | None = None
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
        self._family_registry = ScreenerFamilyRegistry()
        self._family_registry.register("opportunity", self.run_opportunity_scan)
        self._family_registry.register("strategy", self.run_strategy_scan)
        self._family_registry.register("inspect", self.run_inspect_parquet)

    def get_universe(self, asset_type: str) -> AssetUniverse:
        """Get universe config by asset type with validation."""
        asset_type = canonicalize_asset_type(asset_type)
        if asset_type not in UNIVERSE_MAP:
            raise ConfigurationError(
                f"Unknown asset type: {asset_type}. Valid options: {', '.join(UNIVERSE_MAP.keys())}"
            )
        return UNIVERSE_MAP[asset_type]

    def get_pairs(
        self,
        asset_type: str,
        universe: str | None,
        specific: list[str] | None,
        *,
        instrument_type: str | None = None,
    ) -> list[str]:
        """Resolve symbols based on asset type, universe selector, or explicit list."""
        if specific:
            return specific

        # Universe aliases for ergonomic CLI/config usage.
        universe_aliases = {
            "binance_spot_base": "binance_spot_tradeable_base",
            "binance_perp_base": "binance_perp_tradeable_base",
            "binance_spot_largecap": "binance_spot_tradeable_mcap_cs",
            "binance_perp_largecap": "binance_perp_tradeable_mcap_cs",
            "binance_spot_snapshot": "binance_spot_top100",
            "binance_perp_snapshot": "binance_perp_top100",
        }
        if asset_type == "crypto" and universe in {"majors", "minors"}:
            it = (instrument_type or "spot").strip().lower()
            venue = "perp" if it in {"perp", "swap"} else "spot"
            universe = f"binance_{venue}_{universe}"

        if universe:
            universe = universe_aliases.get(universe, universe)

        asset_type = canonicalize_asset_type(asset_type)
        if asset_type == "forex":
            if universe == "majors":
                return FOREX_MAJORS
            if universe == "minors":
                return FOREX_MINORS
            if universe in (None, "all"):
                return DEFAULT_FOREX_PAIRS
            # Unknown forex selector: fall back to default
            return DEFAULT_FOREX_PAIRS

        if universe in {"market_risk", "risk"}:
            if asset_type == "stock":
                return list(MARKET_RISK_PROXY_TICKERS)
            if asset_type == "futures":
                return list(MARKET_RISK_FUTURES_TICKERS)

        # Non-forex: use configured universe pairs
        if asset_type == "crypto" and universe in {"binance_spot_top100", "binance_perp_top100"}:
            from tvscreener.lib.universe.binance_crypto import (
                BinanceCryptoUniverseConstraints,
                build_binance_crypto_universe,
                maybe_write_universe_json,
            )

            instrument_type = "spot" if universe == "binance_spot_top100" else "perp"
            tickers, snapshot = build_binance_crypto_universe(
                constraints=BinanceCryptoUniverseConstraints(
                    instrument_type=instrument_type,
                    quote_assets=("USDT", "USDC"),
                    # Tune spot floor down to keep spot/perp universe sizes comparable.
                    min_quote_volume_usd=(2_500_000 if instrument_type == "spot" else 10_000_000),
                )
            )

            run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
            _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
            return tickers

        if asset_type == "crypto" and universe in {
            "binance_spot_mcap_top100",
            "binance_perp_mcap_top100",
        }:
            from tvscreener.lib.universe.binance_crypto import (
                BinanceCryptoMarketCapUniverseConstraints,
                build_binance_crypto_universe_market_cap,
                maybe_write_universe_json,
            )

            instrument_type = "spot" if universe == "binance_spot_mcap_top100" else "perp"
            tickers, snapshot = build_binance_crypto_universe_market_cap(
                constraints=BinanceCryptoMarketCapUniverseConstraints(
                    instrument_type=instrument_type,
                    min_volatility_24h_pct=0.0,
                )
            )

            run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
            _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
            return tickers

        if asset_type == "crypto" and universe in {
            "binance_spot_cs_momentum",
            "binance_perp_cs_momentum",
        }:
            from tvscreener.lib.universe.binance_crypto import (
                BinanceCryptoCSMomentumUniverseConstraints,
                build_binance_crypto_universe_cs_momentum,
                maybe_write_universe_json,
            )

            instrument_type = "spot" if universe == "binance_spot_cs_momentum" else "perp"
            tickers, snapshot = build_binance_crypto_universe_cs_momentum(
                constraints=BinanceCryptoCSMomentumUniverseConstraints(
                    instrument_type=instrument_type,
                    # Tune spot floor down to keep spot/perp universe sizes comparable.
                    min_quote_volume_usd=(1_700_000 if instrument_type == "spot" else 10_000_000),
                )
            )

            run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
            _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
            return tickers

        if asset_type == "crypto" and universe in {
            "binance_spot_tradeable_base",
            "binance_perp_tradeable_base",
        }:
            from tvscreener.lib.universe.binance_crypto import (
                BinanceCryptoTradeableBaseUniverseConstraints,
                build_binance_crypto_universe_tradeable_base,
                maybe_write_universe_json,
            )

            instrument_type = "spot" if universe == "binance_spot_tradeable_base" else "perp"
            tickers, snapshot = build_binance_crypto_universe_tradeable_base(
                constraints=BinanceCryptoTradeableBaseUniverseConstraints(
                    instrument_type=instrument_type,
                    # Tune defaults to keep spot/perp sizes comparable (~100).
                    min_quote_volume_usd=(2_500_000 if instrument_type == "spot" else 20_000_000),
                    top_n=200,
                )
            )

            run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
            _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
            return tickers

        if asset_type == "crypto" and universe in {
            "binance_spot_tradeable_mcap_cs",
            "binance_perp_tradeable_mcap_cs",
        }:
            from tvscreener.lib.universe.binance_crypto import (
                BinanceCryptoTradeableMcapOverlapUniverseConstraints,
                build_binance_crypto_universe_tradeable_mcap_overlap,
                maybe_write_universe_json,
            )

            instrument_type = "spot" if universe == "binance_spot_tradeable_mcap_cs" else "perp"
            tickers, snapshot = build_binance_crypto_universe_tradeable_mcap_overlap(
                constraints=BinanceCryptoTradeableMcapOverlapUniverseConstraints(
                    instrument_type=instrument_type,
                )
            )

            run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
            _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
            return tickers

        if asset_type == "crypto" and universe in {
            "binance_spot_majors",
            "binance_perp_majors",
            "binance_spot_minors",
            "binance_perp_minors",
        }:
            from tvscreener.lib.universe.binance_crypto import (
                BinanceCryptoMcapTierUniverseConstraints,
                build_binance_crypto_universe_mcap_tier,
                maybe_write_universe_json,
            )

            instrument_type = (
                "spot" if universe in {"binance_spot_majors", "binance_spot_minors"} else "perp"
            )
            tier = "majors" if universe.endswith("_majors") else "minors"
            rmin, rmax = (1, 20) if tier == "majors" else (21, 200)

            tickers, snapshot = build_binance_crypto_universe_mcap_tier(
                constraints=BinanceCryptoMcapTierUniverseConstraints(
                    instrument_type=instrument_type,
                    top_n_market_cap=200,
                    mcap_rank_min=rmin,
                    mcap_rank_max=rmax,
                    min_quote_volume_usd_spot=2_500_000,
                    min_quote_volume_usd_perp=20_000_000,
                    min_history_days=180,
                )
            )

            if isinstance(snapshot, dict):
                snapshot.setdefault("constraints", {})
                if isinstance(snapshot.get("constraints"), dict):
                    snapshot["constraints"]["tier"] = tier

            run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
            _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
            return tickers

        cfg = self.get_universe(asset_type)
        return list(cfg.pairs)

    def resolve_defaults(self, request: ScanRequest) -> ScanRequest:
        """Fill in missing parameters from settings."""
        request.assets.asset_type = canonicalize_asset_type(request.assets.asset_type)
        settings = load_settings(request.output.config_path)

        if request.assets.universe is None:
            request.assets.universe = settings.default_universe

        # Normalize universe aliases early so downstream routing is consistent.
        if request.assets.universe:
            request.assets.universe = {
                "binance_spot_base": "binance_spot_tradeable_base",
                "binance_perp_base": "binance_perp_tradeable_base",
                "binance_spot_largecap": "binance_spot_tradeable_mcap_cs",
                "binance_perp_largecap": "binance_perp_tradeable_mcap_cs",
                "binance_spot_snapshot": "binance_spot_top100",
                "binance_perp_snapshot": "binance_perp_top100",
            }.get(request.assets.universe, request.assets.universe)
        if request.assets.timeframes is None:
            request.assets.timeframes = settings.default_timeframes
        if request.assets.contract_type is None:
            request.assets.contract_type = settings.contract_type

        if (
            request.assets.asset_type == "crypto"
            and request.assets.universe
            in {
                "binance_spot_top100",
                "binance_perp_top100",
                "binance_spot_mcap_top100",
                "binance_perp_mcap_top100",
                "binance_spot_cs_momentum",
                "binance_perp_cs_momentum",
                "binance_spot_tradeable_base",
                "binance_perp_tradeable_base",
                "binance_spot_tradeable_mcap_cs",
                "binance_perp_tradeable_mcap_cs",
                "binance_spot_majors",
                "binance_perp_majors",
                "binance_spot_minors",
                "binance_perp_minors",
            }
            and getattr(request.assets, "instrument_type", None) is None
        ):
            request.assets.instrument_type = (
                "spot"
                if request.assets.universe
                in {
                    "binance_spot_top100",
                    "binance_spot_mcap_top100",
                    "binance_spot_cs_momentum",
                    "binance_spot_tradeable_base",
                    "binance_spot_tradeable_mcap_cs",
                }
                else "perp"
            )

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
        return self._family_registry.run(request.assets.scanner, request)

    def run_maintenance(self, args: argparse.Namespace) -> int:
        """Run lakehouse maintenance tasks."""
        if self.console:
            self.console.print("[bold cyan]Running Lakehouse Maintenance...[/bold cyan]")

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
        # Initialize lakehouse manager early so catalog config is consistent for the process.
        # This ensures CLI `--config` affects Iceberg catalog/warehouse selection.
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

        matrix_mode = args.matrix
        detailed_mode = args.detailed
        if not (matrix_mode or detailed_mode):
            matrix_mode = True

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
        target = getattr(args, "target", None)
        out_dir = getattr(args, "out_dir", None)
        if not target:
            return 2

        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown audit target: {target}[/red]")
            return 2

        import json
        import os
        from pathlib import Path

        out_base = Path(out_dir or "artifacts/audits/binance-universes")
        out_base.mkdir(parents=True, exist_ok=True)

        include_all = bool(getattr(args, "include_all", False))

        # Default audit set focuses on screener-style universes.
        universes = [
            "binance_spot_majors",
            "binance_perp_majors",
            "binance_spot_minors",
            "binance_perp_minors",
            "binance_spot_tradeable_base",
            "binance_perp_tradeable_base",
            "binance_spot_tradeable_mcap_cs",
            "binance_perp_tradeable_mcap_cs",
            "binance_spot_top100",
            "binance_perp_top100",
        ]

        if include_all:
            universes = universes + [
                "binance_spot_mcap_top100",
                "binance_perp_mcap_top100",
                "binance_spot_cs_momentum",
                "binance_perp_cs_momentum",
            ]

        report: dict[str, dict] = {}
        sets: dict[str, set[str]] = {}

        previous_run_dir = os.environ.get("TVSCREENER_RUN_DIR")
        for u in universes:
            run_dir = out_base / u
            run_dir.mkdir(parents=True, exist_ok=True)

            os.environ["TVSCREENER_RUN_DIR"] = str(run_dir)
            pairs = self.get_pairs("crypto", u, specific=None)
            sets[u] = set(pairs)

            def _quote_asset(ticker: str) -> str:
                sym = ticker.split(":", 1)[-1]
                if sym.endswith(".P"):
                    sym = sym[: -len(".P")]
                for q in ("USDT", "USDC", "BTC", "ETH", "TRY", "BRL", "EUR", "JPY", "GBP"):
                    if sym.endswith(q):
                        return q
                return "OTHER"

            quote_dist: dict[str, int] = {}
            for p in pairs:
                q = _quote_asset(p)
                quote_dist[q] = quote_dist.get(q, 0) + 1

            uni_path = run_dir / "universe.json"
            uni = None
            if uni_path.exists():
                try:
                    uni = json.loads(uni_path.read_text(encoding="utf-8"))
                except Exception:
                    uni = None

            errors: list[str] = []
            if len(pairs) != len(set(pairs)):
                errors.append("duplicates")
            if u.startswith("binance_perp") and any(not p.endswith(".P") for p in pairs):
                errors.append("perp_missing_dotP")
            if u.startswith("binance_spot") and any(p.endswith(".P") for p in pairs):
                errors.append("spot_has_dotP")
            if any(not p.startswith("BINANCE:") for p in pairs):
                errors.append("non_binance_ticker")

            if u in {"binance_spot_top100", "binance_perp_top100"} and len(pairs) < 100:
                errors.append("underfilled_top_n")

            if u in {"binance_spot_top100", "binance_perp_top100"}:
                allowed = {"USDT", "USDC"}
                extra_quotes = [q for q in quote_dist if q not in allowed]
                if extra_quotes:
                    errors.append("non_usdt_usdc_quotes")

            report[u] = {
                "count": len(pairs),
                "sample": pairs[:10],
                "quote_asset_dist": dict(
                    sorted(quote_dist.items(), key=lambda kv: (-kv[1], kv[0]))
                ),
                "universe_json": str(uni_path) if uni_path.exists() else None,
                "selection": (
                    uni.get("constraints", {}).get("selection") if isinstance(uni, dict) else None
                ),
                "diagnostics": (uni.get("diagnostics") if isinstance(uni, dict) else None),
                "requested_tickers": (
                    len(uni.get("requested_tickers", [])) if isinstance(uni, dict) else None
                ),
                "missing_tickers": (
                    len(uni.get("missing_tickers", [])) if isinstance(uni, dict) else None
                ),
                "included_bases": (
                    len(uni.get("included_bases", [])) if isinstance(uni, dict) else None
                ),
                "missing_bases": (
                    len(uni.get("missing_bases", [])) if isinstance(uni, dict) else None
                ),
                "errors": errors,
            }

        overlap: dict[str, dict[str, int]] = {}
        for a in universes:
            overlap[a] = {}
            for b in universes:
                overlap[a][b] = len(sets[a] & sets[b])

        payload = {"universes": report, "overlap": overlap}
        report_path = out_base / "report.json"
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        if self.console:
            self.console.print(f"[green]Wrote {report_path}[/green]")
            for u in universes:
                info = report[u]
                self.console.print(
                    f"- {u}: {info['count']} (missing_tickers={info['missing_tickers']}, missing_bases={info['missing_bases']})"
                )

        if previous_run_dir is None:
            os.environ.pop("TVSCREENER_RUN_DIR", None)
        else:
            os.environ["TVSCREENER_RUN_DIR"] = previous_run_dir

        return 0

    def run_report(self, args: argparse.Namespace) -> int:
        target = getattr(args, "target", None)
        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown report target: {target}[/red]")
            return 2

        in_dir = getattr(args, "in_dir", "artifacts/audits/binance-universes")
        out_dir = getattr(args, "out_dir", "artifacts/reports/binance-universes")

        from tvscreener.lib.reports.binance_universes import (
            generate_binance_universes_report,
        )

        paths = generate_binance_universes_report(in_dir=in_dir, out_dir=out_dir)
        if self.console:
            self.console.print(f"[green]Wrote {paths.report_json}[/green]")
            self.console.print(f"[green]Wrote {paths.report_md}[/green]")
        return 0

    def run_review(self, args: argparse.Namespace) -> int:
        target = getattr(args, "target", None)
        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown review target: {target}[/red]")
            return 2

        audit_out_dir = getattr(args, "audit_out_dir", "artifacts/audits/binance-universes")
        report_out_dir = getattr(args, "report_out_dir", "artifacts/reports/binance-universes")
        strict = bool(getattr(args, "strict", False))

        audit_args = argparse.Namespace(
            command="audit",
            target=target,
            out_dir=audit_out_dir,
            include_all=bool(getattr(args, "include_all", False)),
            verbose=getattr(args, "verbose", False),
            config=getattr(args, "config", None),
        )
        rc = self.run_audit(audit_args)
        if rc != 0:
            return rc

        # Strict mode: fail if any universe has errors.
        if strict:
            import json
            from pathlib import Path

            report_path = Path(audit_out_dir) / "report.json"
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                universes = (payload or {}).get("universes", {})
                has_errors = any((v or {}).get("errors") for v in universes.values())
                if has_errors:
                    if self.console:
                        self.console.print(
                            "[bold red]Review failed: audit errors present[/bold red]"
                        )
                    return 2
            except Exception:
                return 2

        report_args = argparse.Namespace(
            command="report",
            target=target,
            in_dir=audit_out_dir,
            out_dir=report_out_dir,
            verbose=getattr(args, "verbose", False),
            config=getattr(args, "config", None),
        )
        return self.run_report(report_args)

    def run_opportunity_scan(self, request: ScanRequest) -> int:
        """Run opportunity screener and handle output."""
        request = self.resolve_defaults(request)
        pipeline = (request.assets.pipeline or "both").strip().lower()
        if pipeline not in ("data", "analytics", "both"):
            pipeline = "both"

        # 1) Data pipeline (fetch + Iceberg)
        if pipeline in ("data", "both"):
            _results, _screener = self.get_opportunity_results(request)
            if pipeline == "data":
                # Data pipeline run is complete; analytics pipeline is responsible for matrix rendering.
                if self.console:
                    self.console.print("[green]Data pipeline complete (Iceberg updated).[/green]")
                return len(_results)

        # 2) Analytics pipeline (Iceberg + render)
        pairs = self.get_pairs(
            request.assets.asset_type,
            request.assets.universe,
            request.assets.pairs,
            instrument_type=getattr(request.assets, "instrument_type", None),
        )
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        # Build a screener instance only for enrichment + rendering (no fetch).
        config = self._build_opportunity_config(request)
        screener = AssetScreenerFactory.create_screener(
            asset_type=request.assets.asset_type,
            symbols=pairs,
            timeframes=timeframes,
            config=config,
        )

        results = self._load_latest_signals_latest(
            asset_type=request.assets.asset_type,
            pairs=pairs,
            timeframes=timeframes,
        )
        snapshot_label = self._snapshot_label_from_df(results)
        results = self._apply_edge_filters(results, request)

        if request.output.confluence_grade or request.output.min_opportunity_confluence:
            results = self._filter_by_confluence(
                results,
                grade=request.output.confluence_grade,
                min_confluence=request.output.min_opportunity_confluence,
            )

        metadata = self._build_opportunity_metadata(request)
        if request.output.output:
            self._export_dataframe(results, request.output.output, metadata, label="opportunities")

        if self.console:
            if results.empty:
                self.console.print("[yellow]No results found matching criteria.[/yellow]")
            else:
                screener.print_summary(
                    results_df=results,
                    detailed=request.output.detailed,
                    matrix=request.output.matrix,
                    limit=request.output.limit,
                    show_risk=request.output.show_risk,
                    snapshot_label=snapshot_label,
                    console=self.console,
                )

        if request.output.save_config:
            self._maybe_save_opportunity_config(request.output.save_config, request)

        return len(results)

    def get_opportunity_results(
        self, request: ScanRequest
    ) -> tuple[pd.DataFrame, BaseOpportunityScreener]:
        """Run opportunity screener and return results + screener instance."""
        request = self.resolve_defaults(request)
        pairs = self.get_pairs(
            request.assets.asset_type,
            request.assets.universe,
            request.assets.pairs,
            instrument_type=getattr(request.assets, "instrument_type", None),
        )
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        if self.console:
            self.console.print(
                f"[cyan]Scanning {len(pairs)} {request.assets.asset_type} symbols...[/cyan]"
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
        request = self.resolve_defaults(request)
        pipeline = (request.assets.pipeline or "both").strip().lower()
        if pipeline not in ("data", "analytics", "both"):
            pipeline = "both"

        # Strategy depends on opportunity-style Gold rows; in split mode:
        # - data: refresh Iceberg (opportunity medallion) only
        # - analytics: compute strategy signals from Iceberg-backed data only
        # - both: refresh then compute from Iceberg
        if pipeline in ("data", "both"):
            results, _screener = self.get_opportunity_results(request)
            if pipeline == "data":
                if self.console:
                    self.console.print("[green]Data pipeline complete (Iceberg updated).[/green]")
                # Return the count of refreshed Gold rows for correct CLI exit semantics.
                return len(results)

        pairs = self.get_pairs(
            request.assets.asset_type, request.assets.universe, request.assets.pairs
        )
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        raw_data = self._load_latest_signals_latest(
            asset_type=request.assets.asset_type,
            pairs=pairs,
            timeframes=timeframes,
        )
        snapshot_label = self._snapshot_label_from_df(raw_data)

        config = self._build_strategy_config(request)
        scanner = ForexStrategyScanner(pairs=pairs, timeframes=timeframes, config=config)
        results = self._fetch_data_with_progress(lambda: scanner.scan_from_data(raw_data))
        results = self._apply_edge_filters(results, request)

        metadata = self._build_strategy_metadata(request)
        if request.output.output:
            self._export_dataframe(results, request.output.output, metadata, label="signals")

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
                    snapshot_label=snapshot_label,
                    console=self.console,
                )

        return len(results)

    def get_strategy_results(
        self, request: ScanRequest
    ) -> tuple[pd.DataFrame, ForexStrategyScanner]:
        """Run strategy scanner and return results + scanner instance."""
        request = self.resolve_defaults(request)
        pairs = self.get_pairs(
            request.assets.asset_type, request.assets.universe, request.assets.pairs
        )
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        if self.console:
            self.console.print(
                f"[cyan]Scanning {len(pairs)} {request.assets.asset_type} symbols for {request.assets.strategy} signals...[/cyan]"
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

    def _fetch_data_with_progress(self, fetch_func: Any) -> Any:
        """Helper to run a fetch function with rich progress bar if console is available."""
        if self.console and not getattr(self.console, "record", False):
            from rich.progress import Progress, SpinnerColumn, TextColumn

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                progress.add_task("Fetching data...", total=None)
                return fetch_func()

        # Avoid noisy spinner frames in recorded consoles (e.g. Prefect runner logs/artifacts).
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

    def _export_dataframe(
        self, df: Any, output: str, metadata: dict[str, Any], *, label: str
    ) -> None:
        """Export a provided dataframe without triggering a fetch."""
        import logging

        try:
            output_path = self._validate_path(output)
            self._ensure_parent_exists(output_path)
        except ValueError as e:
            if self.console:
                self.console.print(f"[red]Error: {e}[/red]")
            return

        output_lower = str(output_path).lower()
        from tvscreener.lib.screeners.export_helpers import get_export_function

        logger = logging.getLogger(__name__)

        def df_getter() -> Any:
            return df

        try:
            if output_lower.endswith(".csv"):
                get_export_function("csv")(
                    df_getter,
                    str(output_path),
                    include_index=False,
                    logger=logger,
                    label=label,
                    metadata=metadata,
                )
            elif output_lower.endswith(".json"):
                get_export_function("json")(
                    df_getter,
                    str(output_path),
                    orient="records",
                    logger=logger,
                    label=label,
                    metadata=metadata,
                )
            elif output_lower.endswith(".parquet"):
                get_export_function("parquet")(
                    df_getter,
                    str(output_path),
                    include_index=False,
                    logger=logger,
                    label=label,
                    metadata=metadata,
                )
            elif output_lower.endswith(".xml"):
                get_export_function("xml")(
                    df_getter,
                    str(output_path),
                    include_index=False,
                    logger=logger,
                    label=label,
                    metadata=metadata,
                )
            else:
                if self.console:
                    self.console.print(f"[yellow]Unknown output format: {output}[/yellow]")
                return
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Export failed: {e}[/red]")
            logger.error("Export failed: %s", e)
            return

        if self.console:
            self.console.print(f"[green]Saved to {output_path}[/green]")

    def _apply_edge_filters(self, df: pd.DataFrame, request: ScanRequest) -> pd.DataFrame:
        """Apply optional Edge SQL / filter expressions to a dataframe."""
        if df.empty:
            return df
        if not (request.output.sql or request.output.filters):
            return df

        from tvscreener.lib.query import EdgeQueryClient

        try:
            with EdgeQueryClient() as edge_client:
                if request.output.sql:
                    df = edge_client.query_sql(
                        df, request.output.sql, params=request.output.sql_params
                    )
                if request.output.filters:
                    for f in request.output.filters:
                        df = edge_client.query_sql(df, f"SELECT * FROM df WHERE {f}")
        except Exception as e:
            logger.error("Failed to apply edge filters: %s", e)
        return df

    def _load_latest_signals_latest(
        self, *, asset_type: str, pairs: list[str], timeframes: list[str]
    ) -> pd.DataFrame:
        """Load latest-per-entity Gold rows from Iceberg for analytics rendering."""
        from tvscreener.lib.query import EdgeQueryClient
        from tvscreener.util import canonicalize_asset_type, timeframe_set_id

        at = canonicalize_asset_type(asset_type)
        tfsid = timeframe_set_id(timeframes)

        from tvscreener.lib.lakehouse.table_ids import (
            default_instrument_type,
            normalize_instrument_type,
            product_table_id,
        )

        it_env = (os.getenv("TVSCREENER_INSTRUMENT_TYPE") or "").strip() or None
        it = normalize_instrument_type(asset_type=at, raw=it_env or default_instrument_type(at))
        signals_latest_table = product_table_id(
            dataset="signals_latest", asset_type=at, instrument_type=it
        )

        def _in_list(vals: list[str]) -> str:
            safe = [v.replace("'", "''") for v in vals]
            inner = ", ".join(f"'{v}'" for v in safe)
            return f"({inner})" if inner else "('')"

        pairs_in = _in_list(pairs)

        base_where = "asset_type = $asset_type AND timeframe_set_id = $tfsid"
        params = {"asset_type": at, "tfsid": tfsid}

        order_by = "ORDER BY ENSEMBLE_SCORE DESC, GRID_ALIGNED DESC, fetched_at_utc DESC"
        sql_entity = f"SELECT * FROM df WHERE {base_where} AND entity_id IN {pairs_in} {order_by}"
        sql_pair = f"SELECT * FROM df WHERE {base_where} AND PAIR IN {pairs_in} {order_by}"
        sql_symbol = f"SELECT * FROM df WHERE {base_where} AND symbol IN {pairs_in} {order_by}"

        with EdgeQueryClient() as edge_client:
            try:
                # Fully-qualified symbols (BINANCE:BTCUSDT) should filter by entity_id.
                if any(":" in p for p in pairs):
                    return edge_client.query_sql(signals_latest_table, sql_entity, params=params)
                return edge_client.query_sql(signals_latest_table, sql_pair, params=params)
            except Exception:
                # Fallback order: PAIR then symbol then entity_id.
                try:
                    return edge_client.query_sql(signals_latest_table, sql_pair, params=params)
                except Exception:
                    try:
                        return edge_client.query_sql(
                            signals_latest_table, sql_symbol, params=params
                        )
                    except Exception:
                        return edge_client.query_sql(
                            signals_latest_table, sql_entity, params=params
                        )

    def _snapshot_label_from_df(self, df: Any) -> str | None:
        """Best-effort snapshot label for matrix view headers.

        For Iceberg-backed analytics runs, we derive a human-readable snapshot time from
        the `fetched_at_utc` column (if present) on the loaded dataframe.
        """
        try:
            if df is None or getattr(df, "empty", True):
                return None
            if not hasattr(df, "columns") or "fetched_at_utc" not in df.columns:
                return None
            import pandas as pd

            ts = pd.to_datetime(df["fetched_at_utc"], errors="coerce")
            ts = ts.dropna()
            if ts.empty:
                return None
            t_min = ts.min()
            t_max = ts.max()
            # Display as UTC (Iceberg timestamps are treated as UTC in this repo).
            fmt = "%Y-%m-%d %H:%M:%S"
            if t_min == t_max:
                return f"{t_max.strftime(fmt)} UTC"
            return f"{t_min.strftime(fmt)}..{t_max.strftime(fmt)} UTC"
        except Exception:
            return None

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
            grade_values = df["GRADE"].map(lambda g: grade_order.get(g, 0)).fillna(0)
            df = df.loc[grade_values >= min_grade_value]

        if min_confluence is not None:
            df = df.loc[df["TOTAL_CONFLUENCE"] >= min_confluence]

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
