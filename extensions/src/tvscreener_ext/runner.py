from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
import pandas as pd
from pydantic import BaseModel, Field

from tvscreener_ext.lakehouse import LakehouseManager
from tvscreener_ext.universes import resolve_universe
from tvscreener_ext.upstream import ensure_upstream_tvscreener

PipelineMode = Literal["data", "analytics", "both"]


class PipelineRunSpec(BaseModel):
    spec_version: str = "1"

    scanner_family: str = "opportunity"
    pipeline_mode: PipelineMode = "both"
    asset_type: str
    instrument_type: str | None = None
    universe: str
    timeframes: list[str] = Field(default_factory=lambda: ["240", "60", "15"])

    limit: int = 50
    matrix: bool = True

    config_path: str | None = None
    artifacts_dir: str = "artifacts/runs"
    output: str | None = None

    params_hash: str | None = None

    def normalized(self) -> PipelineRunSpec:
        tf = [str(t).strip() for t in self.timeframes if str(t).strip()]
        tf = list(dict.fromkeys(tf))
        tf = sorted(tf, key=lambda s: int(s) if s.isdigit() else 999999, reverse=True)
        out = self.model_copy(
            update={
                "scanner_family": str(self.scanner_family).strip().lower(),
                "pipeline_mode": str(self.pipeline_mode).strip().lower(),
                "asset_type": str(self.asset_type).strip().lower(),
                "instrument_type": str(self.instrument_type).strip().lower()
                if self.instrument_type
                else None,
                "universe": str(self.universe).strip().lower(),
                "timeframes": tf,
            }
        )
        if not out.params_hash:
            out = out.model_copy(update={"params_hash": stable_params_hash(out)})
        return out


def stable_params_hash(spec: PipelineRunSpec) -> str:
    payload = spec.model_dump(exclude={"params_hash"}, mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class RunResult:
    params_hash: str
    pipeline_mode_requested: str
    pipeline_mode_executed: str
    artifacts_dir: str
    success: bool
    result_count: int
    results_path: str | None
    matrix_path: str | None
    matrix_md_path: str | None
    results_table_path: str | None
    grade_summary_table_path: str | None
    errors: list[str]


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: object) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _load_field(enum_cls: Any, name: str) -> Any | None:
    try:
        return getattr(enum_cls, name)
    except Exception:
        return None


def _fetch_upstream_snapshot(
    *,
    asset_type: str,
    instrument_type: str | None,
    tickers: list[str],
    timeframes: list[str],
    limit: int,
) -> pd.DataFrame:
    ensure_upstream_tvscreener()

    at = (asset_type or "").strip().lower()
    _ = (instrument_type or "").strip().lower() if instrument_type else None

    if at == "forex":
        from tvscreener.core.forex import ForexScreener
        from tvscreener.field.forex import ForexField as F

        s = ForexScreener()
        # ForexScreener injects a misc `symbols` key which overrides `self.symbols`.
        s.misc.pop("symbols", None)
    elif at == "crypto":
        from tvscreener.core.crypto import CryptoScreener
        from tvscreener.field.crypto import CryptoField as F

        s = CryptoScreener()
    elif at == "stock":
        from tvscreener.core.stock import StockScreener
        from tvscreener.field.stock import StockField as F

        s = StockScreener()
    else:
        raise ValueError(f"Unsupported asset_type: {asset_type}")

    # Restrict to explicit tickers.
    s.symbols = {"query": {"types": []}, "tickers": list(tickers)}

    fields: list[Any] = []
    fields += [F.NAME]
    for tf in timeframes:
        for base in ("CLOSE", "EMA20", "RSI10", "ROC"):
            fld = _load_field(F, f"{base}_{tf}")
            if fld is not None:
                fields.append(fld)

    # Ensure at least one price field exists.
    if not any(getattr(f, "name", "").startswith("CLOSE_") for f in fields):
        close_any = _load_field(F, "PRICE")
        if close_any is not None:
            fields.append(close_any)

    s.select(*fields)
    s.set_range(0, max(int(limit), len(tickers)))
    df = s.get()
    return pd.DataFrame(df)


def _to_bronze(df: pd.DataFrame, *, spec: PipelineRunSpec, fetched_at: datetime) -> pd.DataFrame:
    fetched_at_naive = fetched_at.astimezone(UTC).replace(tzinfo=None)
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        entity_id = str(r.get("Symbol") or "").strip()
        name = str(r.get("Name") or "").strip()
        for tf in spec.timeframes:
            rec: dict[str, Any] = {
                "entity_id": entity_id,
                "name": name,
                "asset_type": spec.asset_type,
                "instrument_type": spec.instrument_type or "",
                "universe": spec.universe,
                "timeframe": tf,
                "fetched_at_utc": fetched_at_naive,
                "params_hash": spec.params_hash,
            }
            for col, out_key in (
                (f"Close|{tf}", "close"),
                (f"Ema20|{tf}", "ema20"),
                (f"Rsi10|{tf}", "rsi10"),
                (f"Roc|{tf}", "roc"),
            ):
                if col in df.columns:
                    rec[out_key] = pd.to_numeric(r.get(col), errors="coerce")
            rows.append(rec)
    return pd.DataFrame(rows)


def _compute_signals_latest(bronze: pd.DataFrame, *, spec: PipelineRunSpec) -> pd.DataFrame:
    if bronze.empty:
        return pd.DataFrame()

    pivot_cols = [
        "entity_id",
        "name",
        "asset_type",
        "instrument_type",
        "universe",
        "params_hash",
        "fetched_at_utc",
    ]
    out_rows: list[dict[str, Any]] = []
    for _entity_id, g in bronze.groupby("entity_id", dropna=False):
        row: dict[str, Any] = {}
        head = g.iloc[0]
        for c in pivot_cols:
            row[c] = head.get(c)

        bulls = 0
        total = 0

        for tf in spec.timeframes:
            gg = g.loc[g["timeframe"] == tf]
            if gg.empty:
                continue
            rr = gg.iloc[0]
            close = rr.get("close")
            ema20 = rr.get("ema20")
            rsi10 = rr.get("rsi10")
            roc = rr.get("roc")

            def _flag(val: Any) -> str:
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return "neutral"
                try:
                    return "bull" if float(val) > 0 else "bear"
                except Exception:
                    return "neutral"

            trend = _flag(roc)
            ma = "neutral"
            if (
                close is not None
                and ema20 is not None
                and not pd.isna(close)
                and not pd.isna(ema20)
            ):
                ma = "bull" if float(close) >= float(ema20) else "bear"
            osc = "neutral"
            if rsi10 is not None and not pd.isna(rsi10):
                osc = "bull" if float(rsi10) >= 50.0 else "bear"
            roc_flag = trend

            row[f"trend_{tf}"] = trend
            row[f"ma_{tf}"] = ma
            row[f"osc_{tf}"] = osc
            row[f"roc_{tf}"] = roc_flag

            for flag in (trend, ma, osc, roc_flag):
                if flag == "neutral":
                    continue
                total += 1
                if flag == "bull":
                    bulls += 1

        score = (bulls / total) if total > 0 else 0.0
        row["bull_count"] = int(bulls)
        row["total_count"] = int(total)
        row["score"] = float(score)

        if score >= 0.90:
            grade = "A+"
        elif score >= 0.80:
            grade = "A"
        elif score >= 0.70:
            grade = "B"
        elif score >= 0.60:
            grade = "C"
        else:
            grade = "D"
        row["grade"] = grade
        row["direction"] = "bull" if bulls >= max(1, total - bulls) else "bear"

        out_rows.append(row)

    return pd.DataFrame(out_rows)


def _render_matrix(df: pd.DataFrame, *, spec: PipelineRunSpec) -> str:
    if df is None or df.empty:
        return "(no rows)"

    def _pick(*candidates: str) -> str | None:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    entity_col = _pick("entity_id", "Symbol") or "entity_id"
    grade_col = _pick("grade", "grade_1", "GRADE")
    direction_col = _pick("direction", "direction_1", "DIRECTION")

    cols: list[str] = [entity_col]
    if direction_col:
        cols.append(direction_col)
    if grade_col:
        cols.append(grade_col)

    for tf in spec.timeframes:
        cols += [
            _pick(f"trend_{tf}", f"trend_{tf}_1", f"TREND_{tf}") or f"trend_{tf}",
            _pick(f"ma_{tf}", f"ma_{tf}_1", f"MA_{tf}") or f"ma_{tf}",
            _pick(f"osc_{tf}", f"osc_{tf}_1", f"OSC_{tf}") or f"osc_{tf}",
            _pick(f"roc_{tf}", f"roc_{tf}_1", f"ROC_{tf}") or f"roc_{tf}",
        ]

    view = df.copy()
    for c in cols:
        if c not in view.columns:
            view[c] = None
    return view[cols].to_string(index=False)


def _render_matrix_markdown(matrix_text: str, *, spec: PipelineRunSpec) -> str:
    title = (
        f"Matrix: {spec.scanner_family} {spec.asset_type}"
        + (f" {spec.instrument_type}" if spec.instrument_type else "")
        + f" {spec.universe}"
    )
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- `pipeline_mode`: `{spec.pipeline_mode}`",
            f"- `timeframes`: `{','.join(spec.timeframes)}`",
            f"- `limit`: `{spec.limit}`",
            "",
            "```text",
            matrix_text.rstrip(),
            "```",
            "",
        ]
    )


class LocalRunner:
    def run(self, spec: PipelineRunSpec) -> RunResult:
        spec = spec.normalized()
        params_hash = spec.params_hash or stable_params_hash(spec)

        artifacts_base = Path(spec.artifacts_dir)
        run_dir = artifacts_base / params_hash
        _ensure_dir(run_dir)

        started = _utc_now()
        errors: list[str] = []
        results_path: str | None = None
        matrix_path: str | None = None
        matrix_md_path: str | None = None
        results_table_path: str | None = None
        grade_summary_table_path: str | None = None
        result_count = 0
        success = False
        pipeline_mode_executed: str = spec.pipeline_mode

        _write_json(run_dir / "run_spec.json", spec.model_dump(mode="json"))

        try:
            lh = LakehouseManager(config_path=spec.config_path)

            if spec.pipeline_mode in {"data", "both"}:
                uni = resolve_universe(
                    asset_type=spec.asset_type,
                    universe=spec.universe,
                    instrument_type=spec.instrument_type,
                )
                fetched_at = _utc_now()
                snap = _fetch_upstream_snapshot(
                    asset_type=spec.asset_type,
                    instrument_type=spec.instrument_type,
                    tickers=uni.tickers,
                    timeframes=spec.timeframes,
                    limit=spec.limit,
                )
                bronze = _to_bronze(snap, spec=spec, fetched_at=fetched_at)
                lh.write_table(bronze, "tvscreener.bronze", mode="append")

                latest = _compute_signals_latest(bronze, spec=spec)
                lh.write_table(
                    latest,
                    "tvscreener.signals_latest",
                    mode="overwrite",
                    partition_by=["asset_type", "instrument_type", "universe"],
                )
                result_count = int(len(latest))
                pipeline_mode_executed = "data" if spec.pipeline_mode == "data" else "both"

            if spec.pipeline_mode in {"analytics", "both"}:
                arrow = lh.read_table_arrow("tvscreener.signals_latest")
                con = duckdb.connect(database=":memory:")
                con.register("signals_latest", arrow)

                where = [f"asset_type = '{spec.asset_type}'", f"universe = '{spec.universe}'"]
                if spec.instrument_type:
                    where.append(f"instrument_type = '{spec.instrument_type}'")
                sql = (
                    "SELECT * FROM signals_latest WHERE "
                    + " AND ".join(where)
                    + " ORDER BY score DESC"
                )
                out_df = con.execute(sql).df()
                if spec.limit:
                    out_df = out_df.head(int(spec.limit))
                result_count = int(len(out_df))

                results_path = spec.output or str(
                    run_dir / f"{spec.scanner_family}_results.parquet"
                )
                Path(results_path).parent.mkdir(parents=True, exist_ok=True)
                out_df.to_parquet(results_path, index=False)

                # Semantic (DuckDB) tables for Prefect Table artifacts.
                try:
                    from tvscreener_ext.semantic.sidemantic_duckdb import write_semantic_tables

                    results_table_path = str(run_dir / "results_top_rows.json")
                    grade_summary_table_path = str(run_dir / "results_grade_summary.json")
                    write_semantic_tables(
                        results_parquet_path=str(results_path),
                        out_top_rows_json_path=str(results_table_path),
                        out_grade_summary_json_path=str(grade_summary_table_path),
                        top_rows_limit=25,
                    )
                except Exception as exc:
                    results_table_path = None
                    grade_summary_table_path = None
                    if os.getenv("TVSCREENER_SEMANTIC_DEBUG", "0").strip() == "1":
                        errors.append(f"semantic_tables_error: {exc}")

                if bool(spec.matrix):
                    matrix_text = _render_matrix(out_df, spec=spec)
                    (run_dir / "matrix.txt").write_text(matrix_text, encoding="utf-8")
                    matrix_path = str(run_dir / "matrix.txt")

                    matrix_md = _render_matrix_markdown(matrix_text, spec=spec)
                    (run_dir / "matrix.md").write_text(matrix_md, encoding="utf-8")
                    matrix_md_path = str(run_dir / "matrix.md")

                pipeline_mode_executed = (
                    "analytics" if spec.pipeline_mode == "analytics" else "both"
                )

            success = True
        except Exception as exc:
            errors.append(str(exc))
            success = False

        finished = _utc_now()
        run_payload = {
            "spec_version": spec.spec_version,
            "params_hash": params_hash,
            "scanner_family": spec.scanner_family,
            "pipeline_mode_requested": spec.pipeline_mode,
            "pipeline_mode_executed": pipeline_mode_executed,
            "started_at_utc": started.isoformat(),
            "finished_at_utc": finished.isoformat(),
            "success": bool(success),
            "result_count": int(result_count),
            "errors": list(errors),
            "artifacts_dir": str(run_dir),
            "run_spec_path": str(run_dir / "run_spec.json"),
            "run_result_path": str(run_dir / "run_result.json"),
            "results_path": results_path,
            "matrix_path": matrix_path,
            "matrix_md_path": matrix_md_path,
            "results_table_path": results_table_path,
            "grade_summary_table_path": grade_summary_table_path,
        }
        _write_json(run_dir / "run_result.json", run_payload)

        # Best-effort audit table.
        try:
            lh = LakehouseManager(config_path=spec.config_path)
            audit = pd.DataFrame(
                [
                    {
                        "params_hash": params_hash,
                        "asset_type": spec.asset_type,
                        "instrument_type": spec.instrument_type or "",
                        "universe": spec.universe,
                        "pipeline_mode_requested": spec.pipeline_mode,
                        "pipeline_mode_executed": pipeline_mode_executed,
                        "started_at_utc": started.astimezone(UTC).replace(tzinfo=None),
                        "finished_at_utc": finished.astimezone(UTC).replace(tzinfo=None),
                        "success": bool(success),
                        "result_count": int(result_count),
                    }
                ]
            )
            lh.write_table(audit, "tvscreener.runs", mode="append")
        except Exception:
            pass

        return RunResult(
            params_hash=params_hash,
            pipeline_mode_requested=spec.pipeline_mode,
            pipeline_mode_executed=pipeline_mode_executed,
            artifacts_dir=str(run_dir),
            success=bool(success),
            result_count=int(result_count),
            results_path=results_path,
            matrix_path=matrix_path,
            matrix_md_path=matrix_md_path,
            results_table_path=results_table_path,
            grade_summary_table_path=grade_summary_table_path,
            errors=errors,
        )
