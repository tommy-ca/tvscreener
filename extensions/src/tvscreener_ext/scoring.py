from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass

import narwhals as nw
import numpy as np
import pandas as pd

from tvscreener_ext.enums import Direction


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Configuration for scoring weights."""

    trend_weight: float = 0.4
    ma_weight: float = 0.3
    osc_weight: float = 0.2
    roc_weight: float = 0.1
    volatility_weight: float = 0.0  # Optional volatility scaling
    min_volatility_threshold: float = 0.0  # Minimum ATR/RVOL for full score


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
        copy: bool = False,
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
                # Use Narwhals for zero-copy scoring across backends
                nw_df = nw.from_native(cast(Any, df[cols]))
                expr = (
                    sum(nw.col(c).fill_null(0) * w for c, w in zip(cols, weights, strict=False))
                    / weight_sum
                )
                df[f"{factor_name}_SCORE"] = nw.to_native(nw_df.select(expr.alias("score")))[
                    "score"
                ]
        else:
            df[f"{factor_name}_SCORE"] = 0.0

        return df

    def calculate_roc_score(self, df: pd.DataFrame, copy: bool = False) -> pd.DataFrame:
        """Calculate momentum (ROC) score across timeframes.

        Args:
            df: DataFrame with ROC columns
            copy: If True, copy DataFrame to avoid mutation

        Returns:
            DataFrame with added ROC_SCORE column
        """
        if copy:
            df = df.copy()

        roc_cols = []
        for tf in self.timeframes:
            canonical = f"ROC_{tf}"
            raw = f"Roc|{tf}"
            if canonical in df.columns:
                roc_cols.append(canonical)
            elif raw in df.columns:
                roc_cols.append(raw)
        if roc_cols:
            df["ROC_SCORE"] = df[roc_cols].mean(axis=1)
        else:
            df["ROC_SCORE"] = 0.0

        return df

    def calculate_volatility_score(self, df: pd.DataFrame, copy: bool = False) -> pd.DataFrame:
        """Calculate volatility factor score across timeframes.

        Args:
            df: DataFrame with ATR or RVOL columns
            copy: If True, copy DataFrame to avoid mutation

        Returns:
            DataFrame with added VOLATILITY_SCORE column (normalized 0.0 to 1.0)
        """
        if copy:
            df = df.copy()

        # Look for relative volume (RVOL) or ATR %
        rvol_cols = [c for c in df.columns if "RELATIVE_VOLUME" in c or "RVOL" in c]
        if rvol_cols:
            # Average RVOL, capped at 2.0 (high) and normalized
            avg_rvol = df[rvol_cols].mean(axis=1).fillna(1.0)
            df["VOLATILITY_SCORE"] = (avg_rvol / 2.0).clip(0.0, 1.0)
        else:
            df["VOLATILITY_SCORE"] = 1.0  # Default to neutral if not available

        return df

    def calculate_ensemble_score(self, df: pd.DataFrame, copy: bool = False) -> pd.DataFrame:
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

        # Apply volatility scaling if configured
        if cfg.volatility_weight > 0 and "VOLATILITY_SCORE" in df.columns:
            # Scale the core ensemble score by volatility factor
            # Higher volatility (within range) = higher ensemble score
            scale_factor = df["VOLATILITY_SCORE"].fillna(1.0)
            df["ENSEMBLE_SCORE"] = df["ENSEMBLE_SCORE"] * (
                (1.0 - cfg.volatility_weight) + (cfg.volatility_weight * scale_factor)
            )

        df["DIRECTION"] = (
            nw.from_native(df)
            .select(
                nw.when(nw.col("ENSEMBLE_SCORE") > 0)
                .then(nw.lit(Direction.LONG.value))
                .otherwise(nw.lit(Direction.SHORT.value))
                .alias("DIRECTION")
            )
            .to_native()["DIRECTION"]
        )

        return df

    def calculate_confluence(self, df: pd.DataFrame, copy: bool = False) -> pd.DataFrame:
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

            df["DIRECTION"] = (
                nw.from_native(df.assign(ensemble=ensemble))
                .select(
                    nw.when(nw.col("ensemble") > 0)
                    .then(nw.lit(Direction.LONG.value))
                    .otherwise(nw.lit(Direction.SHORT.value))
                    .alias("DIRECTION")
                )
                .to_native()["DIRECTION"]
            )

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

                grid_aligned = (cast(Any, long_aligned) | cast(Any, short_aligned)).sum(axis=1)
            else:
                grid_aligned = pd.Series(0, index=df.index, dtype=int)

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

        df["CONFLUENCE_LEVEL"] = (
            nw.from_native(df)
            .select(
                nw.when(nw.col("GRID_PCT") >= 83)
                .then(nw.lit("strong"))
                .otherwise(
                    nw.when(nw.col("GRID_PCT") >= 58)
                    .then(nw.lit("medium"))
                    .otherwise(
                        nw.when(nw.col("GRID_PCT") >= 25)
                        .then(nw.lit("weak"))
                        .otherwise(nw.lit("none"))
                    )
                )
                .alias("CONFLUENCE_LEVEL")
            )
            .to_native()["CONFLUENCE_LEVEL"]
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
                df[f"{factor}_DIR"] = self.calculate_direction(cast(pd.Series, df[col]))

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
        # Ensure series has a name for Narwhals
        name = str(series.name) if series.name else "val"
        return cast(
            pd.Series,
            nw.from_native(series.to_frame(name=name))
            .select(
                nw.when(nw.col(name) > 0)
                .then(nw.lit(Direction.BULLISH.value))
                .otherwise(
                    nw.when(nw.col(name) < 0)
                    .then(nw.lit(Direction.BEARISH.value))
                    .otherwise(nw.lit(Direction.NEUTRAL.value))
                )
                .alias(name)
            )
            .to_native()[name],
        )

    def rank_opportunities(self, df: pd.DataFrame, copy: bool = False) -> pd.DataFrame:
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
        df = self.calculate_volatility_score(df, copy=False)

        df = self.calculate_ensemble_score(df, copy=False)

        df = self.calculate_confluence(df, copy=False)

        df["RATING_SCORE"] = df.get("ENSEMBLE_SCORE", 0.0)
        df["ROC_AVG"] = df.get("ROC_SCORE", 0.0)

        df.sort_values(by=["ENSEMBLE_SCORE"], ascending=[False], inplace=True)

        df = calculate_grades(df, copy=False, config=self.config)

        return df


def calculate_grades(
    df: pd.DataFrame, copy: bool = False, config: ScoringConfig | None = None
) -> pd.DataFrame:
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

    Low volatility penalties:
        If RVOL < 1.0 (or custom threshold), drop one grade level (e.g. A -> B).

    Args:
        df: DataFrame with GRID_PCT and supplementary confluence columns
        copy: If True, copy DataFrame to avoid mutation
        config: Optional scoring configuration for volatility penalties

    Returns:
        DataFrame with GRADE, TF_CONFLUENCE, and FACTOR_CONFLUENCE columns
    """
    if copy:
        df = df.copy()

    grid_pct = df["GRID_PCT"] if "GRID_PCT" in df.columns else pd.Series(0, index=df.index)
    grid_pct = cast(pd.Series, pd.to_numeric(grid_pct, errors="coerce")).fillna(0)

    # Initial Grade assignment
    df["GRADE"] = (
        nw.from_native(df.assign(grid_pct_val=grid_pct))
        .select(
            nw.when(nw.col("grid_pct_val") >= 83)
            .then(nw.lit("A+"))
            .otherwise(
                nw.when(nw.col("grid_pct_val") >= 67)
                .then(nw.lit("A"))
                .otherwise(
                    nw.when(nw.col("grid_pct_val") >= 58)
                    .then(nw.lit("B"))
                    .otherwise(
                        nw.when(nw.col("grid_pct_val") >= 42)
                        .then(nw.lit("C"))
                        .otherwise(
                            nw.when(nw.col("grid_pct_val") >= 25)
                            .then(nw.lit("D"))
                            .otherwise(nw.lit("F"))
                        )
                    )
                )
            )
            .alias("GRADE")
        )
        .to_native()["GRADE"]
    )

    # Apply Volatility Penalty
    if config is not None and (thr := config.min_volatility_threshold) > 0:
        vol_score = df.get("VOLATILITY_SCORE", pd.Series(1.0, index=df.index))
        low_vol = vol_score < (thr / 2.0)  # RVOL normalized by 2.0

        # Grade downgrade map
        downgrades = {
            "A+": "A",
            "A": "B",
            "B": "C",
            "C": "D",
            "D": "F",
            "F": "F",
        }
        df["GRADE"] = df["GRADE"].mask(
            low_vol, cast(Any, df["GRADE"]).map(downgrades).fillna(df["GRADE"])
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
    tf_aligned = tf_long.where(is_long, tf_short)
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
    factor_aligned = factor_bull.where(is_long, factor_bear)
    df["FACTOR_CONFLUENCE"] = pd.Series(factor_aligned, index=df.index).astype(str) + "/4"

    return df
