from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tvscreener.beauty import VisualStyler
from tvscreener.lib.screeners.renderers.base import BaseRenderer
from tvscreener.util import to_scalar

if TYPE_CHECKING:
    import pandas as pd
    from rich.console import Console
    from rich.table import Table

logger = logging.getLogger(__name__)


def get_enriched_col(row: Any, canonical: str, raw: str, default: Any = "N/A") -> Any:
    """Helper to handle dual-lookup of canonical and raw API column names."""
    # Handle both dict-like and object-like rows
    if hasattr(row, "get"):
        return row.get(canonical, row.get(raw, default))
    # For namedtuples or objects
    return getattr(row, canonical, getattr(row, raw, default))


class RichConsoleRenderer(BaseRenderer):
    """Rich-based terminal renderer for screeners."""

    _registry: dict[str, dict[str, Any]] = {}

    @classmethod
    def register(cls, class_name: str, **kwargs: Any) -> None:
        """Register a rendering configuration for a screener class."""
        cls._registry[class_name] = kwargs

    def render(self, screener: Any, results_df: pd.DataFrame | None = None, **kwargs: Any) -> None:
        """Render the screener results using Rich."""
        from tvscreener.lib.screeners.export_helpers import print_summary

        class_name = screener.__class__.__name__
        config = self._registry.get(class_name)

        # Use external results if provided (e.g. from Edge SQL), else internal enriched data
        def get_data():
            if results_df is not None:
                # Still run through enrichment to ensure STRENGTH_SIGN etc. are present
                return screener._prepare_enriched_data(results_df)

            # Get the data from the screener instance
            # Use getattr for robustness since internal attribute names differ
            raw_data = getattr(screener, "_cached_data", None)
            if raw_data is None:
                raw_data = getattr(screener, "_cached_results", None)

            if raw_data is None:
                # Fallback to internal _get_data if not cached
                raw_data = screener._get_data()

            return screener._prepare_enriched_data(raw_data)

        if config:
            # Check for alternative renderer class
            renderer_class = config.get("renderer_class")
            if renderer_class:
                renderer = renderer_class()
                renderer.render(screener, **kwargs)
                return

            # Check for registered render method on this class
            render_method_name = config.get("render_method")
            if render_method_name:
                render_method = getattr(self, render_method_name)

                def safe_render(df, console, table):
                    try:
                        render_method(screener, df, console, table, **kwargs)
                    except (KeyError, AttributeError, ValueError) as e:
                        logger.warning(
                            "Render failed with %s (%s), falling back to generic.",
                            type(e).__name__,
                            e,
                        )
                        self._render_generic(screener, df, console, table, **kwargs)

                print_summary(
                    get_data,
                    empty_rich_message=config.get("empty_rich_message", "No results found"),
                    render_rich=safe_render,
                )
                return

        # Fallback for unregistered screeners
        print_summary(
            get_data,
            empty_rich_message="No results found",
            render_rich=lambda df, console, table: self._render_generic(
                screener, df, console, table, **kwargs
            ),
        )

    def _render_generic(
        self, screener: Any, df: pd.DataFrame, console: Console, Table: type[Table], **kwargs: Any
    ) -> None:
        title = f"{getattr(screener, 'asset_type', 'Asset').title()} Opportunities"
        table = Table(title=title)
        max_cols = 10
        cols = list(df.columns[:max_cols])

        for col in cols:
            table.add_column(str(col))

        limit = kwargs.get("limit", 20)
        for _, row in df.head(limit).iterrows():
            table.add_row(*[str(row.get(col, "")) for col in cols])

        console.print(table)
        shown = len(df.head(limit))
        console.print(f"\n[dim]Showing {shown} of {len(df)} results[/dim]")

    def _collect_confluence_stats(self, row: Any) -> dict[str, int]:
        grid_total = int(to_scalar(row.get("GRID_TOTAL", 12) or 12))
        grid_aligned = int(to_scalar(row.get("GRID_ALIGNED", row.get("TOTAL_CONFLUENCE", 0)) or 0))
        total_confluence = int(to_scalar(row.get("TOTAL_CONFLUENCE", grid_aligned) or grid_aligned))
        tf_long = int(to_scalar(row.get("TF_CONFLUENCE_LONG", 0) or 0))
        tf_short = int(to_scalar(row.get("TF_CONFLUENCE_SHORT", 0) or 0))

        return {
            "grid_aligned": grid_aligned,
            "grid_total": grid_total,
            "total_confluence": total_confluence,
            "tf_long": tf_long,
            "tf_short": tf_short,
        }

    def _format_confluence_summary(self, stats: dict[str, int]) -> str:
        return (
            f"TOTAL_CONFLUENCE={stats['total_confluence']} "
            f"GRID_TOTAL={stats['grid_total']} "
            f"TF_LONG={stats['tf_long']} "
            f"TF_SHORT={stats['tf_short']}"
        )

    def _render_opportunity(
        self, screener: Any, df: pd.DataFrame, console: Console, Table: type[Table], **kwargs: Any
    ) -> None:
        detailed = kwargs.get("detailed", False)
        matrix = kwargs.get("matrix", False)
        limit = kwargs.get("limit")

        if detailed:
            self._render_opportunity_detailed(screener, df, console, limit=limit)
            return
        if matrix:
            self._render_opportunity_matrix(screener, df, console, Table, limit=limit)
            return

        from tvscreener.constants.forex import DEFAULT_LIMIT_SUMMARY

        display_limit = limit if limit is not None else DEFAULT_LIMIT_SUMMARY
        table = Table(title="Forex Opportunities")
        table.add_column("Rank", style="dim", justify="right", no_wrap=True)
        table.add_column("Pair", style="cyan", no_wrap=True)
        table.add_column("Dir", justify="center")
        table.add_column("Ens", style="green", justify="right")
        table.add_column("Grid", style="yellow", justify="center")
        table.add_column("TF", style="dim yellow", justify="center")
        table.add_column("Fac", style="dim yellow", justify="center")
        table.add_column("Gr", style="magenta", justify="center")
        table.add_column("Confluence", justify="left", style="dim")

        if getattr(screener.config, "show_risk", False):
            table.add_column("SL", justify="right", style="red")
            table.add_column("TP", justify="right", style="green")
            table.add_column("RR", justify="right", style="yellow")
            table.add_column("Sz", justify="right", style="cyan")

        for idx, (_, row) in enumerate(df.head(display_limit).iterrows(), 1):
            name = get_enriched_col(row, "PAIR", "Name")
            ensemble = row.get("ENSEMBLE_SCORE", 0) or 0
            grid_aligned = row.get("GRID_ALIGNED", 0) or 0
            grid_total = row.get("GRID_TOTAL", 12) or 12
            tf_conf = row.get("TF_CONFLUENCE", "0/3")
            factor_conf = row.get("FACTOR_CONFLUENCE", "0/4")
            grade = row.get("GRADE", "F")
            stats = self._collect_confluence_stats(row)
            confluence_summary = self._format_confluence_summary(stats)

            # Direction column should never show ⚪ (Todo 064)
            direction_sign = row.get("DIRECTION_SIGN") or VisualStyler.direction_emoji(ensemble)

            row_data = [
                str(idx),
                str(name),
                direction_sign,
                f"{ensemble:+.2f}",
                f"{grid_aligned}/{grid_total}",
                str(tf_conf),
                str(factor_conf),
                f"[bold]{grade}[/bold]",
                confluence_summary,
            ]

            if getattr(screener.config, "show_risk", False):
                sl = row.get("STOP_LOSS", 0) or 0
                tp = row.get("TAKE_PROFIT", 0) or 0
                rr = row.get("RR_RATIO", 0) or 0
                size = row.get("POSITION_SIZE", 0) or 0
                row_data.extend(
                    [
                        f"{sl:.5f}" if sl else "N/A",
                        f"{tp:.5f}" if tp else "N/A",
                        f"{rr:.2f}" if rr else "N/A",
                        f"{size:.2f}" if size else "N/A",
                    ]
                )

            table.add_row(*row_data)

        console.print(table)
        shown = len(df.head(display_limit))
        console.print(f"\n[dim]Showing {shown} of {len(df)} opportunities[/dim]")

    def _render_opportunity_detailed(
        self, screener: Any, df: pd.DataFrame, console: Console, limit: int | None = None
    ) -> None:
        from rich.table import Table as RichTable

        from tvscreener.constants.forex import DEFAULT_LIMIT_DETAILED

        display_limit = limit if limit is not None else DEFAULT_LIMIT_DETAILED
        for idx, (_, row) in enumerate(df.head(display_limit).iterrows(), 1):
            name = get_enriched_col(row, "PAIR", "Name")
            ensemble = row.get("ENSEMBLE_SCORE", 0) or 0
            grade = row.get("GRADE", "F")
            stats = self._collect_confluence_stats(row)
            grid_aligned = stats["grid_aligned"]
            grid_total = stats["grid_total"]
            total_confluence = stats["total_confluence"]
            grid_pct = row.get("GRID_PCT", 0) or 0
            factor_conf = row.get("FACTOR_CONFLUENCE", "0/4")
            confluence_summary = self._format_confluence_summary(stats)

            # Direction should never show ⚪ (Todo 064)
            direction_sign = row.get("DIRECTION_SIGN") or VisualStyler.direction_emoji(ensemble)

            table = RichTable(title=f"#{idx} {name} - {direction_sign} (Grade: {grade})")
            table.add_column("Timeframe", style="cyan")
            table.add_column("TREND", justify="center")
            table.add_column("MA", justify="center")
            table.add_column("OSC", justify="center")
            table.add_column("ROC", justify="center")

            for tf in screener.timeframes:
                trend_val = get_enriched_col(row, f"TREND_{tf}", f"Recommend All|{tf}", 0)
                ma_val = get_enriched_col(row, f"MA_{tf}", f"Recommend Ma|{tf}", 0)
                osc_val = get_enriched_col(row, f"OSC_{tf}", f"Recommend Other|{tf}", 0)
                roc_val = get_enriched_col(row, f"ROC_{tf}", f"Roc|{tf}", 0)

                trend_val = to_scalar(trend_val)
                ma_val = to_scalar(ma_val)
                osc_val = to_scalar(osc_val)
                roc_val = to_scalar(roc_val)

                trend_sign = VisualStyler.opportunity_strength_sign(trend_val)
                ma_sign = VisualStyler.opportunity_strength_sign(ma_val)
                osc_sign = VisualStyler.opportunity_strength_sign(osc_val)
                roc_sign = VisualStyler.opportunity_strength_sign(roc_val, is_roc=True)

                table.add_row(
                    str(tf),
                    f"{trend_val:+.2f} {trend_sign}",
                    f"{ma_val:+.2f} {ma_sign}",
                    f"{osc_val:+.2f} {osc_sign}",
                    # Zero ROC values show +0.00 ⚪ instead of dash (Todo 066)
                    f"{roc_val:+.2f} {roc_sign}",
                )

            console.print(table)
            footer = (
                f"  Ensemble: {ensemble:+.3f} | "
                f"Total: {total_confluence} | "
                f"Grid: {grid_aligned}/{grid_total} ({grid_pct}%) | "
                f"TF+: {stats['tf_long']} TF-: {stats['tf_short']} | "
                f"Factor: {factor_conf}"
            )

            if getattr(screener.config, "show_risk", False):
                sl = row.get("STOP_LOSS", 0) or 0
                tp = row.get("TAKE_PROFIT", 0) or 0
                rr = row.get("RR_RATIO", 0) or 0
                size = row.get("POSITION_SIZE", 0) or 0

                htf = sorted(screener.timeframes, key=lambda x: int(x), reverse=True)[0]
                atr = get_enriched_col(row, f"ATR_{htf}", f"ATR|{htf}", 0)
                rvol = get_enriched_col(row, "RVOL", "relative_volume_10d_calc", 0)

                from rich.text import Text

                console.print(footer)
                console.print(
                    Text.assemble(
                        "  ",
                        VisualStyler.format_sl(sl),
                        " | ",
                        VisualStyler.format_tp(tp),
                        " | ",
                        VisualStyler.format_rr(rr),
                        " | ",
                        VisualStyler.format_size(size),
                    )
                )
                console.print(f"  [dim]Stats: ATR {atr:.5f} | RVOL {rvol:.2f}x[/dim]\n")
            else:
                console.print(footer)

            console.print(f"[dim]{confluence_summary}[/dim]\n")

        shown = len(df.head(display_limit))

        console.print(f"[dim]{VisualStyler.legend()}[/dim]")
        console.print(f"[dim]Showing {shown} of {len(df)} opportunities[/dim]")

    def _render_confluence_matrix(
        self,
        screener: Any,
        df: pd.DataFrame,
        console: Console,
        Table: type[Table],
        title: str,
    ) -> None:
        from tvscreener.core.enums import Direction

        table = Table(title=title)
        table.add_column("Pair", style="cyan", no_wrap=True)
        table.add_column("Dir", justify="center")
        table.add_column("TREND", justify="center")
        table.add_column("MA", justify="center")
        table.add_column("OSC", justify="center")
        table.add_column("ROC", justify="center")
        table.add_column("Grid", style="yellow", justify="center")
        table.add_column("Grade", style="magenta", justify="center")
        # Keep the matrix view compact and decision-oriented.
        # More numeric detail (ENSEMBLE_SCORE / TF_CONFLUENCE_*) is available in summary/detailed views.

        for _, row in df.iterrows():
            name = str(get_enriched_col(row, "PAIR", "Name"))
            direction = str(row.get("DIRECTION", Direction.LONG.value))
            grade = str(row.get("GRADE", "F"))
            stats = self._collect_confluence_stats(row)
            grid_aligned = stats["grid_aligned"]
            grid_total = stats["grid_total"]

            direction_emoji = (
                VisualStyler.BULL if direction == Direction.LONG.value else VisualStyler.BEAR
            )

            trend_dirs = []
            ma_dirs = []
            osc_dirs = []
            roc_dirs = []

            for tf in screener.timeframes:
                trend_val = get_enriched_col(row, f"TREND_{tf}", f"Recommend All|{tf}", 0)
                ma_val = get_enriched_col(row, f"MA_{tf}", f"Recommend Ma|{tf}", 0)
                osc_val = get_enriched_col(row, f"OSC_{tf}", f"Recommend Other|{tf}", 0)
                roc_val = get_enriched_col(row, f"ROC_{tf}", f"Roc|{tf}", 0)

                # Matrix cells show only single emojis (🟢/⚪/🔴) to prevent truncation (Todo 065)
                trend_dirs.append(VisualStyler.matrix_sign(to_scalar(trend_val)))
                ma_dirs.append(VisualStyler.matrix_sign(to_scalar(ma_val)))
                osc_dirs.append(VisualStyler.matrix_sign(to_scalar(osc_val)))
                roc_dirs.append(VisualStyler.matrix_sign(to_scalar(roc_val)))

            table.add_row(
                name,
                direction_emoji,
                "|".join(trend_dirs),
                "|".join(ma_dirs),
                "|".join(osc_dirs),
                "|".join(roc_dirs),
                f"{grid_aligned}/{grid_total}",
                f"[bold]{grade}[/bold]",
            )

        console.print(table)

    def _render_opportunity_matrix(
        self,
        screener: Any,
        df: pd.DataFrame,
        console: Console,
        Table: type[Table],
        limit: int | None = None,
    ) -> None:
        from tvscreener.constants.forex import DEFAULT_LIMIT_MATRIX

        display_limit = limit if limit is not None else DEFAULT_LIMIT_MATRIX
        display_df = df.head(display_limit)
        self._render_confluence_matrix(
            screener, display_df, console, Table, title="Confluence Matrix"
        )

        shown = len(display_df)
        console.print(f"\n[dim]{VisualStyler.legend()}[/dim]")
        console.print(f"[dim]Showing {shown} of {len(df)} opportunities[/dim]")

    def _render_strategy(
        self, screener: Any, df: pd.DataFrame, console: Console, Table: type[Table], **kwargs: Any
    ) -> None:
        matrix = kwargs.get("matrix", False)
        detailed = kwargs.get("detailed", False)
        limit = kwargs.get("limit")

        if matrix:
            self._render_strategy_matrix(screener, df, console, Table, limit=limit)
            return

        if detailed:
            from rich.console import Group
            from rich.panel import Panel

            from tvscreener.constants.forex import DEFAULT_LIMIT_DETAILED

            display_limit = limit if limit is not None else DEFAULT_LIMIT_DETAILED
            self._render_strategy_detailed(
                screener, df, console, Table, Panel, Group, limit=display_limit
            )
            return

        from tvscreener.constants.forex import DEFAULT_LIMIT_SUMMARY
        from tvscreener.core.enums import Direction

        display_limit = limit if limit is not None else DEFAULT_LIMIT_SUMMARY
        for strategy in df["STRATEGY"].unique():
            strategy_df = df[df["STRATEGY"] == strategy]
            total_strategy_count = len(strategy_df)

            if display_limit > 0:
                strategy_df = strategy_df.head(display_limit)

            table = Table(title=f"Strategy: {strategy}")
            table.add_column("Rank", justify="right", style="dim")
            table.add_column("Pair", style="cyan")
            table.add_column("Dir", justify="center")
            table.add_column("Ens", justify="right", style="green")

            if strategy == "confluence":
                table.add_column("Pattern", style="magenta")
                table.add_column("Sco", justify="right")
                table.add_column("MR", justify="right")
            else:
                table.add_column("Sco", justify="right")

            table.add_column("Grid", justify="center")
            table.add_column("Gr", justify="center", style="bold magenta")
            table.add_column("Confluence", justify="left", style="dim")

            if getattr(screener.config, "show_risk", False):
                table.add_column("SL", justify="right", style="red")
                table.add_column("TP", justify="right", style="green")
                table.add_column("RR", justify="right", style="yellow")
                table.add_column("Sz", justify="right", style="cyan")

            for i, row_tuple in enumerate(strategy_df.itertuples(index=False), 1):
                row = row_tuple._asdict()
                stats = self._collect_confluence_stats(row)
                confluence_summary = self._format_confluence_summary(stats)
                pair = str(get_enriched_col(row, "PAIR", "Name"))
                direction = str(row.get("DIRECTION", Direction.LONG.value))

                confluence_score = row.get("CONFLUENCE_SCORE", 0) or 0
                # Direction should never show ⚪ (Todo 064)
                direction_display = row.get("DIRECTION_SIGN")
                if not direction_display:
                    direction_display = VisualStyler.strategy_direction_sign(
                        confluence_score, direction=direction
                    )

                grid_aligned = stats["grid_aligned"]
                grid_total = stats["grid_total"]
                grid_display = f"{grid_aligned}/{grid_total}"
                grade = str(row.get("GRADE", "F"))

                row_data = [
                    str(i),
                    pair,
                    direction_display,
                    f"{(row.get('ENSEMBLE_SCORE', 0) or 0):+.2f}",
                ]

                if strategy == "confluence":
                    row_data.extend(
                        [
                            str(row.get("CONFLUENCE_PATTERN", "")),
                            str(row.get("CONFLUENCE_SCORE", "N/A")),
                            str(round((row.get("MR_EXTREMITY", 0) or 0), 2)),
                        ]
                    )
                else:
                    row_data.append(str(row.get("CONFLUENCE_SCORE", "N/A")))

                row_data.extend([grid_display, grade, confluence_summary])

                if getattr(screener.config, "show_risk", False):
                    sl = row.get("STOP_LOSS", 0) or 0
                    tp = row.get("TAKE_PROFIT", 0) or 0
                    rr = row.get("RR_RATIO", 0) or 0
                    size = row.get("POSITION_SIZE", 0) or 0
                    row_data.extend(
                        [
                            f"{sl:.5f}" if sl else "N/A",
                            f"{tp:.5f}" if tp else "N/A",
                            f"{rr:.2f}" if rr else "N/A",
                            f"{size:.2f}" if size else "N/A",
                        ]
                    )

                table.add_row(*row_data)

            console.print(table)
            shown = len(strategy_df.head(display_limit))
            console.print(f"[dim]Showing {shown} of {total_strategy_count} signals[/dim]")

        console.print(f"\n[dim]Showing {len(df)} of {len(df)} signals[/dim]")

    def _render_strategy_detailed(
        self,
        screener: Any,
        df: pd.DataFrame,
        console: Console,
        Table: type[Table],
        Panel: Any,
        Group: Any,
        limit: int | None = None,
    ) -> None:
        from rich.columns import Columns

        from tvscreener.constants.forex import DEFAULT_LIMIT_DETAILED

        display_limit = limit if limit is not None else DEFAULT_LIMIT_DETAILED

        for strategy in df["STRATEGY"].unique():
            strategy_df = df[df["STRATEGY"] == strategy]
            total_strategy_count = len(strategy_df)

            if display_limit > 0:
                strategy_df = strategy_df.head(display_limit)

            console.print(
                f"\n[bold underline]Strategy Group: {strategy.replace('_', ' ').title()}[/bold underline]"
            )

            panels = []
            for _, row in strategy_df.iterrows():
                stats = self._collect_confluence_stats(row)
                confluence_summary = self._format_confluence_summary(stats)
                ensemble = row.get("ENSEMBLE_SCORE", 0) or 0
                pair = get_enriched_col(row, "PAIR", "Name")
                score = row.get("CONFLUENCE_SCORE", "N/A")
                pattern = row.get("CONFLUENCE_PATTERN", "")

                grid = Table(box=None, show_header=True, padding=(0, 1), header_style="dim")
                grid.add_column("TF", style="dim")
                grid.add_column("TREND", justify="center")
                grid.add_column("MA", justify="center")
                grid.add_column("OSC", justify="center")
                grid.add_column("ROC", justify="center")

                for tf in screener.timeframes:
                    trend_val = get_enriched_col(row, f"TREND_{tf}", f"Recommend All|{tf}", 0)
                    ma_val = get_enriched_col(row, f"MA_{tf}", f"Recommend Ma|{tf}", 0)
                    osc_val = get_enriched_col(row, f"OSC_{tf}", f"Recommend Other|{tf}", 0)
                    roc_val = get_enriched_col(row, f"ROC_{tf}", f"Roc|{tf}", 0)

                    grid.add_row(
                        str(tf),
                        # Single emojis for density (Todo 065)
                        VisualStyler.matrix_sign(to_scalar(trend_val)),
                        VisualStyler.matrix_sign(to_scalar(ma_val)),
                        VisualStyler.matrix_sign(to_scalar(osc_val)),
                        VisualStyler.matrix_sign(to_scalar(roc_val)),
                    )

                strat_display = strategy.replace("_", " ").title()
                title = (
                    f"[bold cyan]{pair}[/bold cyan] "
                    f"[dim]({strat_display} - Score: {score} | Ensemble: {ensemble:+.2f})[/dim]"
                )
                if pattern:
                    title += f" [magenta]({pattern})[/magenta]"
                title += f" [dim]{confluence_summary}[/dim]"

                if getattr(screener.config, "show_risk", False):
                    sl = to_scalar(row.get("STOP_LOSS", 0))
                    tp = to_scalar(row.get("TAKE_PROFIT", 0))
                    rr = to_scalar(row.get("RR_RATIO", 0))
                    size = to_scalar(row.get("POSITION_SIZE", 0))

                    htf = sorted(screener.timeframes, key=lambda x: int(x), reverse=True)[0]
                    atr = to_scalar(get_enriched_col(row, f"ATR_{htf}", f"ATR|{htf}", 0))
                    rvol = to_scalar(get_enriched_col(row, "RVOL", "relative_volume_10d_calc", 0))

                    from rich.text import Text

                    risk_info = Text.assemble(
                        ("\nRisk: ", "dim"),
                        VisualStyler.format_sl(sl),
                        (" | ", "dim"),
                        VisualStyler.format_tp(tp),
                        (" | ", "dim"),
                        VisualStyler.format_rr(rr),
                        (" | ", "dim"),
                        VisualStyler.format_size(size),
                        (f"\nStats: ATR {atr:.5f} | RVOL {rvol:.2f}x", "dim"),
                    )
                    content = Group(grid, risk_info)
                else:
                    content = grid

                panels.append(Panel(content, title=title, expand=False))

            console.print(Columns(panels))
            shown = len(strategy_df.head(display_limit))
            console.print(f"[dim]Showing {shown} of {total_strategy_count} signals[/dim]")

        console.print(f"\n[dim]{VisualStyler.legend()}[/dim]")

    def _render_strategy_matrix(
        self,
        screener: Any,
        df: pd.DataFrame,
        console: Console,
        Table: type[Table],
        limit: int | None = None,
    ) -> None:
        from tvscreener.constants.forex import DEFAULT_LIMIT_MATRIX

        display_limit = limit if limit is not None else DEFAULT_LIMIT_MATRIX
        for strategy in df["STRATEGY"].unique():
            strategy_df = df[df["STRATEGY"] == strategy]
            display_df = strategy_df.head(display_limit) if display_limit > 0 else strategy_df
            self._render_confluence_matrix(
                screener, display_df, console, Table, title=f"Strategy Matrix: {strategy}"
            )

            shown = len(display_df)
            console.print(f"[dim]Showing {shown} of {len(strategy_df)} signals[/dim]")

        console.print(f"\n[dim]{VisualStyler.legend()}[/dim]")


def register_renderers() -> None:
    """Register all default renderers."""
    RichConsoleRenderer.register(
        "ForexOpportunityScreener",
        empty_rich_message="No opportunities found",
        render_method="_render_opportunity",
    )
    RichConsoleRenderer.register(
        "ForexStrategyScanner",
        empty_rich_message="No signals found",
        render_method="_render_strategy",
    )
