from __future__ import annotations

import logging
from typing import Any

import narwhals as nw

logger = logging.getLogger(__name__)


class DataTransformer:
    """Utility for data normalization and renaming logic across screeners."""

    @staticmethod
    @nw.narwhalify
    def rename_technical_columns(df: Any, timeframes: list[str]) -> Any:
        """Rename technical factor columns to a standardized format.

        Handles both 'Recommend All|15' and 'REC_ALL_15' patterns.
        """
        # Build a single mapping dictionary
        rename_map = {}
        for tf in timeframes:
            rename_map.update(
                {
                    f"Recommend All|{tf}": f"TREND_{tf}",
                    f"Recommend Ma|{tf}": f"MA_{tf}",
                    f"Recommend Other|{tf}": f"OSC_{tf}",
                    f"Roc|{tf}": f"ROC_{tf}",
                    f"ATR|{tf}": f"ATR_{tf}",
                    f"RSI|{tf}": f"RSI_{tf}",
                    f"REC_ALL_{tf}": f"TREND_{tf}",
                    f"REC_MA_{tf}": f"MA_{tf}",
                    f"REC_OTHER_{tf}": f"OSC_{tf}",
                    f"ROC_{tf}": f"ROC_{tf}",
                    f"ATR_{tf}": f"ATR_{tf}",
                    f"RSI_{tf}": f"RSI_{tf}",
                }
            )

        # Only rename columns that actually exist in df
        actual_map = {k: v for k, v in rename_map.items() if k in df.columns}
        if actual_map:
            return df.rename(actual_map)
        return df

    @staticmethod
    @nw.narwhalify
    def standardize_stat_columns(df: Any) -> Any:
        """Rename stats columns (RVOL, AVG_VOLUME, ATR, RSI) to a standardized format."""
        rename_map = {}
        for col in df.columns:
            col_upper = str(col).upper()
            if "RELATIVE VOLUME" in col_upper:
                rename_map[col] = "RVOL"
            elif "AVERAGE VOLUME" in col_upper:
                rename_map[col] = "AVG_VOLUME"
            elif col_upper.startswith("ATR|"):
                parts = col_upper.split("|")
                if len(parts) > 1:
                    tf = parts[1]
                    rename_map[col] = f"ATR_{tf}"
            elif col_upper.startswith("RSI|"):
                parts = col_upper.split("|")
                if len(parts) > 1:
                    tf = parts[1]
                    rename_map[col] = f"RSI_{tf}"

        if rename_map:
            return df.rename(rename_map)
        return df

    @staticmethod
    @nw.narwhalify
    def normalize_forex_pairs(
        df: Any, valid_pairs: list[str], exchange_priority: dict[str, int]
    ) -> Any:
        """Normalize Forex symbols and deduplicate based on exchange priority.

        Refactored to use Narwhals for cross-engine compatibility (Pandas, Polars, DuckDB).
        """
        if len(df) == 0:
            return df

        valid_pairs_set = set(valid_pairs)

        # 1. Prepare base columns using expressions
        if "Name" in df.columns:
            name_col = nw.col("Name").fill_null(nw.lit("")).cast(nw.String).str.to_uppercase()
        else:
            name_col = nw.lit("").alias("Name")

        # Handle OANDA:EURUSD, EURUSD.CFD, X_EURUSD etc.
        clean_name = name_col.str.replace(r"^.*:", "", literal=False)
        clean_name = clean_name.str.replace(r"^X_", "", literal=False)

        # 2. Extract potential pairs
        prefix6 = clean_name.str.slice(0, 6)
        prefix7 = clean_name.str.slice(0, 7).str.replace("_", "", n=1)

        # 3. Determine PAIR using when/then logic
        df = df.with_columns(
            PAIR=nw.when(prefix6.is_in(valid_pairs_set))
            .then(prefix6)
            .otherwise(
                nw.when(prefix7.is_in(valid_pairs_set))
                .then(prefix7)
                .otherwise(clean_name.str.slice(0, 6))
            )
        )

        # 4. Exchange scoring and canonical check
        if "Symbol" in df.columns:
            symbol_col = nw.col("Symbol").fill_null("").cast(nw.String)
            exchange = symbol_col.str.replace(r":.*$", "", literal=False)
            exchange = nw.when(symbol_col.str.contains(":")).then(exchange).otherwise(nw.lit(""))
        else:
            exchange = nw.lit("")

        is_canonical = name_col.is_in(valid_pairs_set).cast(nw.Int32)

        # Priority mapping
        exchange_score = nw.lit(999)
        for ex, prio in exchange_priority.items():
            exchange_score = nw.when(exchange == ex).then(prio).otherwise(exchange_score)

        # Volume column for ranking
        volume_cols = ["Average Volume (10 day Calc)", "AVG_VOLUME", "VOLUME"]
        _volume = nw.lit(0)
        for col in volume_cols:
            if col in df.columns:
                _volume = nw.col(col).fill_null(0)
                break

        df = df.with_columns(
            _is_canonical=is_canonical, _exchange_score=exchange_score, _volume=_volume
        )

        # 5. Final ranking and deduplication
        # Higher is_canonical, lower exchange_score, higher volume
        df = df.sort(
            ["_is_canonical", "_exchange_score", "_volume"], descending=[True, False, True]
        )
        df = df.unique(subset=["PAIR"], keep="first")

        # Cleanup internal columns
        df = df.drop(["_is_canonical", "_exchange_score", "_volume"])

        return df
