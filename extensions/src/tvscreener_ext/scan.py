#!/usr/bin/env python3
"""CLI for TradingView scanners (Extensions)."""

from __future__ import annotations

import argparse
import contextlib
import sys

from dotenv import load_dotenv
from rich.console import Console

from tvscreener_ext.cli.scan_handler import handle_scan
from tvscreener_ext.cli.utils import add_common_args, setup_logging
from tvscreener_ext.orchestrator import ScreenerController
from tvscreener_ext.upstream import ensure_upstream_tvscreener
from tvscreener_ext.utils.logic import load_dotenv_file

console = Console()


def main(argv: list[str] | None = None) -> int:
    ensure_upstream_tvscreener()

    load_dotenv(override=False)
    # Best-effort load `.env` so Prefect and other libs
    # see their config without requiring manual exports.
    with contextlib.suppress(Exception):
        load_dotenv_file(".env")

    parser = argparse.ArgumentParser(
        description="TradingView Screener Extensions CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # --- Scan Command ---
    scan_p = subparsers.add_parser("scan", help="Run a scanner (default if no command given)")
    scan_p.add_argument(
        "--scanner",
        "-s",
        choices=["opportunity", "strategy", "inspect"],
        default="strategy",
    )
    scan_p.add_argument(
        "--pipeline",
        choices=["both", "data", "analytics"],
        default="both",
        help="Execution mode",
    )
    scan_p.add_argument(
        "--runner",
        choices=["local", "export", "prefect"],
        default="prefect",
        help="Execution runner",
    )
    scan_p.add_argument("--spec-out", help="Write PipelineRunSpec JSON to file")
    scan_p.add_argument("--artifacts-dir", default="artifacts/runs", help="Artifacts directory")
    scan_p.add_argument(
        "--asset-type",
        choices=["forex", "stock", "stocks", "crypto", "futures", "commodity"],
        default="forex",
    )
    scan_p.add_argument("--universe", "-u")
    scan_p.add_argument("--pairs", nargs="+", help="Specific pairs to scan")
    scan_p.add_argument("--timeframes", "-t", help="Comma-separated timeframes")
    scan_p.add_argument("--contract-type", choices=["spot", "cfd", "spreadbet", "all"])
    scan_p.add_argument("--instrument-type", choices=["spot", "perp"])
    scan_p.add_argument("--output", "-o", help="Output file")
    scan_p.add_argument("--save-config", help="Save opportunity config to YAML")
    scan_p.add_argument("--load-config", help="Load opportunity config from YAML")
    scan_p.add_argument(
        "--strategy",
        choices=["all", "trend", "mean_reversion", "hybrid", "breakout", "confluence"],
        default="all",
    )
    scan_p.add_argument("--direction", choices=["long", "short"], help="Filter by direction")
    scan_p.add_argument("--filter", action="append", help="MTF filter expression")
    scan_p.add_argument("--sql", help="Raw SQL query to filter")
    scan_p.add_argument("--sql-params", help="JSON string of parameters for SQL")
    scan_p.add_argument("--min_volume", type=float, help="Minimum average volume")
    scan_p.add_argument("--max-atr", type=float, help="Maximum ATR")
    scan_p.add_argument("--min-ma-score", type=float, help="Minimum MA score")
    scan_p.add_argument("--min-confluence", type=int, help="Min confluence score")
    scan_p.add_argument("--trend-threshold", type=float, help="Trend score threshold")
    scan_p.add_argument("--mr-threshold", type=float, help="MR score threshold")
    scan_p.add_argument("--rsi-lower", type=float, help="Lower RSI threshold")
    scan_p.add_argument("--rsi-upper", type=float, help="Upper RSI threshold")
    scan_p.add_argument("--min-roc", type=float, help="Min ROC value")
    scan_p.add_argument("--opportunity-trend-weight", type=float, help="Trend weight")
    scan_p.add_argument("--opportunity-ma-weight", type=float, help="MA weight")
    scan_p.add_argument("--opportunity-osc-weight", type=float, help="Oscillator weight")
    scan_p.add_argument("--opportunity-roc-weight", type=float, help="ROC weight")
    scan_p.add_argument("--opportunity-timeframe-weights", help="TF weights (240:0.2,...)")
    scan_p.add_argument("--include-atr", action="store_true", help="Request ATR fields")
    scan_p.add_argument("--include-rsi", action="store_true", help="Request RSI fields")
    scan_p.add_argument(
        "--mr-signal",
        choices=["rsi_oversold", "rsi_overbought"],
        action="append",
        help="MR signal",
    )
    scan_p.add_argument("--min-tf-alignment", type=int, choices=[1, 2, 3], help="Min TF alignment")
    scan_p.add_argument(
        "--require-momentum", action="store_true", help="Require momentum alignment"
    )
    scan_p.add_argument("--min-rvol", type=float, help="Min relative volume")
    scan_p.add_argument("--require-volume-spike", action="store_true", help="Require volume spike")
    scan_p.add_argument("--risk-per-trade", type=float, help="Risk per trade %%")
    scan_p.add_argument("--atr-multiplier", type=float, help="ATR multiplier for SL")
    scan_p.add_argument("--min-risk-reward", type=float, help="Min risk:reward")
    scan_p.add_argument("--account-balance", type=float, help="Account balance")
    scan_p.add_argument("--detailed", action="store_true", help="Show detailed breakdown")
    scan_p.add_argument("--matrix", action="store_true", help="Show confluence matrix")
    scan_p.add_argument("--limit", type=int, help="Limit results shown")
    scan_p.add_argument("--confluence-grade", choices=["A+", "A", "B", "C", "D", "F"])
    scan_p.add_argument("--min-opportunity-confluence", type=int, help="Min grid-aligned cells")
    scan_p.add_argument("--head", type=int, help="Number of rows to show (inspect)")
    scan_p.add_argument("--metadata_only", action="store_true", help="Metadata only (inspect)")
    scan_p.add_argument("--show-risk", action="store_true", help="Show risk metadata")
    add_common_args(scan_p)

    # --- Maintenance Command ---
    maint_p = subparsers.add_parser("maintenance", help="Lakehouse maintenance tools")
    maint_p.add_argument("--expire-snapshots", action="store_true", help="Expire snapshots")
    maint_p.add_argument("--days", type=int, default=7, help="Days to keep snapshots")
    maint_p.add_argument("--table", default="forex.opportunities", help="Table name")
    maint_p.add_argument("--compact", action="store_true", help="Trigger compaction")
    add_common_args(maint_p)

    # --- Query Command ---
    query_p = subparsers.add_parser("query", help="Query Iceberg tables using DuckDB")
    query_p.add_argument("table", help="Table identifier")
    query_p.add_argument("--sql", help="SQL query to execute")
    query_p.add_argument("--snapshot-id", type=int, help="Snapshot ID for time-travel")
    query_p.add_argument("--output", "-o", help="Output file")
    query_p.add_argument("--head", type=int, default=10, help="Number of rows to show")
    add_common_args(query_p)

    # --- Audit Command ---
    audit_p = subparsers.add_parser("audit", help="Audit universe selection")
    audit_p.add_argument("target", choices=["binance-universes"], help="Audit target")
    audit_p.add_argument("--out-dir", default="artifacts/audits/binance-universes")
    audit_p.add_argument("--include-all", action="store_true", help="Include diagnostic universes")
    add_common_args(audit_p)

    # --- Report Command ---
    report_p = subparsers.add_parser("report", help="Generate DuckDB reports")
    report_p.add_argument("target", choices=["binance-universes"], help="Report target")
    report_p.add_argument("--in-dir", default="artifacts/audits/binance-universes")
    report_p.add_argument("--out-dir", default="artifacts/reports/binance-universes")
    add_common_args(report_p)

    # --- Review Command ---
    review_p = subparsers.add_parser("review", help="Run audit + report pipeline")
    review_p.add_argument("target", choices=["binance-universes"], help="Review target")
    review_p.add_argument("--audit-out-dir", default="artifacts/audits/binance-universes")
    review_p.add_argument("--report-out-dir", default="artifacts/reports/binance-universes")
    review_p.add_argument("--strict", action="store_true", help="Fail if audit has errors")
    review_p.add_argument("--include-all", action="store_true", help="Include diagnostic universes")
    add_common_args(review_p)

    # Default to scan if no command given (backwards compatibility)
    effective_argv = sys.argv[1:] if argv is None else argv[1:]
    if not effective_argv or effective_argv[0] not in subparsers.choices:
        effective_argv = ["scan"] + effective_argv

    args = parser.parse_args(effective_argv)
    setup_logging(args.verbose)

    controller = ScreenerController(console=console)

    if args.command == "scan":
        return handle_scan(args, controller, console)
    if args.command == "maintenance":
        return controller.run_maintenance(args)
    if args.command == "query":
        return controller.run_query(args)
    if args.command == "audit":
        return controller.run_audit(args)
    if args.command == "report":
        return controller.run_report(args)
    if args.command == "review":
        return controller.run_review(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
