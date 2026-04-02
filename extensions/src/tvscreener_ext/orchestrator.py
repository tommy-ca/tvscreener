#!/usr/bin/env python3
"""Orchestrator for screener execution and configuration."""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

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
from tvscreener_ext.screeners.base import BaseOpportunityScreener
from tvscreener_ext.screeners.factory import AssetScreenerFactory
from tvscreener_ext.screeners.forex_opportunity import ForexScreenerConfig
from tvscreener_ext.screeners.forex_strategy import (
    ForexStrategyScanner,
    StrategyConfig,
)
from tvscreener_ext.screeners.registry import ScreenerFamilyRegistry
from tvscreener_ext.services.config import ConfigFactory
from tvscreener_ext.services.export import ExportService
from tvscreener_ext.services.universe import UniverseResolver
from tvscreener_ext.services.workflow import ScanWorkflow
from tvscreener_ext.utils.logic import (
    canonicalize_asset_type,
    timeframe_set_id,
    validate_path,
)

if TYPE_CHECKING:
    import pandas as pd
    from rich.console import Console

logger = logging.getLogger(__name__)


class ScreenerController:
    """Handles the execution lifecycle of scanners."""

    def __init__(self, console: Console | None = None):
        self.console = console
        self._universe_resolver = UniverseResolver()
        self._export_service = ExportService()
        self._config_factory = ConfigFactory()
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
        target = getattr(args, "target", None)
        out_dir = getattr(args, "out_dir", None)
        if not target:
            return 2

        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown audit target: {target}[/red]")
            return 2

        import json

        out_base = Path(out_dir or "artifacts/audits/binance-universes")
        out_base.mkdir(parents=True, exist_ok=True)

        include_all = bool(getattr(args, "include_all", False))
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
            universes += [
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
                with contextlib.suppress(Exception):
                    uni = json.loads(uni_path.read_text(encoding="utf-8"))

            errors: list[str] = []
            if len(pairs) != len(set(pairs)):
                errors.append("duplicates")
            if u.startswith("binance_perp") and any(not p.endswith(".P") for p in pairs):
                errors.append("perp_missing_dotP")
            if u.startswith("binance_spot") and any(p.endswith(".P") for p in pairs):
                errors.append("spot_has_dotP")
            if any(not p.startswith("BINANCE:") for p in pairs):
                errors.append("non_binance_ticker")

            report[u] = {
                "count": len(pairs),
                "sample": pairs[:10],
                "quote_asset_dist": dict(
                    sorted(quote_dist.items(), key=lambda kv: (-kv[1], kv[0]))
                ),
                "universe_json": str(uni_path) if uni_path.exists() else None,
                "selection": uni.get("constraints", {}).get("selection")
                if isinstance(uni, dict)
                else None,
                "missing_tickers": len(uni.get("missing_tickers", []))
                if isinstance(uni, dict)
                else None,
                "included_bases": len(uni.get("included_bases", []))
                if isinstance(uni, dict)
                else None,
                "errors": errors,
            }

        overlap: dict[str, dict[str, int]] = {
            a: {b: len(sets[a] & sets[b]) for b in universes} for a in universes
        }
        payload = {"universes": report, "overlap": overlap}
        report_path = out_base / "report.json"
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        if self.console:
            self.console.print(f"[green]Wrote {report_path}[/green]")

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
        from tvscreener_ext.reports.binance_universes import generate_binance_universes_report

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

        if strict:
            report_path = Path(audit_out_dir) / "report.json"
            try:
                import json

                payload = json.loads(report_path.read_text(encoding="utf-8"))
                universes = (payload or {}).get("universes", {})
                if any((v or {}).get("errors") for v in universes.values()):
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

        if pipeline in ("data", "both"):
            results, _ = self.get_opportunity_results(request)
            if pipeline == "data":
                if self.console:
                    self.console.print("[green]Data pipeline complete (Iceberg updated).[/green]")
                return len(results)

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
        config = self._build_opportunity_config(request)
        screener = AssetScreenerFactory.create_screener(
            asset_type=request.assets.asset_type,
            symbols=pairs,
            timeframes=timeframes,
            config=config,
        )
        results = self._load_latest_signals_latest(
            asset_type=request.assets.asset_type, pairs=pairs, timeframes=timeframes
        )
        snapshot_label = self._snapshot_label_from_df(results)
        results = self._apply_edge_filters(results, request)

        if request.output.confluence_grade or request.output.min_opportunity_confluence:
            results = self._filter_by_confluence(
                results,
                grade=request.output.confluence_grade,
                min_confluence=request.output.min_opportunity_confluence,
            )

        if request.output.output:
            self._export_service.export_dataframe(
                results,
                request.output.output,
                self._build_opportunity_metadata(request),
                label="opportunities",
            )

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
        results = self._apply_edge_filters(results, request)
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

        if pipeline in ("data", "both"):
            results, _ = self.get_opportunity_results(request)
            if pipeline == "data":
                if self.console:
                    self.console.print("[green]Data pipeline complete (Iceberg updated).[/green]")
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
            asset_type=request.assets.asset_type, pairs=pairs, timeframes=timeframes
        )
        snapshot_label = self._snapshot_label_from_df(raw_data)
        config = self._build_strategy_config(request)
        scanner = ForexStrategyScanner(pairs=pairs, timeframes=timeframes, config=config)
        results = self._fetch_data_with_progress(lambda: scanner.scan_from_data(raw_data))
        results = self._apply_edge_filters(results, request)

        if request.output.output:
            self._export_service.export_dataframe(
                results,
                request.output.output,
                self._build_strategy_metadata(request),
                label="signals",
            )

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

    def run_inspect_parquet(self, request: ScanRequest) -> int:
        """Inspect a parquet file or Iceberg table."""
        from tvscreener_ext.inspect_utils import inspect_parquet
        from tvscreener_ext.query import EdgeQueryClient

        if not request.output.output:
            if self.console:
                self.console.print(
                    "[red]Error: Please specify a file or table to inspect using --output or -o[/red]"
                )
            return -1

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
                return 0

        if not is_iceberg:
            validated_path = validate_path(request.output.output)
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
                with contextlib.suppress(Exception), EdgeQueryClient() as edge_client:
                    results = edge_client.query_sql(
                        request.output.output, f"SELECT * FROM df LIMIT {request.output.head or 10}"
                    )
                    from rich.table import Table

                    table = Table(title=f"Preview of {request.output.output}")
                    for col in results.columns:
                        table.add_column(col)
                    for _, row in results.iterrows():
                        table.add_row(*[str(val) for val in row])
                    self.console.print(table)
        return 0

    def _fetch_data_with_progress(self, fetch_func: Any) -> Any:
        """Helper to run a fetch function with rich progress bar."""
        if self.console and not getattr(self.console, "record", False):
            from rich.progress import Progress, SpinnerColumn, TextColumn

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                progress.add_task("Fetching data...", total=None)
                return fetch_func()
        return fetch_func()

    def _apply_edge_filters(self, df: pd.DataFrame, request: ScanRequest) -> pd.DataFrame:
        """Apply optional Edge SQL / filter expressions to a dataframe."""
        if df.empty or not (request.output.sql or request.output.filters):
            return df
        from tvscreener_ext.query import EdgeQueryClient

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
        """Load latest-per-entity Gold rows from Iceberg."""
        from tvscreener_ext.query import EdgeQueryClient

        at = canonicalize_asset_type(asset_type)
        tfsid = timeframe_set_id(timeframes)
        from tvscreener_ext.lakehouse.table_ids import (
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
        sql_pair = f"SELECT * FROM df WHERE {base_where} AND PAIR IN {pairs_in} {order_by}"

        with EdgeQueryClient() as edge_client:
            try:
                return edge_client.query_sql(signals_latest_table, sql_pair, params=params)
            except Exception:
                return pd.DataFrame()

    def _snapshot_label_from_df(self, df: Any) -> str | None:
        """Best-effort snapshot label for matrix view headers."""
        try:
            if df is None or getattr(df, "empty", True) or "fetched_at_utc" not in df.columns:
                return None
            import pandas as pd

            ts = pd.to_datetime(df["fetched_at_utc"], errors="coerce").dropna()
            if ts.empty:
                return None
            fmt = "%Y-%m-%d %H:%M:%S"
            t_min, t_max = ts.min(), ts.max()
            return (
                f"{t_max.strftime(fmt)} UTC"
                if t_min == t_max
                else f"{t_min.strftime(fmt)}..{t_max.strftime(fmt)} UTC"
            )
        except Exception:
            return None

    def _build_opportunity_config(self, request: ScanRequest) -> ForexScreenerConfig:
        return self._config_factory.build_opportunity_config(request)

    def _build_strategy_config(self, request: ScanRequest) -> StrategyConfig:
        return self._config_factory.build_strategy_config(request)

    def _build_opportunity_metadata(self, request: ScanRequest) -> dict[str, Any]:
        return self._config_factory.build_opportunity_metadata(request)

    def _build_strategy_metadata(self, request: ScanRequest) -> dict[str, Any]:
        return self._config_factory.build_strategy_metadata(request)

    def _parse_timeframe_weights(self, spec: str | None) -> dict[str, float]:
        return self._config_factory._parse_timeframe_weights(spec)

    def _filter_by_confluence(
        self, df: pd.DataFrame, grade: str | None = None, min_confluence: int | None = None
    ) -> pd.DataFrame:
        if df.empty:
            return df
        if grade:
            order = {"A+": 6, "A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
            df = df.loc[df["GRADE"].map(lambda g: order.get(g, 0)).fillna(0) >= order.get(grade, 0)]
        if min_confluence is not None:
            df = df.loc[df["TOTAL_CONFLUENCE"] >= min_confluence]
        return df

    def _maybe_save_opportunity_config(self, path: str, request: ScanRequest) -> None:
        try:
            p = validate_path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w") as fh:
                yaml.safe_dump({"timeframes": request.assets.timeframes}, fh)
        except Exception:
            pass
