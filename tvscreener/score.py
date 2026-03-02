from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from tvscreener.core.enums import Direction


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Configuration for scoring weights."""

    trend_weight: float = 0.4
    ma_weight: float = 0.3
    osc_weight: float = 0.2
    roc_weight: float = 0.1


DEFAULT_SCORING_CONFIG = ScoringConfig()


class ScoringEngine:
    """Memory-efficient scoring engine for opportunity screening.

    Provides public methods for calculating factor scores, ensemble scores,
    confluence levels, and trade directions.
    """

    __slots__ = ("config", "timeframes", "tf_weights")

    def __init__(
        self,
        config: ScoringConfig | None = None,
        timeframes: list[str] | None = None,
        tf_weights: dict[str, float] | None = None,
    ):
        self.config = config or DEFAULT_SCORING_CONFIG
        self.timeframes = timeframes or []
        self.tf_weights = tf_weights or {}

    def calculate_factor_scores(
        self,
        df: pd.DataFrame,
        factor_name: str,
        col_pattern: str,
        copy: bool = True,
    ) -> pd.DataFrame:
        """Calculate weighted factor scores across timeframes."""
        if copy:
            df = df.copy()

        # Map canonical names to their raw counterparts for weight lookup
        # e.g. TREND_240 -> 240
        prefix_map = {"TREND": "TREND_", "MA": "MA_", "OSC": "OSC_"}
        canonical_prefix = prefix_map.get(factor_name, "UNKNOWN_")

        # Find columns using both raw pattern and canonical prefix
        cols = [c for c in df.columns if col_pattern in c or c.startswith(canonical_prefix)]
        if cols:
            # Extract timeframe from column name (handle both 'Recommend All|240' and 'TREND_240')
            def extract_tf(c):
                if "|" in c:
                    return c.split("|")[-1]
                return c.split("_")[-1]

            weights = np.array([self.tf_weights.get(extract_tf(c), 0.33) for c in cols])
            weight_sum = weights.sum()

            if weight_sum == 0:
                df[f"{factor_name}_SCORE"] = 0.0
            else:
                # Performance: Use native pandas dot product to stay in Arrow/Vectorized domain
                # instead of dropping to .values (NumPy)
                df[f"{factor_name}_SCORE"] = (df[cols].fillna(0) @ weights) / weight_sum
        else:
            df[f"{factor_name}_SCORE"] = 0.0

        return df

    def calculate_roc_score(self, df: pd.DataFrame, copy: bool = True) -> pd.DataFrame:
        """Calculate momentum (ROC) score across timeframes.

        Args:
            df: DataFrame with ROC columns
            copy: If True, copy DataFrame to avoid mutation

        Returns:
            DataFrame with added ROC_SCORE column
        """
        if copy:
            df = df.copy()

        roc_cols = [f"Roc|{tf}" for tf in self.timeframes if f"Roc|{tf}" in df.columns]
        if roc_cols:
            df["ROC_SCORE"] = df[roc_cols].mean(axis=1)
        else:
            df["ROC_SCORE"] = 0.0

        return df

    def calculate_ensemble_score(self, df: pd.DataFrame, copy: bool = True) -> pd.DataFrame:
        """Combine all factor scores into ensemble score using weights.

        Args:
            df: DataFrame with factor score columns
            copy: If True, copy DataFrame to avoid mutation

        Returns:
            DataFrame with added ENSEMBLE_SCORE and DIRECTION columns
        """
        if copy:
            df = df.copy()

        cfg = self.config
        df["ENSEMBLE_SCORE"] = (
            df["TREND_SCORE"].fillna(0) * cfg.trend_weight
            + df["MA_SCORE"].fillna(0) * cfg.ma_weight
            + df["OSC_SCORE"].fillna(0) * cfg.osc_weight
            + df["ROC_SCORE"].fillna(0) * cfg.roc_weight
        )

        df["DIRECTION"] = np.where(
            df["ENSEMBLE_SCORE"] > 0, Direction.LONG.value, Direction.SHORT.value
        )

        return df

    def calculate_confluence(self, df: pd.DataFrame, copy: bool = True) -> pd.DataFrame:
        """Calculate confluence using a TF × Factor grid."""
        if copy:
            df = df.copy()

        # Ensure DIRECTION exists
        if "DIRECTION" not in df.columns:
            # Infer direction from first available trend column if ensemble score is missing
            ensemble_val = df.get("ENSEMBLE_SCORE")
            ensemble: Any = ensemble_val

            if ensemble is None:
                trend_cols = [
                    c for c in df.columns if "Recommend All|" in c or c.startswith("TREND_")
                ]
                ensemble = df[trend_cols[0]] if trend_cols else pd.Series(0.0, index=df.index)

            df["DIRECTION"] = np.where(ensemble > 0, Direction.LONG.value, Direction.SHORT.value)

        is_long = df["DIRECTION"] == Direction.LONG.value

        # Identify all relevant grid columns that exist in DF
        # Support both raw and canonical names
        relevant_cols = []
        for tf in self.timeframes:
            for factor in ["TREND", "MA", "OSC", "ROC"]:
                raw_col = {
                    "TREND": "Recommend All|",
                    "MA": "Recommend Ma|",
                    "OSC": "Recommend Other|",
                    "ROC": "Roc|",
                }[factor] + tf
                canonical_col = f"{factor}_{tf}"

                if canonical_col in df.columns:
                    relevant_cols.append(canonical_col)
                elif raw_col in df.columns:
                    relevant_cols.append(raw_col)

        if relevant_cols:
            # Performance: Stay in vectorized domain
            # We want: (LONG & val > 0) | (SHORT & val < 0)
            # Use boolean logic on the whole dataframe slice
            grid_slice = df[relevant_cols].fillna(0)

            if is_long.any() or (~is_long).any():
                # (LONG & val > 0) | (SHORT & val < 0)
                # Performance: Stay in vectorized domain without dropping to .values
                long_aligned = grid_slice.gt(0).where(is_long, False)
                short_aligned = grid_slice.lt(0).where(~is_long, False)

                grid_aligned = (long_aligned | short_aligned).sum(axis=1)
            else:
                grid_aligned = np.zeros(len(df), dtype=int)

            grid_total = len(relevant_cols)
        else:
            grid_aligned = pd.Series(0, index=df.index)
            grid_total = 0

        df["GRID_ALIGNED"] = grid_aligned.astype(int)
        df["GRID_TOTAL"] = grid_total
        df["GRID_PCT"] = (
            (grid_aligned / grid_total * 100).round(0).astype(int) if grid_total > 0 else 0
        )
        df["TOTAL_CONFLUENCE"] = grid_aligned.astype(int)

        df["CONFLUENCE_LEVEL"] = np.select(
            [
                df["GRID_PCT"] >= 83,
                df["GRID_PCT"] >= 58,
                df["GRID_PCT"] >= 25,
            ],
            ["strong", "medium", "weak"],
            default="none",
        )

        # --- Supplementary TF confluence (Recommend All only, per-TF) ---
        tf_cols = [
            f"TREND_{tf}" if f"TREND_{tf}" in df.columns else f"Recommend All|{tf}"
            for tf in self.timeframes
            if f"TREND_{tf}" in df.columns or f"Recommend All|{tf}" in df.columns
        ]
        if tf_cols:
            tf_values = df[tf_cols].fillna(0)
            df["TF_CONFLUENCE_LONG"] = (tf_values > 0).sum(axis=1)
            df["TF_CONFLUENCE_SHORT"] = (tf_values < 0).sum(axis=1)
        else:
            df["TF_CONFLUENCE_LONG"] = 0
            df["TF_CONFLUENCE_SHORT"] = 0

        # --- Supplementary Factor confluence (aggregated scores) ---
        for factor in ["TREND", "MA", "OSC", "ROC"]:
            col = f"{factor}_SCORE"
            if col in df.columns:
                df[f"{factor}_DIR"] = self.calculate_direction(df[col])

        factor_dir_cols = [
            f"{f}_DIR" for f in ["TREND", "MA", "OSC", "ROC"] if f"{f}_DIR" in df.columns
        ]
        if factor_dir_cols:
            bullish_val = Direction.BULLISH.value
            bearish_val = Direction.BEARISH.value
            df["FACTOR_BULLISH_COUNT"] = (df[factor_dir_cols] == bullish_val).sum(axis=1)
            df["FACTOR_BEARISH_COUNT"] = (df[factor_dir_cols] == bearish_val).sum(axis=1)
        else:
            df["FACTOR_BULLISH_COUNT"] = 0
            df["FACTOR_BEARISH_COUNT"] = 0

        return df

    def calculate_direction(self, series: pd.Series) -> pd.Series:
        """Calculate direction (bullish/bearish/neutral) from values.

        Args:
            series: Series of numeric values

        Returns:
            Series with direction labels
        """
        # Use .value to get plain strings — passing Direction enums directly
        # to np.where causes truncation on Python 3.11+ because str(Enum)
        # returns "Direction.BULLISH" instead of "bullish", and numpy's
        # fixed-width U7 dtype truncates it to "Directi".
        return pd.Series(
            np.where(
                series > 0,
                Direction.BULLISH.value,
                np.where(series < 0, Direction.BEARISH.value, Direction.NEUTRAL.value),
            ),
            index=series.index,
        )

    def rank_opportunities(self, df: pd.DataFrame, copy: bool = True) -> pd.DataFrame:
        """Full ranking pipeline: scores, ensemble, confluence, sorting.

        Args:
            df: DataFrame with raw opportunity data
            copy: If True, copy DataFrame to avoid mutation

        Returns:
            DataFrame with all scoring columns, sorted by ensemble score
        """
        if df.empty:
            return df

        if copy:
            df = df.copy()

        df = self.calculate_factor_scores(df, "TREND", "Recommend All|", copy=False)
        df = self.calculate_factor_scores(df, "MA", "Recommend Ma|", copy=False)
        df = self.calculate_factor_scores(df, "OSC", "Recommend Other|", copy=False)

        df = self.calculate_roc_score(df, copy=False)

        df = self.calculate_ensemble_score(df, copy=False)

        df = self.calculate_confluence(df, copy=False)

        df["RATING_SCORE"] = df.get("ENSEMBLE_SCORE", 0.0)
        df["ROC_AVG"] = df.get("ROC_SCORE", 0.0)

        df.sort_values(by=["ENSEMBLE_SCORE"], ascending=[False], inplace=True)

        df = calculate_grades(df, copy=False)

        return df


def calculate_grades(df: pd.DataFrame, copy: bool = True) -> pd.DataFrame:
    """Calculate confluence grade based on grid confluence percentage.

    Uses the grid-based TF × Factor confluence (GRID_PCT) which is
    direction-neutral and works correctly for both LONG and SHORT signals.

    Grade thresholds:
        A+ ≥ 83%  (≥10/12)
        A  ≥ 67%  (≥8/12)
        B  ≥ 58%  (≥7/12)
        C  ≥ 42%  (≥5/12)
        D  ≥ 25%  (≥3/12)
        F  < 25%

    Args:
        df: DataFrame with GRID_PCT and supplementary confluence columns
        copy: If True, copy DataFrame to avoid mutation

    Returns:
        DataFrame with GRADE, TF_CONFLUENCE, and FACTOR_CONFLUENCE columns
    """
    if copy:
        df = df.copy()

    grid_pct = df["GRID_PCT"] if "GRID_PCT" in df.columns else pd.Series(0, index=df.index)
    grid_pct = pd.to_numeric(grid_pct, errors="coerce").fillna(0)

    df["GRADE"] = np.select(
        [
            grid_pct >= 83,
            grid_pct >= 67,
            grid_pct >= 58,
            grid_pct >= 42,
            grid_pct >= 25,
        ],
        ["A+", "A", "B", "C", "D"],
        default="F",
    )

    # Supplementary display columns (direction-aware)
    direction = (
        df["DIRECTION"]
        if "DIRECTION" in df.columns
        else pd.Series(Direction.LONG.value, index=df.index)
    )
    is_long = direction == Direction.LONG.value

    tf_long = (
        df["TF_CONFLUENCE_LONG"].fillna(0).astype(int)
        if "TF_CONFLUENCE_LONG" in df.columns
        else pd.Series(0, index=df.index)
    )
    tf_short = (
        df["TF_CONFLUENCE_SHORT"].fillna(0).astype(int)
        if "TF_CONFLUENCE_SHORT" in df.columns
        else pd.Series(0, index=df.index)
    )

    tf_max = max(len(df.attrs.get("timeframes", ["15", "60", "240"])), 3)
    tf_aligned = np.where(is_long, tf_long, tf_short)
    df["TF_CONFLUENCE"] = pd.Series(tf_aligned, index=df.index).astype(str) + f"/{tf_max}"

    factor_bull = (
        df["FACTOR_BULLISH_COUNT"].fillna(0).astype(int)
        if "FACTOR_BULLISH_COUNT" in df.columns
        else pd.Series(0, index=df.index)
    )
    factor_bear = (
        df["FACTOR_BEARISH_COUNT"].fillna(0).astype(int)
        if "FACTOR_BEARISH_COUNT" in df.columns
        else pd.Series(0, index=df.index)
    )
    factor_aligned = np.where(is_long, factor_bull, factor_bear)
    df["FACTOR_CONFLUENCE"] = pd.Series(factor_aligned, index=df.index).astype(str) + "/4"

    return df
