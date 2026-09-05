from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from tvscreener_ext.models import (
    AssetSelection,
    OutputConfig,
    RiskConfig,
    ScanRequest,
    ScoringConfig,
)

if TYPE_CHECKING:
    from rich.console import Console

    from tvscreener_ext.orchestrator import ScreenerController


def handle_scan(args: argparse.Namespace, controller: ScreenerController, console: Console) -> int:
    """Handle the 'scan' command."""
    matrix_mode = getattr(args, "matrix", True)
    detailed_mode = getattr(args, "detailed", False)

    # Parse sql_params if provided
    sql_params = {}
    if getattr(args, "sql_params", None):
        import json

        try:
            sql_params = json.loads(args.sql_params)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing --sql-params: {e}[/red]")
            return 1

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
            sql_params=sql_params,
            filters=getattr(args, "filter", []) or [],
            confluence_grade=args.confluence_grade,
            min_opportunity_confluence=args.min_opportunity_confluence,
        ),
    )

    # Runner selection logic
    runner_type = getattr(args, "runner", "prefect")

    if runner_type == "export":
        from tvscreener_ext.runner import PipelineRunSpec

        spec = PipelineRunSpec.from_cli_args(args)
        payload = spec.model_dump_json(indent=2)
        spec_out = getattr(args, "spec_out", None)
        if spec_out:
            from pathlib import Path

            Path(spec_out).write_text(payload, encoding="utf-8")
        else:
            print(payload)
        return 0

    if runner_type == "prefect":
        from tvscreener_ext.runner import PipelineRunSpec

        spec = PipelineRunSpec.from_cli_args(args)
        try:
            from tvscreener_ext.prefect.run_batch import run_prefect

            _ = run_prefect(spec, artifacts_dir=getattr(args, "artifacts_dir", "artifacts/runs"))
            return 0
        except Exception as e:
            console.print(f"[red]Prefect runner failed: {e}[/red]")
            console.print("[dim]Hint: install with `uv sync --extra prefect`[/dim]")
            return 2

    if runner_type == "local":
        from tvscreener_ext.runner import LocalRunner, PipelineRunSpec

        spec = PipelineRunSpec.from_cli_args(args)
        res = LocalRunner(console=console).run(spec)
        if not res.success:
            console.print("\n[bold red]Scan failed[/bold red]")
            return 2
        console.print(f"\n[bold]Total: {res.result_count} results[/bold]")
        return 0 if res.result_count > 0 else 1

    # Fallback to direct controller execution if runner is unknown
    count = controller.run_scan(request)
    if count < 0:
        console.print("\n[bold red]Scan failed[/bold red]")
        return 2

    console.print(f"\n[bold]Total: {count} results[/bold]")
    return 0 if count > 0 else 1
