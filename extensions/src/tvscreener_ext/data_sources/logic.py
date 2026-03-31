from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd


class DataSourceAdapter(Protocol):
    source: str

    def fetch_batch(self, *, screener: Any, tickers: list[str]) -> pd.DataFrame: ...


def _event_id(source: str, tickers: list[str]) -> str:
    raw = f"{source}:{','.join(tickers)}".encode()
    return hashlib.blake2s(raw, digest_size=8).hexdigest()


@dataclass(frozen=True, slots=True)
class TradingViewDataSource:
    source: str = "tradingview"

    def fetch_batch(self, *, screener: Any, tickers: list[str]) -> pd.DataFrame:
        if hasattr(screener, "set_tickers"):
            screener.set_tickers(*tickers)
        elif hasattr(screener, "set_symbols"):
            screener.set_symbols(*tickers)
        else:
            # Fallback for v0.2.1 style if no helper exists
            screener.symbols = {"symbolset": tickers}

        df = screener.get()
        if df is None:
            return pd.DataFrame()
        if df.empty:
            return df

        if "source" not in df.columns:
            df["source"] = self.source
        if "source_event_id" not in df.columns:
            df["source_event_id"] = _event_id(self.source, tickers)
        return df


@dataclass(frozen=True, slots=True)
class StubDataSource:
    source: str = "stub"

    def fetch_batch(self, *, screener: Any, tickers: list[str]) -> pd.DataFrame:
        rows = [
            {
                "Symbol": ticker,
                "Name": ticker,
                "PRICE": 1.0,
                "source": self.source,
                "source_event_id": _event_id(self.source, [ticker]),
            }
            for ticker in tickers
        ]
        return pd.DataFrame(rows)


def build_data_source(name: str | None) -> DataSourceAdapter:
    normalized = (name or "tradingview").strip().lower()
    if normalized in {"tradingview", "tv"}:
        return TradingViewDataSource()
    if normalized in {"stub", "mock"}:
        return StubDataSource()
    raise ValueError(f"Unknown data source adapter: {name}")
