from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from tvscreener_ext.models import (
    AssetSelection,
    OutputConfig,
    RiskConfig,
    ScanRequest,
    ScoringConfig,
)
from tvscreener_ext.orchestrator import ScreenerController
from tvscreener_ext.utils.logic import canonicalize_asset_type, timeframe_set_id

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _resolve_code_version() -> str:
    env_version = (os.getenv("TVSCREENER_CODE_VERSION") or "").strip()
    if env_version:
        return env_version

    try:
        raw = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if raw:
            return raw
    except Exception:
        pass
    return "unknown"


def _persist_run_record(spec: PipelineRunSpec, result: RunResult) -> None:
    from tvscreener_ext.lakehouse import write_iceberg

    ingest_date = result.started_at_utc.astimezone(UTC).strftime("%Y-%m-%d")
    payload = {
        "run_id": spec.params_hash,
        "params_hash": result.params_hash,
        "code_version": spec.code_version or "unknown",
        "scanner_family": result.scanner_family,
        "pipeline_mode_requested": spec.pipeline_mode,
        "pipeline_mode_executed": result.pipeline_mode_executed,
        "asset_type": spec.asset_type,
        "timeframes": ",".join(spec.timeframes or []),
        "timeframe_set_id": spec.timeframe_set_id or "",
        "source": "tradingview",
        "universe": spec.universe or "",
        "instrument_type": spec.instrument_type or "",
        "pairs_count": len(spec.pairs or []),
        "config_path": spec.config_path or "",
        "started_at_utc": result.started_at_utc,
        "finished_at_utc": result.finished_at_utc,
        "success": result.success,
        "result_count": result.result_count,
        "exit_code": result.exit_code,
        "errors_json": json.dumps(result.errors, sort_keys=True),
        "ingest_date": ingest_date,
    }

    try:
        import pandas as pd

        write_iceberg(
            pd.DataFrame([payload]),
            "tvscreener.runs",
            mode="append",
            partition_by=["asset_type", "ingest_date"],
        )
    except Exception as exc:
        if (os.getenv("TVSCREENER_STRICT_PERSIST") or "").strip() == "1":
            raise

        logger.debug("Run metadata persistence failed: %s", exc)


class PipelineRunSpec(BaseModel):
    """Serializable contract for defining a pipeline run.

    This model is intended to be engine-agnostic. External workflow engines should treat it as their run config.
    """

    spec_version: int = 1

    scanner_family: str = Field(description="opportunity | strategy")
    pipeline_mode: str = Field(default="both", description="data | analytics | both")

    asset_type: str = "forex"
    universe: str | None = None
    pairs: list[str] | None = None

    timeframes: list[str] = Field(default_factory=list)
    timeframe_set_id: str | None = None

    # Asset/scanner parameters
    strategy: str | None = None
    contract_type: str | None = None
    instrument_type: str | None = None
    min_volume: float | None = None
    max_atr: float | None = None
    min_ma_score: float | None = None
    min_roc: float | None = None
    min_rvol: float | None = None
    require_volume_spike: bool | None = None
    include_atr: bool | None = None
    include_rsi: bool | None = None

    # Scoring / strategy thresholds
    direction: str | None = None
    min_confluence: int | None = None
    trend_threshold: float | None = None
    mr_threshold: float | None = None
    rsi_lower: float | None = None
    rsi_upper: float | None = None
    mr_signal: list[str] = Field(default_factory=list)
    min_tf_alignment: int | None = None
    require_momentum: bool | None = None
    opportunity_trend_weight: float | None = None
    opportunity_ma_weight: float | None = None
    opportunity_osc_weight: float | None = None
    opportunity_roc_weight: float | None = None
    opportunity_timeframe_weights: str | None = None

    # Risk controls
    risk_per_trade: float | None = None
    atr_multiplier: float | None = None
    min_risk_reward: float | None = None
    account_balance: float | None = None

    # Analytics filters
    sql: str | None = None
    sql_params: dict[str, Any] = Field(default_factory=dict)
    filters: list[str] = Field(default_factory=list)

    # Output controls
    output: str | None = None
    detailed: bool | None = None
    matrix: bool | None = None
    limit: int | None = None
    head: int | None = None
    metadata_only: bool | None = None
    show_risk: bool | None = None
    confluence_grade: str | None = None
    min_opportunity_confluence: int | None = None

    # Config pointer + reproducibility
    config_path: str | None = None
    created_at_utc: datetime = Field(default_factory=_utc_now)
    params_hash: str | None = None
    code_version: str | None = None

    def _hash_payload(self) -> dict[str, Any]:
        """Payload used for stable hashing (exclude volatile/runtime fields)."""
        return self.model_dump(
            exclude={
                "created_at_utc",
                "params_hash",
                "code_version",
            },
            exclude_none=True,
        )

    def compute_params_hash(self) -> str:
        payload = self._hash_payload()
        raw = _canonical_json(payload).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def normalized(self) -> PipelineRunSpec:
        """Return a normalized copy with derived fields populated."""
        tf = [str(t).strip() for t in self.timeframes if str(t).strip()]
        at = canonicalize_asset_type(self.asset_type)
        scanner = (self.scanner_family or "").strip().lower()
        pipeline = (self.pipeline_mode or "both").strip().lower()
        tfs_id = self.timeframe_set_id
        if tf and not tfs_id:
            tfs_id = timeframe_set_id(tf)
        spec = self.model_copy(
            update={
                "asset_type": at,
                "scanner_family": scanner or self.scanner_family,
                "pipeline_mode": pipeline or self.pipeline_mode,
                "timeframes": tf,
                "timeframe_set_id": tfs_id,
            }
        )
        if not spec.params_hash:
            spec = spec.model_copy(update={"params_hash": spec.compute_params_hash()})
        if not spec.code_version:
            spec = spec.model_copy(update={"code_version": _resolve_code_version()})
        return spec

    @classmethod
    def from_cli_args(cls, args: Any) -> PipelineRunSpec:
        tfs: list[str]
        if getattr(args, "timeframes", None):
            tfs = [t.strip() for t in str(args.timeframes).split(",") if t.strip()]
        else:
            tfs = []

        detailed = getattr(args, "detailed", None)
        matrix = getattr(args, "matrix", None)
        if bool(detailed) is False and bool(matrix) is False:
            # Match CLI/orchestrator behavior: default to matrix view if neither is explicitly set.
            matrix = True

        spec = cls(
            scanner_family=str(getattr(args, "scanner", "strategy")),
            pipeline_mode=str(getattr(args, "pipeline", "both")),
            asset_type=str(getattr(args, "asset_type", "forex")),
            universe=getattr(args, "universe", None),
            pairs=getattr(args, "pairs", None),
            timeframes=tfs,
            strategy=getattr(args, "strategy", None),
            contract_type=getattr(args, "contract_type", None),
            instrument_type=getattr(args, "instrument_type", None),
            min_volume=getattr(args, "min_volume", None),
            max_atr=getattr(args, "max_atr", None),
            min_ma_score=getattr(args, "min_ma_score", None),
            min_roc=getattr(args, "min_roc", None),
            min_rvol=getattr(args, "min_rvol", None),
            require_volume_spike=getattr(args, "require_volume_spike", None),
            include_atr=getattr(args, "include_atr", None),
            include_rsi=getattr(args, "include_rsi", None),
            direction=getattr(args, "direction", None),
            min_confluence=getattr(args, "min_confluence", None),
            trend_threshold=getattr(args, "trend_threshold", None),
            mr_threshold=getattr(args, "mr_threshold", None),
            rsi_lower=getattr(args, "rsi_lower", None),
            rsi_upper=getattr(args, "rsi_upper", None),
            mr_signal=getattr(args, "mr_signal", []) or [],
            min_tf_alignment=getattr(args, "min_tf_alignment", None),
            require_momentum=getattr(args, "require_momentum", None),
            opportunity_trend_weight=getattr(args, "opportunity_trend_weight", None),
            opportunity_ma_weight=getattr(args, "opportunity_ma_weight", None),
            opportunity_osc_weight=getattr(args, "opportunity_osc_weight", None),
            opportunity_roc_weight=getattr(args, "opportunity_roc_weight", None),
            opportunity_timeframe_weights=getattr(args, "opportunity_timeframe_weights", None),
            risk_per_trade=getattr(args, "risk_per_trade", None),
            atr_multiplier=getattr(args, "atr_multiplier", None),
            min_risk_reward=getattr(args, "min_risk_reward", None),
            account_balance=getattr(args, "account_balance", None),
            sql=getattr(args, "sql", None),
            sql_params=getattr(args, "sql_params", {}) or {},
            filters=getattr(args, "filter", []) or [],
            output=getattr(args, "output", None),
            detailed=detailed,
            matrix=matrix,
            limit=getattr(args, "limit", None),
            head=getattr(args, "head", None),
            metadata_only=getattr(args, "metadata_only", None),
            show_risk=getattr(args, "show_risk", None),
            confluence_grade=getattr(args, "confluence_grade", None),
            min_opportunity_confluence=getattr(args, "min_opportunity_confluence", None),
            config_path=getattr(args, "config", None),
        )
        return spec.normalized()

    def to_scan_request(self) -> ScanRequest:
        tfs_str = ",".join(self.timeframes) if self.timeframes else None
        return ScanRequest(
            assets=AssetSelection(
                scanner=self.scanner_family,
                pipeline=self.pipeline_mode,
                strategy=self.strategy or "all",
                asset_type=self.asset_type,
                universe=self.universe,
                pairs=self.pairs,
                timeframes=tfs_str,
                contract_type=self.contract_type,
                instrument_type=self.instrument_type,
                min_volume=self.min_volume,
                max_atr=self.max_atr,
                min_ma_score=self.min_ma_score,
                min_roc=self.min_roc,
                min_rvol=self.min_rvol,
                require_volume_spike=bool(self.require_volume_spike)
                if self.require_volume_spike is not None
                else False,
                include_atr=bool(self.include_atr) if self.include_atr is not None else False,
                include_rsi=bool(self.include_rsi) if self.include_rsi is not None else False,
            ),
            scoring=ScoringConfig(
                opportunity_trend_weight=self.opportunity_trend_weight,
                opportunity_ma_weight=self.opportunity_ma_weight,
                opportunity_osc_weight=self.opportunity_osc_weight,
                opportunity_roc_weight=self.opportunity_roc_weight,
                opportunity_timeframe_weights=self.opportunity_timeframe_weights,
                filter_direction=self.direction,
                min_confluence=self.min_confluence,
                trend_threshold=self.trend_threshold,
                mr_threshold=self.mr_threshold,
                rsi_lower=self.rsi_lower,
                rsi_upper=self.rsi_upper,
                mr_signal=self.mr_signal or [],
                min_tf_alignment=self.min_tf_alignment,
                require_momentum=bool(self.require_momentum)
                if self.require_momentum is not None
                else False,
            ),
            risk=RiskConfig(
                risk_per_trade_pct=self.risk_per_trade,
                atr_multiplier=self.atr_multiplier,
                min_risk_reward_ratio=self.min_risk_reward,
                account_balance=self.account_balance,
            ),
            output=OutputConfig(
                output=self.output,
                detailed=bool(self.detailed) if self.detailed is not None else False,
                matrix=bool(self.matrix) if self.matrix is not None else False,
                limit=self.limit,
                head=self.head,
                metadata_only=bool(self.metadata_only) if self.metadata_only is not None else False,
                show_risk=bool(self.show_risk) if self.show_risk is not None else False,
                sql=self.sql,
                sql_params=self.sql_params or {},
                filters=self.filters or [],
                confluence_grade=self.confluence_grade,
                min_opportunity_confluence=self.min_opportunity_confluence,
                config_path=self.config_path,
            ),
        )


class RunResult(BaseModel):
    spec_version: int = 1

    params_hash: str
    scanner_family: str
    pipeline_mode_executed: str

    started_at_utc: datetime
    finished_at_utc: datetime

    success: bool
    result_count: int
    exit_code: int
    errors: list[str] = Field(default_factory=list)

    # Optional artifact paths
    results_path: str | None = None
    results_table_path: str | None = None
    matrix_path: str | None = None
    matrix_md_path: str | None = None
    grade_summary_table_path: str | None = None

    # Optional audit fields (best-effort)
    tables_read: list[str] = Field(default_factory=list)
    tables_written: list[str] = Field(default_factory=list)


class PipelineRunner(Protocol):
    def run(self, spec: PipelineRunSpec) -> RunResult: ...


class LocalRunner:
    """In-process runner that delegates to the existing orchestrator."""

    def __init__(self, console: Any | None = None):
        self._console = console

    def run(self, spec: PipelineRunSpec) -> RunResult:
        started = _utc_now()
        spec = spec.normalized()
        env_run_id = spec.params_hash or spec.compute_params_hash()

        previous_env = {
            "TVSCREENER_RUN_ID": os.environ.get("TVSCREENER_RUN_ID"),
            "TVSCREENER_PARAMS_HASH": os.environ.get("TVSCREENER_PARAMS_HASH"),
            "TVSCREENER_CODE_VERSION": os.environ.get("TVSCREENER_CODE_VERSION"),
            "TVSCREENER_INSTRUMENT_TYPE": os.environ.get("TVSCREENER_INSTRUMENT_TYPE"),
        }
        os.environ["TVSCREENER_RUN_ID"] = env_run_id
        os.environ["TVSCREENER_PARAMS_HASH"] = env_run_id
        os.environ["TVSCREENER_CODE_VERSION"] = spec.code_version or "unknown"
        if spec.instrument_type:
            os.environ["TVSCREENER_INSTRUMENT_TYPE"] = spec.instrument_type

        # Ensure lakehouse config is initialized consistently for this process.
        from tvscreener_ext.lakehouse import get_manager

        get_manager(spec.config_path)

        controller = ScreenerController(console=self._console)

        # Keep renderer registration lazy and optional: only needed when using the rich console.
        if self._console is not None:
            try:
                from tvscreener_ext.screeners.renderers.rich_console import register_renderers

                register_renderers()

            except Exception:
                # Rendering is optional; avoid blocking non-interactive runners.
                pass

        try:
            count = controller.run_scan(spec.to_scan_request())
            success = count >= 0
            exit_code = 0 if success else 2
            errors: list[str] = []
        except Exception as e:
            count = -1
            success = False
            exit_code = 2
            errors = [str(e)]
        finally:
            for key, previous in previous_env.items():
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous

        finished = _utc_now()
        result = RunResult(
            params_hash=spec.params_hash or spec.compute_params_hash(),
            scanner_family=spec.scanner_family,
            pipeline_mode_executed=spec.pipeline_mode,
            started_at_utc=started,
            finished_at_utc=finished,
            success=success,
            result_count=max(0, int(count)),
            exit_code=exit_code,
            errors=errors,
        )
        _persist_run_record(spec, result)
        return result
