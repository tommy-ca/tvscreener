from __future__ import annotations

from collections.abc import Sequence

import narwhals as nw
from narwhals.typing import FrameT


@nw.narwhalify
def apply_volume_filter(df: FrameT, min_volume: float | None) -> FrameT:
    if min_volume is None:
        return df

    # Support both raw and canonical names
    candidates = ["Average Volume (10 day Calc)", "AVG_VOLUME", "volume"]
    for col in candidates:
        if col in df.columns:
            return df.filter(nw.col(col) >= min_volume)
    return df


@nw.narwhalify
def apply_atr_filter(df: FrameT, max_atr: float | None) -> FrameT:
    if max_atr is None:
        return df

    # Support both raw "ATR|{tf}" and canonical "ATR_{tf}"
    atr_cols = [c for c in df.columns if c.startswith("ATR|") or c.startswith("ATR_") or c == "ATR"]
    if not atr_cols:
        return df

    return df.filter(nw.mean_horizontal(*atr_cols) <= max_atr)


@nw.narwhalify
def apply_ma_score_filter(df: FrameT, min_ma_score: float | None) -> FrameT:
    if min_ma_score is None:
        return df

    # Support both raw "Recommend Ma|{tf}" and canonical "MA_{tf}"
    ma_cols = [c for c in df.columns if c.startswith("Recommend Ma|") or c.startswith("MA_")]
    if not ma_cols:
        return df

    return df.filter(nw.mean_horizontal(*(nw.col(c).fill_null(0) for c in ma_cols)) >= min_ma_score)


@nw.narwhalify
def apply_contract_type_filter(df: FrameT, contract_type: str) -> FrameT:
    """Filter DataFrame by contract type (spot, cfd, spreadbet).

    Note: Many forex brokers (OANDA, FXOPEN, FOREXCOM) return an empty string
    for their subtype even though they are CFD instruments.  When filtering for
    CFDs we therefore accept both ``"cfd"`` and ``""`` (empty).  Explicit
    non-CFD subtypes such as ``"synthetic"`` and ``"spreadbet"`` are excluded.
    """
    if contract_type == "all":
        return df

    subtype_col = "Subtype"
    if subtype_col in df.columns:
        subtype = nw.col(subtype_col).fill_null("")
        if contract_type == "cfd":
            # Accept explicit "cfd" and empty (brokers that don't tag subtype)
            return df.filter(subtype.is_in(["cfd", ""]))
        elif contract_type == "spot":
            return df.filter(subtype.is_in(["", "spot"]))
        elif contract_type == "spreadbet":
            return df.filter(subtype == "spreadbet")

    return df


@nw.narwhalify
def enrich_screener_data(df: FrameT, timeframes: Sequence[str]) -> FrameT:
    """Enrich DataFrame with human-readable factor names."""
    # Ensure PAIR is at the front
    cols = list(df.columns)
    if "PAIR" in cols:
        cols.remove("PAIR")
        df = df.select("PAIR", *cols)

    # Rename technical columns to human-readable factor context
    rename_map = {}
    for tf in timeframes:
        target_trend = f"TREND_{tf}"
        target_ma = f"MA_{tf}"
        target_osc = f"OSC_{tf}"
        target_roc = f"ROC_{tf}"

        if f"Recommend All|{tf}" in df.columns and target_trend not in df.columns:
            rename_map[f"Recommend All|{tf}"] = target_trend
        if f"Recommend Ma|{tf}" in df.columns and target_ma not in df.columns:
            rename_map[f"Recommend Ma|{tf}"] = target_ma
        if f"Recommend Other|{tf}" in df.columns and target_osc not in df.columns:
            rename_map[f"Recommend Other|{tf}"] = target_osc
        if f"Roc|{tf}" in df.columns and target_roc not in df.columns:
            rename_map[f"Roc|{tf}"] = target_roc

        if f"Atr|{tf}" in df.columns and f"ATR_{tf}" not in df.columns:
            rename_map[f"Atr|{tf}"] = f"ATR_{tf}"
        if f"Rsi|{tf}" in df.columns and f"RSI_{tf}" not in df.columns:
            rename_map[f"Rsi|{tf}"] = f"RSI_{tf}"

    if rename_map:
        return df.rename(rename_map)

    return df


@nw.narwhalify
def detect_mean_reversion_signals(
    df: FrameT,
    signals: Sequence[str],
    rsi_lower: float = 30.0,
    rsi_upper: float = 70.0,
) -> FrameT:
    if not signals:
        return df

    rsi_cols = [c for c in df.columns if c.startswith("RSI")]
    if not rsi_cols:
        return df

    exprs = []

    if "rsi_oversold" in signals:
        exprs.append(
            nw.any_horizontal(
                *(nw.col(c).fill_null(50) < rsi_lower for c in rsi_cols),
                ignore_nulls=True,
            )
            .cast(nw.Int64)
            .alias("rsi_oversold")
        )

    if "rsi_overbought" in signals:
        exprs.append(
            nw.any_horizontal(
                *(nw.col(c).fill_null(50) > rsi_upper for c in rsi_cols),
                ignore_nulls=True,
            )
            .cast(nw.Int64)
            .alias("rsi_overbought")
        )

    if exprs:
        return df.with_columns(*exprs)

    return df
