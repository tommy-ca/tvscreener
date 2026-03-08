from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

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


def compute_volatility_24h_pct(df: pd.DataFrame) -> pd.Series:
    # TradingView crypto /scan returns High/Low/Price columns that correspond to the 24h window.
    high = pd.to_numeric(df.get("High"), errors="coerce")
    low = pd.to_numeric(df.get("Low"), errors="coerce")
    price = pd.to_numeric(df.get("Price"), errors="coerce")
    return (high - low) / price * 100.0


def filter_and_rank_candidates(
    df: pd.DataFrame, *, constraints: BinanceCryptoUniverseConstraints
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    out["quote_volume_usd"] = pd.to_numeric(out.get("Volume 24h in USD"), errors="coerce")
    out["volatility_24h_pct"] = compute_volatility_24h_pct(out)

    out = out.dropna(subset=["Symbol", "quote_volume_usd", "volatility_24h_pct"])
    out = out[out["quote_volume_usd"] >= float(constraints.min_quote_volume_usd)]
    out = out[out["volatility_24h_pct"] >= float(constraints.min_volatility_24h_pct)]

    out = out.sort_values(["quote_volume_usd", "volatility_24h_pct"], ascending=[False, False])
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
            ranked[
                [
                    "rank",
                    "Symbol",
                    "Name",
                    "Type",
                    "Subtype",
                    "quote_volume_usd",
                    "volatility_24h_pct",
                ]
            ]
            .rename(columns={"Symbol": "ticker"})
            .to_dict(orient="records")
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
