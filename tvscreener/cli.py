#!/usr/bin/env python3
"""CLI for TradingView scanners."""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys

from rich.console import Console

from tvscreener.lib.orchestrator import ScreenerController
from tvscreener.util import load_dotenv_file

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main() -> int:
    # Best-effort load `.env` so Prefect and other libs
    # see their config without requiring manual exports.
    with contextlib.suppress(Exception):
        load_dotenv_file(".env")

    # Handle maintenance subcommand separately to preserve top-level compatibility for scans
    if len(sys.argv) > 1 and sys.argv[1] == "maintenance":
        parser = argparse.ArgumentParser(description="Lakehouse maintenance tools")
        parser.add_argument("command", choices=["maintenance"])
        parser.add_argument(
            "--expire-snapshots", action="store_true", help="Expire snapshots older than X days"
        )
        parser.add_argument("--days", type=int, default=7, help="Days to keep snapshots")
        parser.add_argument("--table", default="forex.opportunities", help="Table name")
        parser.add_argument("--compact", action="store_true", help="Trigger file compaction (Hook)")
        parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
        parser.add_argument("--config", help="Path to YAML config")

        args = parser.parse_args()
    elif len(sys.argv) > 1 and sys.argv[1] == "query":
        parser = argparse.ArgumentParser(description="Query Iceberg tables using DuckDB")
        parser.add_argument("command", choices=["query"])
        parser.add_argument("table", help="Table identifier (e.g. forex.opportunities)")
        parser.add_argument(
            "--sql",
            help="SQL query to execute (can use MiniJinja 'df' as the table alias)",
        )
        parser.add_argument("--snapshot-id", type=int, help="Iceberg snapshot ID for time-travel")
        parser.add_argument("--output", "-o", help="Output file (csv/parquet)")
        parser.add_argument("--head", type=int, default=10, help="Number of rows to show")
        parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
        parser.add_argument("--config", help="Path to YAML config")

        args = parser.parse_args()
    else:
        parser = argparse.ArgumentParser(
            description="Run TradingView scanners",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        parser.add_argument(
            "--config",
            default=None,
            help="Path to YAML config (default: tvscreener.yaml)",
        )

        parser.add_argument(
            "--scanner",
            "-s",
            choices=["opportunity", "strategy", "inspect"],
            default="strategy",
        )
        parser.add_argument(
            "--pipeline",
            choices=["both", "data", "analytics"],
            default="both",
            help="Execution mode: data (fetch+Iceberg), analytics (Iceberg+render), both (data then analytics)",
        )
        parser.add_argument(
            "--runner",
            choices=["local", "export", "prefect"],
            default="prefect",
            help="Execution runner: prefect (execute via Prefect flow), local (execute in-process), export (emit PipelineRunSpec JSON)",
        )
        parser.add_argument(
            "--spec-out",
            default=None,
            help="Write PipelineRunSpec JSON to this file (only when --runner export)",
        )
        parser.add_argument(
            "--artifacts-dir",
            default="artifacts/runs",
            help="Artifacts directory (used by --runner prefect)",
        )
        parser.add_argument(
            "--asset-type",
            choices=["forex", "stock", "stocks", "crypto", "futures", "commodity"],
            default="forex",
        )
        parser.add_argument(
            "--universe",
            "-u",
            choices=[
                "majors",
                "minors",
                "all",
                "binance_spot_top100",
                "binance_perp_top100",
                "binance_spot_mcap_top100",
                "binance_perp_mcap_top100",
            ],
            default=None,
        )
        parser.add_argument("--pairs", nargs="+", help="Specific pairs to scan")
        parser.add_argument("--timeframes", "-t", default=None, help="Comma-separated timeframes")
        parser.add_argument(
            "--contract-type",
            choices=["spot", "cfd", "spreadbet", "all"],
            default=None,
            help="Contract type to filter (default: cfd)",
        )
        parser.add_argument(
            "--instrument-type",
            choices=["spot", "perp"],
            default=None,
            help="Instrument type (crypto only): spot or perp",
        )
        parser.add_argument("--output", "-o", help="Output file (csv/json/parquet/xml)")
        parser.add_argument("--save-config", help="Save opportunity config to YAML")
        parser.add_argument("--load-config", help="Load opportunity config from YAML")
        parser.add_argument(
            "--strategy",
            choices=["all", "trend", "mean_reversion", "hybrid", "breakout", "confluence"],
            default="all",
        )
        parser.add_argument("--direction", choices=["long", "short"], help="Filter by direction")
        parser.add_argument(
            "--filter", action="append", help="MTF filter expression (e.g. '1H:TREND > 0')"
        )
        parser.add_argument("--sql", help="Raw SQL query to filter the results")
        parser.add_argument(
            "--sql-params",
            type=str,
            help="JSON string of parameters for the SQL query",
        )
        parser.add_argument("--min_volume", type=float, help="Minimum average volume")
        parser.add_argument("--max-atr", type=float, help="Maximum ATR (volatility proxy)")
        parser.add_argument("--min-ma-score", type=float, help="Minimum MA score (-2 to 2)")
        parser.add_argument(
            "--min-confluence",
            type=int,
            help="Minimum confluence score (strategy scanner)",
        )
        parser.add_argument(
            "--trend-threshold",
            type=float,
            help="Trend score threshold (strategy scanner)",
        )
        parser.add_argument(
            "--mr-threshold",
            type=float,
            help="Mean-reversion score threshold (strategy scanner)",
        )
        parser.add_argument(
            "--rsi-lower",
            type=float,
            help="Lower RSI threshold for oversold signals",
        )
        parser.add_argument(
            "--rsi-upper",
            type=float,
            help="Upper RSI threshold for overbought signals",
        )
        parser.add_argument(
            "--min-roc",
            type=float,
            help="Minimum ROC value for breakout filter",
        )
        parser.add_argument(
            "--opportunity-trend-weight",
            type=float,
            help="Trend weight for opportunity scoring",
        )
        parser.add_argument(
            "--opportunity-ma-weight",
            type=float,
            help="MA weight for opportunity scoring",
        )
        parser.add_argument(
            "--opportunity-osc-weight",
            type=float,
            help="Oscillator weight for opportunity scoring",
        )
        parser.add_argument(
            "--opportunity-roc-weight",
            type=float,
            help="ROC weight for opportunity scoring",
        )
        parser.add_argument(
            "--opportunity-timeframe-weights",
            help="Timeframe weights for opportunity scoring (format 240:0.2,60:0.3,15:0.5)",
        )
        parser.add_argument(
            "--include-atr",
            action="store_true",
            help="Request ATR fields when running strategy scan",
        )
        parser.add_argument(
            "--include-rsi",
            action="store_true",
            help="Request RSI fields when running strategy scan",
        )
        parser.add_argument(
            "--mr-signal",
            choices=["rsi_oversold", "rsi_overbought"],
            action="append",
            help="Mean reversion signal (can be specified multiple times)",
        )
        # Risk management signal quality filters
        parser.add_argument(
            "--min-tf-alignment",
            type=int,
            choices=[1, 2, 3],
            help="Minimum aligned timeframes for signal quality",
        )
        parser.add_argument(
            "--require-momentum",
            action="store_true",
            help="Require ROC to align with direction",
        )
        parser.add_argument(
            "--min-rvol",
            type=float,
            help="Minimum relative volume (1.0 = average)",
        )
        parser.add_argument(
            "--require-volume-spike",
            action="store_true",
            help="Require volume > 1.5x average",
        )
        # Risk management parameters
        parser.add_argument(
            "--risk-per-trade",
            type=float,
            help="Risk per trade as percentage (default from settings)",
        )
        parser.add_argument(
            "--atr-multiplier",
            type=float,
            help="ATR multiplier for stop loss calculation",
        )
        parser.add_argument(
            "--min-risk-reward",
            type=float,
            help="Minimum risk:reward ratio",
        )
        parser.add_argument(
            "--account-balance",
            type=float,
            help="Account balance for position sizing",
        )
        # Output format options
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed per-pair breakdown with TF analysis",
        )
        parser.add_argument(
            "--matrix",
            action="store_true",
            help="Show confluence matrix view for all pairs",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Number of results to show in summary/detailed/matrix views",
        )
        parser.add_argument(
            "--confluence-grade",
            choices=["A+", "A", "B", "C", "D", "F"],
            help="Filter by confluence grade",
        )
        parser.add_argument(
            "--min-opportunity-confluence",
            type=int,
            help="Minimum grid-aligned cells (0-12) for opportunity scanner",
        )
        # Inspect options
        parser.add_argument(
            "--head",
            type=int,
            help="Number of rows to show when inspecting parquet",
        )
        parser.add_argument(
            "--metadata-only",
            action="store_true",
            help="Only show metadata when inspecting parquet",
        )
        parser.add_argument(
            "--show-risk",
            action="store_true",
            help="Show risk management metadata (SL/TP/RR/Size) in output",
        )
        parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

        args = parser.parse_args()
        args.command = "scan"

    setup_logging(args.verbose)

    # Parse sql_params if provided
    if getattr(args, "sql_params", None):
        import json

        try:
            args.sql_params = json.loads(args.sql_params)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing --sql-params: {e}[/red]")
            return 1
    else:
        args.sql_params = {}

    # Export runner: emit a PipelineRunSpec JSON payload for workflow engines.
    if getattr(args, "command", None) == "scan" and getattr(args, "runner", "prefect") == "export":
        from tvscreener.lib.pipeline_runner import PipelineRunSpec

        spec = PipelineRunSpec.from_cli_args(args)
        payload = spec.model_dump_json(indent=2)
        spec_out = getattr(args, "spec_out", None)
        if spec_out:
            from pathlib import Path

            Path(spec_out).write_text(payload, encoding="utf-8")
        else:
            print(payload)
        return 0

    # Prefect runner: execute via Prefect flow in-process (no intermediate spec file required).
    if getattr(args, "command", None) == "scan" and getattr(args, "runner", "prefect") == "prefect":
        from tvscreener.lib.pipeline_runner import PipelineRunSpec

        spec = PipelineRunSpec.from_cli_args(args)
        try:
            from tvscreener.lib.prefect_runner import run_prefect

            _ = run_prefect(spec, artifacts_dir=getattr(args, "artifacts_dir", "artifacts/runs"))
            return 0
        except Exception as e:
            console.print(f"[red]Prefect runner failed: {e}[/red]")
            console.print("[dim]Hint: install with `uv sync --extra prefect`[/dim]")
            return 2

    # Register renderers (interactive CLI output)
    from tvscreener.lib.screeners.renderers.rich_console import register_renderers

    register_renderers()

    # Initialize orchestrator and run
    controller = ScreenerController(console=console)
    count = controller.run_from_args(args)

    if count < 0:
        console.print("\n[bold red]Scan failed[/bold red]")
        return 2

    console.print(f"\n[bold]Total: {count} results[/bold]")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
