from __future__ import annotations

from dataclasses import dataclass

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
        """Calculate weighted factor scores across timeframes.

        Args:
            df: DataFrame with timeframe columns matching col_pattern
            factor_name: Name for the output score column (e.g., "TREND")
            col_pattern: Column pattern to match (e.g., "Recommend All|")
            copy: If True, copy DataFrame to avoid mutation (default True)

        Returns:
            DataFrame with added factor score column
        """
        if copy:
            df = df.copy()

        cols = [c for c in df.columns if col_pattern in c]
        if cols:
            weights = np.array([self.tf_weights.get(c.split("|")[-1], 0.33) for c in cols])
            weight_sum = weights.sum()
            if weight_sum == 0:
                df[f"{factor_name}_SCORE"] = 0.0
            else:
                values = df[cols].fillna(0).values
                df[f"{factor_name}_SCORE"] = (values * weights).sum(axis=1) / weight_sum
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
        """Calculate confluence using a TF × Factor grid.

        Each cell in the grid (e.g. TREND_240, MA_60, OSC_15) gets one vote.
        A cell is "aligned" if its value agrees with the overall DIRECTION:
          - LONG direction: value > 0 = aligned
          - SHORT direction: value < 0 = aligned

        With 3 TFs × 4 factors = 12 cells, confluence is expressed as
        aligned/total (e.g. 10/12 = 83%).

        Supplementary TF_CONFLUENCE and FACTOR_CONFLUENCE columns are also
        produced for per-axis visibility.
        """
        if copy:
            df = df.copy()

        # --- Ensure DIRECTION exists ---
        if "DIRECTION" not in df.columns:
            if "ENSEMBLE_SCORE" in df.columns:
                ensemble = df["ENSEMBLE_SCORE"].fillna(0)
                df["DIRECTION"] = np.where(
                    ensemble > 0, Direction.LONG.value, Direction.SHORT.value
                )
            else:
                # Fallback: infer from raw data
                tf_cols = [
                    f"Recommend All|{tf}"
                    for tf in self.timeframes
                    if f"Recommend All|{tf}" in df.columns
                ]
                if tf_cols:
                    net = df[tf_cols].fillna(0).sum(axis=1)
                    df["DIRECTION"] = np.where(net > 0, Direction.LONG.value, Direction.SHORT.value)
                else:
                    df["DIRECTION"] = Direction.LONG.value

        is_long = df["DIRECTION"] == Direction.LONG.value

        # --- Grid confluence: TF × Factor cell voting (Vectorized) ---
        factor_col_map = {
            "TREND": "Recommend All|",
            "MA": "Recommend Ma|",
            "OSC": "Recommend Other|",
            "ROC": "Roc|",
        }

        # Identify all relevant grid columns that exist in DF
        relevant_cols = []
        for tf in self.timeframes:
            # Per-TF direction labels (supplementary)
            tf_dir_col = f"Recommend All|{tf}"
            if tf_dir_col in df.columns:
                df[f"TF_{tf}_DIR"] = self.calculate_direction(df[tf_dir_col])

            for col_prefix in factor_col_map.values():
                col = f"{col_prefix}{tf}"
                if col in df.columns:
                    relevant_cols.append(col)

        # Factor direction labels (supplementary)
        for factor in ["TREND", "MA", "OSC", "ROC"]:
            col = f"{factor}_SCORE"
            if col in df.columns:
                df[f"{factor}_DIR"] = self.calculate_direction(df[col])

        if relevant_cols:
            # Fast vectorized calculation across all grid cells at once
            vals = df[relevant_cols].fillna(0).values
            # Broadcast direction across columns
            is_long_v = is_long.values[:, np.newaxis]
            # Alignment: (LONG & val > 0) | (SHORT & val < 0)
            cell_aligned = np.where(is_long_v, vals > 0, vals < 0)

            grid_aligned = cell_aligned.sum(axis=1)
            grid_total = len(relevant_cols)
        else:
            grid_aligned = np.zeros(len(df), dtype=int)
            grid_total = 0

        df["GRID_ALIGNED"] = grid_aligned
        df["GRID_TOTAL"] = grid_total
        df["GRID_PCT"] = (
            (grid_aligned / grid_total * 100).round(0).astype(int) if grid_total > 0 else 0
        )
        df["TOTAL_CONFLUENCE"] = grid_aligned

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
            f"Recommend All|{tf}" for tf in self.timeframes if f"Recommend All|{tf}" in df.columns
        ]
        if tf_cols:
            tf_values = df[tf_cols].fillna(0).values
            df["TF_CONFLUENCE_LONG"] = (tf_values > 0).sum(axis=1)
            df["TF_CONFLUENCE_SHORT"] = (tf_values < 0).sum(axis=1)
        else:
            df["TF_CONFLUENCE_LONG"] = 0
            df["TF_CONFLUENCE_SHORT"] = 0

        # --- Supplementary Factor confluence (aggregated scores) ---
        factor_dir_cols = [
            f"{factor}_DIR"
            for factor in ["TREND", "MA", "OSC", "ROC"]
            if f"{factor}_DIR" in df.columns
        ]
        if factor_dir_cols:
            # Use .values for faster summation
            bullish_val = Direction.BULLISH.value
            bearish_val = Direction.BEARISH.value
            f_vals = df[factor_dir_cols].values
            df["FACTOR_BULLISH_COUNT"] = (f_vals == bullish_val).sum(axis=1)
            df["FACTOR_BEARISH_COUNT"] = (f_vals == bearish_val).sum(axis=1)
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

    def rank_opportunities(self, df: pd.DataFrame) -> pd.DataFrame:
        """Full ranking pipeline: scores, ensemble, confluence, sorting.

        Args:
            df: DataFrame with raw opportunity data

        Returns:
            DataFrame with all scoring columns, sorted by ensemble score
        """
        if df.empty:
            return df

        df = df.copy()

        df = self.calculate_factor_scores(df, "TREND", "Recommend All|", copy=False)
        df = self.calculate_factor_scores(df, "MA", "Recommend Ma|", copy=False)
        df = self.calculate_factor_scores(df, "OSC", "Recommend Other|", copy=False)

        df = self.calculate_roc_score(df, copy=False)

        df = self.calculate_ensemble_score(df, copy=False)

        df = self.calculate_confluence(df, copy=False)

        df["RATING_SCORE"] = df.get("ENSEMBLE_SCORE", 0.0)
        df["ROC_AVG"] = df.get("ROC_SCORE", 0.0)

        df = df.sort_values(by=["ENSEMBLE_SCORE"], ascending=[False])

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
