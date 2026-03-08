from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd


@dataclass(frozen=True, slots=True)
class BinanceCryptoUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n: int = 100
    min_quote_volume_usd: float = 10_000_000
    min_volatility_24h_pct: float = 3.0


def _tv_type_for_instrument(instrument_type: str) -> str:
    it = (instrument_type or "").strip().lower()
    if it == "spot":
        return "spot"
    if it in {"perp", "swap"}:
        return "swap"
    raise ValueError(f"Unsupported crypto instrument_type: {instrument_type}")


def compute_volatility_24h_pct(df: pd.DataFrame):
    # Prefer TradingView's native volatility metric when present.
    # `CryptoField.VOLATILITY` maps to `Volatility.D` and is returned as a percent.
    if "Volatility" in df.columns:
        vol = pd.to_numeric(df["Volatility"], errors="coerce")
        return vol if isinstance(vol, pd.Series) else pd.Series(vol, index=df.index)

    # Fallback: derive a deterministic 24h proxy from TradingView high/low/price.
    n = len(df)
    high = (
        pd.to_numeric(df["High"], errors="coerce")
        if "High" in df.columns
        else pd.Series([pd.NA] * n)
    )
    low = (
        pd.to_numeric(df["Low"], errors="coerce") if "Low" in df.columns else pd.Series([pd.NA] * n)
    )
    price = (
        pd.to_numeric(df["Price"], errors="coerce")
        if "Price" in df.columns
        else pd.Series([pd.NA] * n)
    )
    # Type checkers struggle with pandas' operator overloads.
    import numpy as np

    high_arr = pd.to_numeric(high, errors="coerce").to_numpy(dtype=float)
    low_arr = pd.to_numeric(low, errors="coerce").to_numpy(dtype=float)
    price_arr = pd.to_numeric(price, errors="coerce").to_numpy(dtype=float)
    vol_arr = np.where(price_arr != 0, (high_arr - low_arr) / price_arr * 100.0, np.nan)
    return pd.Series(vol_arr, index=df.index)


def filter_and_rank_candidates(
    df: pd.DataFrame, *, constraints: BinanceCryptoUniverseConstraints
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "Volume 24h in USD" in out.columns:
        out["quote_volume_usd"] = pd.to_numeric(out["Volume 24h in USD"], errors="coerce")
    else:
        out["quote_volume_usd"] = pd.NA
    out["volatility_24h_pct"] = compute_volatility_24h_pct(out)

    out = out.dropna(subset=["Symbol", "quote_volume_usd", "volatility_24h_pct"])
    out = out.loc[out["quote_volume_usd"] >= float(constraints.min_quote_volume_usd)].copy()
    out = out.loc[out["volatility_24h_pct"] >= float(constraints.min_volatility_24h_pct)].copy()

    out = out.sort_values(["quote_volume_usd", "volatility_24h_pct"], ascending=[False, False])  # type: ignore[call-arg]
    out = out.head(int(constraints.top_n))
    out = out.reset_index(drop=True)
    out["rank"] = out.index + 1

    out["instrument_type"] = (constraints.instrument_type or "").strip().lower()
    out["venue"] = "binance"
    return out


def fetch_tradingview_binance_crypto_candidates(
    *, instrument_type: str, max_rows: int = 5000
) -> pd.DataFrame:
    """Fetch candidate rows from TradingView crypto /scan.

    Uses public TradingView /scan via the existing tvscreener library.
    """

    import tvscreener as tvs
    from tvscreener import CryptoField
    from tvscreener.filter import FilterOperator

    tv_type = _tv_type_for_instrument(instrument_type)

    ss = tvs.CryptoScreener()
    ss.set_range(0, int(max_rows))
    ss.sort_by(CryptoField.VOLUME_24H_IN_USD, ascending=False)

    ss.where(CryptoField.EXCHANGE, FilterOperator.EQUAL, "BINANCE")
    ss.where(CryptoField.TYPE, FilterOperator.EQUAL, tv_type)

    ss.select(
        CryptoField.NAME,
        CryptoField.EXCHANGE,
        CryptoField.TYPE,
        CryptoField.SUBTYPE,
        CryptoField.VOLATILITY,
        CryptoField.PRICE,
        CryptoField.HIGH,
        CryptoField.LOW,
        CryptoField.VOLUME_24H_IN_USD,
    )

    df = ss.get()
    if df is None:
        return pd.DataFrame()
    return df


def build_binance_crypto_universe(
    *, constraints: BinanceCryptoUniverseConstraints
) -> tuple[list[str], dict]:
    candidates = fetch_tradingview_binance_crypto_candidates(
        instrument_type=constraints.instrument_type
    )
    ranked = filter_and_rank_candidates(candidates, constraints=constraints)

    tickers = ranked["Symbol"].astype(str).tolist() if not ranked.empty else []
    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "instrument_type": constraints.instrument_type,
            "top_n": constraints.top_n,
            "min_quote_volume_usd": constraints.min_quote_volume_usd,
            "min_volatility_24h_pct": constraints.min_volatility_24h_pct,
        },
        "count": len(tickers),
        "rows": (
            [
                {
                    "rank": int(row.get("rank")),
                    "ticker": str(row.get("Symbol")),
                    "Name": row.get("Name"),
                    "Type": row.get("Type"),
                    "Subtype": row.get("Subtype"),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                }
                for row in cast(list[dict[str, Any]], ranked.to_dict(orient="records"))
            ]
            if not ranked.empty
            else []
        ),
    }
    return tickers, snapshot


def maybe_write_universe_json(snapshot: dict, *, run_dir: str | None) -> str | None:
    if not run_dir:
        return None
    path = Path(run_dir) / "universe.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
