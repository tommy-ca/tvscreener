from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from tvscreener_ext.models import ScanRequest
from tvscreener_ext.screeners.factory import AssetScreenerFactory
from tvscreener_ext.screeners.forex_strategy import ForexStrategyScanner
from tvscreener_ext.services.config import ConfigFactory
from tvscreener_ext.services.export import ExportService
from tvscreener_ext.services.universe import UniverseResolver
from tvscreener_ext.utils.logic import canonicalize_asset_type, timeframe_set_id, validate_path

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)


class ScanWorkflow:
    """Coordinator service for the scan execution lifecycle."""

    def __init__(
        self,
        resolver: UniverseResolver,
        factory: ConfigFactory,
        exporter: ExportService,
        console: Console | None = None,
    ):
        self.resolver = resolver
        self.factory = factory
        self.exporter = exporter
        self.console = console

    def run_opportunity_scan(self, request: ScanRequest) -> int:
        """Run opportunity screener and handle output."""
        pipeline = (request.assets.pipeline or "both").strip().lower()
        if pipeline not in ("data", "analytics", "both"):
            pipeline = "both"

        if pipeline in ("data", "both"):
            results, _ = self.get_opportunity_results(request)
            if pipeline == "data":
                if self.console:
                    self.console.print("[green]Data pipeline complete (Iceberg updated).[/green]")
                return len(results)

        pairs = self.resolver.resolve_tickers(
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
        config = self.factory.build_opportunity_config(request)
        screener = AssetScreenerFactory.create_screener(
            asset_type=request.assets.asset_type,
            symbols=pairs,
            timeframes=timeframes,
            config=config,
        )
        results = self._load_latest_signals(
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
            self.exporter.export_dataframe(
                results,
                request.output.output,
                self.factory.build_opportunity_metadata(request),
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

    def _maybe_save_opportunity_config(self, path: str, request: ScanRequest) -> None:
        """Save opportunity config to YAML."""
        data = {
            "timeframes": request.assets.timeframes,
            "min_volume": request.assets.min_volume,
            "max_atr": request.assets.max_atr,
            "min_ma_score": request.assets.min_ma_score,
        }
        try:
            self.exporter.save_config(path, data)
        except Exception as e:
            logger.warning("Failed to save opportunity config to %s: %s", path, e)

    def get_opportunity_results(self, request: ScanRequest) -> tuple[pd.DataFrame, Any]:
        """Run opportunity screener and return results + screener instance."""
        pairs = self.resolver.resolve_tickers(
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

        config = self.factory.build_opportunity_config(request)
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
        pipeline = (request.assets.pipeline or "both").strip().lower()
        if pipeline not in ("data", "analytics", "both"):
            pipeline = "both"

        if pipeline in ("data", "both"):
            results, _ = self.get_opportunity_results(request)
            if pipeline == "data":
                if self.console:
                    self.console.print("[green]Data pipeline complete (Iceberg updated).[/green]")
                return len(results)

        pairs = self.resolver.resolve_tickers(
            request.assets.asset_type, request.assets.universe, request.assets.pairs
        )
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )
        raw_data = self._load_latest_signals(
            asset_type=request.assets.asset_type, pairs=pairs, timeframes=timeframes
        )
        snapshot_label = self._snapshot_label_from_df(raw_data)
        config = self.factory.build_strategy_config(request)
        scanner = ForexStrategyScanner(pairs=pairs, timeframes=timeframes, config=config)
        results = self._fetch_data_with_progress(lambda: scanner.scan_from_data(raw_data))
        results = self._apply_edge_filters(results, request)

        if request.output.output:
            self.exporter.export_dataframe(
                results,
                request.output.output,
                self.factory.build_strategy_metadata(request),
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

    def run_inspect(self, request: ScanRequest) -> int:
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
                            table.add_column(str(col))
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
                        table.add_column(str(col))
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

    def _load_latest_signals(
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

        # Use entity_id for crypto to ensure canonical resolution
        col = "entity_id" if at == "crypto" else "PAIR"
        sql_pair = f"SELECT * FROM df WHERE {base_where} AND {col} IN {pairs_in} {order_by}"

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
