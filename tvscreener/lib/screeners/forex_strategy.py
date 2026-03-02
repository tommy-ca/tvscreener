from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast

import narwhals as nw
import numpy as np
import pandas as pd

from tvscreener.constants.forex import (
    DEFAULT_FOREX_PAIRS,
)
from tvscreener.core.enums import Direction
from tvscreener.filter import AtrFilter, VolumeFilter
from tvscreener.lib.screeners.base import ExportMixin, ScreenerConfig
from tvscreener.lib.screeners.factory import AssetScreenerFactory
from tvscreener.lib.screeners.filter_utils import (
    apply_ma_score_filter,
    detect_mean_reversion_signals,
)
from tvscreener.lib.screeners.forex_opportunity import ForexScreenerConfig

if TYPE_CHECKING:
    from tvscreener.lib.screeners.filters import DataFrameFilter

logger = logging.getLogger(__name__)

StrategyType = Literal[
    "trend_following",
    "mean_reversion",
    "breakout",
    "hybrid",
    "confluence",
    "all",
]


@dataclass(frozen=True, slots=True)
class StrategyConfig(ScreenerConfig):
    min_confluence: int = 1
    include_strategies: tuple[StrategyType, ...] = ("all",)
    direction: Direction | str = Direction.ALL
    trend_threshold: float = 0.0
    mr_threshold: float = 0.2
    rsi_lower: float = 30.0
    rsi_upper: float = 70.0
    min_roc: float | None = None
    min_volume: float | None = None
    max_atr: float | None = None
    min_ma_score: float | None = None
    mean_reversion_signals: tuple[str, ...] = ()
    contract_type: Literal["spot", "cfd", "spreadbet", "all"] = "cfd"
    include_atr_fields: bool = False
    include_rsi_fields: bool = False
    # Signal quality filters
    min_tf_alignment: int = 1
    require_momentum: bool = False
    require_volume_spike: bool = False


@dataclass
class ForexStrategyScanner(ExportMixin):
    pairs: list[str] = field(default_factory=lambda: DEFAULT_FOREX_PAIRS)
    timeframes: list[str] = field(default_factory=lambda: ["240", "60", "15"])
    config: StrategyConfig = field(default_factory=StrategyConfig)
    asset_type: str = "forex"
    post_filters: list[DataFrameFilter] = field(default_factory=list)
    _screener: Any = field(init=False)
    _cached_results: pd.DataFrame | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        include_atr = (
            self.config.include_atr_fields
            or self.config.max_atr is not None
            or self.config.show_risk
        )
        include_rsi = self.config.include_rsi_fields or bool(self.config.mean_reversion_signals)

        # Build upstream filters (only non-directional filters)
        volume_filter = (
            VolumeFilter(min_volume=self.config.min_volume)
            if self.config.min_volume is not None
            else None
        )
        atr_filter = (
            AtrFilter(max_atr=self.config.max_atr) if self.config.max_atr is not None else None
        )
        self._screener = AssetScreenerFactory.create_screener(
            asset_type=self.asset_type,
            symbols=self.pairs,
            timeframes=self.timeframes,
            config=ForexScreenerConfig(
                volume_filter=volume_filter,
                atr_filter=atr_filter,
                contract_type=self.config.contract_type,
                include_atr=include_atr,
                include_rsi=include_rsi,
                min_rvol=self.config.min_rvol,
                show_risk=self.config.show_risk,
                risk_per_trade_pct=self.config.risk_per_trade_pct,
                atr_multiplier=self.config.atr_multiplier,
                min_risk_reward_ratio=self.config.min_risk_reward_ratio,
                account_balance=self.config.account_balance,
                pip_value=self.config.pip_value,
            ),
        )

    @property
    def metadata(self):
        return self._screener.metadata

    def _get_htf_stf_ltf(self) -> tuple[str, str, str]:
        """Determine HTF, STF, and LTF from available timeframes."""
        if not self.timeframes:
            return "", "", ""

        # Sort timeframes numerically descending (HTF -> STF -> LTF)
        sorted_tfs = sorted(self.timeframes, key=lambda x: int(x), reverse=True)
        num_tfs = len(sorted_tfs)

        if num_tfs >= 3:
            return sorted_tfs[0], sorted_tfs[num_tfs // 2], sorted_tfs[-1]
        if num_tfs == 2:
            return sorted_tfs[0], sorted_tfs[1], sorted_tfs[1]
        return sorted_tfs[0], sorted_tfs[0], sorted_tfs[0]

    def scan(self, use_cache: bool = False) -> pd.DataFrame:
        """Scan selected strategies and return combined results."""
        if use_cache and self._cached_results is not None:
            logger.info("Returning cached scan results")
            return self._cached_results

        raw_data = self._screener.get_opportunities()

        if raw_data.empty:
            return pd.DataFrame()

        strategies_to_run = self.config.include_strategies
        if "all" in strategies_to_run:
            strategies_to_run = [
                "trend_following",
                "mean_reversion",
                "hybrid",
                "breakout",
            ]

        results = []

        if "trend_following" in strategies_to_run:
            trend_results = self.scan_trend_following(raw_data)
            if not trend_results.empty:
                results.append(trend_results)

        if "mean_reversion" in strategies_to_run:
            mr_results = self.scan_mean_reversion(raw_data)
            if not mr_results.empty:
                results.append(mr_results)

        if "hybrid" in strategies_to_run:
            hybrid_results = self.scan_hybrid(raw_data)
            if not hybrid_results.empty:
                results.append(hybrid_results)

        if "breakout" in strategies_to_run:
            breakout_results = self.scan_breakout(raw_data)
            if not breakout_results.empty:
                results.append(breakout_results)

        if "confluence" in strategies_to_run:
            confluence_results = self.scan_confluence(raw_data)
            if not confluence_results.empty:
                results.append(confluence_results)

        if not results:
            return pd.DataFrame()

        combined = pd.concat(results, ignore_index=True)

        # Join back to opportunity results on PAIR to get grid confluence data
        # this ensures we have cross-scanner quality metrics (Todo 072)
        grid_cols = [
            "PAIR",
            "GRID_ALIGNED",
            "GRID_TOTAL",
            "GRID_PCT",
            "GRADE",
            "TF_CONFLUENCE",
            "FACTOR_CONFLUENCE",
        ]
        available_grid_cols = [c for c in grid_cols if c in raw_data.columns]
        if "PAIR" in combined.columns and len(available_grid_cols) > 1:
            # Drop any existing grid columns from combined to avoid duplicates before join
            other_grid_cols = [c for c in available_grid_cols if c != "PAIR"]
            combined = combined.drop(
                columns=[c for c in other_grid_cols if c in combined.columns], errors="ignore"
            )

            grid_df = raw_data[available_grid_cols].drop_duplicates(subset=["PAIR"])
            combined = pd.merge(combined, grid_df, on="PAIR", how="left")

        combined = self._apply_filters(combined)
        combined = apply_ma_score_filter(combined, self.config.min_ma_score)
        combined = detect_mean_reversion_signals(
            combined,
            self.config.mean_reversion_signals,
            rsi_lower=self.config.rsi_lower,
            rsi_upper=self.config.rsi_upper,
        )

        # Apply post_filters so all consumers get identically filtered data
        if self.post_filters:
            for pf in self.post_filters:
                combined = pf(combined)  # type: ignore
                if combined.empty:
                    break

        self._cached_results = combined

        # Finish metadata
        self._screener.metadata.set_config(
            {
                **self._screener.metadata.config,
                "min_confluence": self.config.min_confluence,
                "strategies": list(strategies_to_run),
                "risk_management": {
                    "risk_per_trade_percent": self.config.risk_per_trade_pct,
                    "atr_multiplier": self.config.atr_multiplier,
                    "min_risk_reward": self.config.min_risk_reward_ratio,
                    "account_balance": self.config.account_balance,
                    "min_tf_alignment": self.config.min_tf_alignment,
                    "require_momentum": self.config.require_momentum,
                    "min_rvol": self.config.min_rvol,
                    "require_volume_spike": self.config.require_volume_spike,
                },
            }
        )
        self._screener.metadata.finish(results_count=len(combined), total_signals=len(combined))

        return combined

    def _get_data_or_fetch(self, raw_data: pd.DataFrame | None) -> pd.DataFrame:
        """Fetch data if not provided, or return empty DataFrame if already empty."""
        if raw_data is None:
            raw_data = cast(pd.DataFrame, self._screener.get_opportunities())

        if raw_data.empty:
            return pd.DataFrame()

        return raw_data

    def scan_trend_following(self, raw_data: pd.DataFrame | None = None) -> pd.DataFrame:
        """HTF + STF confluence - trend alignment across timeframes."""
        raw_data = self._get_data_or_fetch(raw_data)
        if raw_data.empty:
            return pd.DataFrame()
        return self._detect_trend_following(raw_data)

    def scan_mean_reversion(self, raw_data: pd.DataFrame | None = None) -> pd.DataFrame:
        """LTF oscillator extremes - overbought/oversold."""
        raw_data = self._get_data_or_fetch(raw_data)
        if raw_data.empty:
            return pd.DataFrame()
        return self._detect_mean_reversion(raw_data)

    def scan_hybrid(self, raw_data: pd.DataFrame | None = None) -> pd.DataFrame:
        """HTF trend + LTF mean reversion."""
        raw_data = self._get_data_or_fetch(raw_data)
        if raw_data.empty:
            return pd.DataFrame()
        return self._detect_hybrid(raw_data)

    def scan_breakout(self, raw_data: pd.DataFrame | None = None) -> pd.DataFrame:
        """Multi-TF momentum alignment."""
        raw_data = self._get_data_or_fetch(raw_data)
        if raw_data.empty:
            return pd.DataFrame()
        return self._detect_breakout(raw_data)

    def scan_confluence(self, raw_data: pd.DataFrame | None = None) -> pd.DataFrame:
        """Multi-TF confluence patterns with unified ranking."""
        raw_data = self._get_data_or_fetch(raw_data)
        if raw_data.empty:
            return pd.DataFrame()
        return self._detect_confluence(raw_data)

    def _detect_trend_following(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect trend following setups: HTF + STF + LTF aligned."""
        htf_val, stf_val, ltf_val = self._get_htf_stf_ltf()
        if not htf_val:
            return pd.DataFrame()

        htf_col = f"Recommend All|{htf_val}"
        stf_col = f"Recommend All|{stf_val}"
        ltf_col = f"Recommend All|{ltf_val}"

        if htf_col not in df.columns or stf_col not in df.columns:
            return pd.DataFrame()

        htf_trend = df[htf_col].fillna(0)
        stf_trend = df[stf_col].fillna(0)
        has_ltf = ltf_col in df.columns
        ltf_trend = df[ltf_col].fillna(0) if has_ltf else pd.Series(0, index=df.index)

        long_mask = (htf_trend > self.config.trend_threshold) & (
            stf_trend > self.config.trend_threshold
        )
        short_mask = (htf_trend < -self.config.trend_threshold) & (
            stf_trend < -self.config.trend_threshold
        )

        if has_ltf:
            long_mask = long_mask & (ltf_trend > self.config.trend_threshold)
            short_mask = short_mask & (ltf_trend < -self.config.trend_threshold)

        aligned_count = 2 + int(has_ltf)
        result = df.loc[long_mask | short_mask].assign(
            STRATEGY="trend_following",
            HTF_TREND=htf_trend[long_mask | short_mask].values,
            STF_TREND=stf_trend[long_mask | short_mask].values,
            CONFLUENCE_SCORE=aligned_count,
        )

        result = self._add_direction(result)

        return result

    def _detect_mean_reversion(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect mean reversion: LTF oscillator extremes aligned with HTF trend."""
        htf_val, _, ltf_val = self._get_htf_stf_ltf()
        if not htf_val:
            return pd.DataFrame()

        htf_col = f"Recommend All|{htf_val}"
        ltf_col = f"Recommend Other|{ltf_val}"

        if htf_col not in df.columns or ltf_col not in df.columns:
            return pd.DataFrame()

        htf_trend = df[htf_col].fillna(0)
        osc_value = df[ltf_col].fillna(0)

        long_mask = (htf_trend > self.config.trend_threshold) & (
            osc_value < -self.config.mr_threshold
        )
        short_mask = (htf_trend < -self.config.trend_threshold) & (
            osc_value > self.config.mr_threshold
        )

        mask = long_mask | short_mask
        if not mask.any():
            return pd.DataFrame()

        result = df.loc[mask].assign(
            STRATEGY="mean_reversion",
            LTF_MOMENTUM=osc_value[mask].values,
            CONFLUENCE_SCORE=1,
        )
        result["MR_STRENGTH"] = result["LTF_MOMENTUM"].abs()
        result["DIRECTION"] = np.where(
            result["LTF_MOMENTUM"] < -self.config.mr_threshold,
            Direction.LONG.value,
            Direction.SHORT.value,
        )
        return result.sort_values("MR_STRENGTH", ascending=False)

    def _detect_hybrid(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect hybrid: HTF trend + LTF mean reversion."""
        htf_val, _, ltf_val = self._get_htf_stf_ltf()
        if not htf_val:
            return pd.DataFrame()

        htf_col = f"Recommend All|{htf_val}"
        ltf_col = f"Recommend Other|{ltf_val}"

        if htf_col not in df.columns or ltf_col not in df.columns:
            return pd.DataFrame()

        htf_trend = df[htf_col].fillna(0)
        ltf_osc = df[ltf_col].fillna(0)

        long_mask = (htf_trend > self.config.trend_threshold) & (
            ltf_osc < -self.config.mr_threshold
        )
        short_mask = (htf_trend < -self.config.trend_threshold) & (
            ltf_osc > self.config.mr_threshold
        )

        mask = long_mask | short_mask
        if not mask.any():
            return pd.DataFrame()

        result = df.loc[mask].assign(
            STRATEGY="hybrid",
            HTF_TREND=htf_trend[mask].values,
            LTF_MOMENTUM=ltf_osc[mask].values,
            CONFLUENCE_SCORE=2,
        )
        result["DIRECTION"] = np.where(
            result["HTF_TREND"] > 0, Direction.LONG.value, Direction.SHORT.value
        )

        return result

    def _detect_breakout(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect breakout: Multi-TF momentum alignment."""
        roc_cols = [f"Roc|{tf}" for tf in self.timeframes]

        available_roc_cols = [c for c in roc_cols if c in df.columns]
        if not available_roc_cols:
            return pd.DataFrame()

        roc_values = df[available_roc_cols].fillna(0)

        if self.config.min_roc is not None:
            long_mask = (roc_values > self.config.min_roc).all(axis=1)
            short_mask = (roc_values < -self.config.min_roc).all(axis=1)
        else:
            long_mask = (roc_values > 0).all(axis=1)
            short_mask = (roc_values < 0).all(axis=1)

        mask = long_mask | short_mask
        if not mask.any():
            return pd.DataFrame()

        result = df.loc[mask].assign(
            STRATEGY="breakout",
            CONFLUENCE_SCORE=len(available_roc_cols),
        )

        result["DIRECTION"] = np.where(
            result[available_roc_cols[0]] > 0, Direction.LONG.value, Direction.SHORT.value
        )

        return result

    def _detect_confluence(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect multi-TF confluence patterns and rank results.

        Produces one confluence pattern per pair (best matching pattern by priority).
        """

        if df.empty:
            return pd.DataFrame()

        trend_thr = self.config.trend_threshold
        mr_thr = self.config.mr_threshold

        htf_val, stf_val, ltf_val = self._get_htf_stf_ltf()
        if not htf_val:
            return pd.DataFrame()

        def _col(name: str) -> pd.Series:
            if name in df.columns:
                return df[name].fillna(0)
            return pd.Series(0, index=df.index)

        htf = _col(f"Recommend All|{htf_val}")
        stf = _col(f"Recommend All|{stf_val}")
        ltf = _col(f"Recommend All|{ltf_val}")
        osc_htf = _col(f"Recommend Other|{htf_val}")
        osc_stf = _col(f"Recommend Other|{stf_val}")
        osc_ltf = _col(f"Recommend Other|{ltf_val}")

        htf_long = htf > trend_thr
        htf_short = htf < -trend_thr

        stf_long_trend = stf > trend_thr
        stf_short_trend = stf < -trend_thr
        ltf_long_trend = ltf > trend_thr
        ltf_short_trend = ltf < -trend_thr

        stf_long_mr = osc_stf < -mr_thr
        stf_short_mr = osc_stf > mr_thr
        ltf_long_mr = osc_ltf < -mr_thr
        ltf_short_mr = osc_ltf > mr_thr

        trend_cont_long = htf_long & stf_long_trend & ltf_long_trend
        trend_cont_short = htf_short & stf_short_trend & ltf_short_trend

        trend_pullback_long = htf_long & stf_long_trend & ltf_long_mr
        trend_pullback_short = htf_short & stf_short_trend & ltf_short_mr

        mr_entry_long = htf_long & stf_long_mr & ltf_long_mr
        mr_entry_short = htf_short & stf_short_mr & ltf_short_mr

        mr_rev_long = (osc_htf < -mr_thr) & (osc_stf < -mr_thr) & (osc_ltf < -mr_thr)
        mr_rev_short = (osc_htf > mr_thr) & (osc_stf > mr_thr) & (osc_ltf > mr_thr)

        conds = [
            mr_entry_long | mr_entry_short,
            trend_cont_long | trend_cont_short,
            trend_pullback_long | trend_pullback_short,
            mr_rev_long | mr_rev_short,
        ]
        patterns = [
            "trend_mr_entry",
            "trend_continuation",
            "trend_pullback",
            "mr_reversal",
        ]
        base_scores = [5, 4, 3, 3]

        pattern = np.select(conds, patterns, default="")
        base_score = np.select(conds, base_scores, default=0).astype(int)

        is_long = mr_entry_long | trend_cont_long | trend_pullback_long | mr_rev_long
        direction = np.where(is_long, Direction.LONG.value, Direction.SHORT.value)

        mr_extremity = pd.Series(
            np.max([osc_htf.abs().values, osc_stf.abs().values, osc_ltf.abs().values], axis=0),
            index=df.index,
        )

        # Optional momentum confirmation: add +1 when ROC aligns across available TFs.
        roc_cols = [f"Roc|{tf}" for tf in self.timeframes if f"Roc|{tf}" in df.columns]
        roc_bonus = pd.Series(0, index=df.index)
        if roc_cols:
            roc_values = df[roc_cols].fillna(0)
            if self.config.min_roc is not None:
                long_ok = (roc_values > self.config.min_roc).all(axis=1)
                short_ok = (roc_values < -self.config.min_roc).all(axis=1)
            else:
                long_ok = (roc_values > 0).all(axis=1)
                short_ok = (roc_values < 0).all(axis=1)
            roc_bonus = ((is_long & long_ok) | (~is_long & short_ok)).astype(int)

        score = (base_score + roc_bonus).clip(upper=5).astype(int)

        mask = base_score > 0
        if not mask.any():
            return pd.DataFrame()

        result = df.loc[mask].assign(
            STRATEGY="confluence",
            CONFLUENCE_PATTERN=pattern[mask],
            CONFLUENCE_SCORE=score[mask],
            DIRECTION=direction[mask],
            MR_EXTREMITY=mr_extremity[mask],
        )

        result = result.sort_values(["CONFLUENCE_SCORE", "MR_EXTREMITY"], ascending=[False, False])

        return result

    def _add_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add direction based on HTF_TREND."""
        if df.empty:
            return df

        if "HTF_TREND" in df.columns:
            df["DIRECTION"] = np.where(
                df["HTF_TREND"] > 0, Direction.LONG.value, Direction.SHORT.value
            )

        return df

    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply config filters to results."""
        if df.empty:
            return df

        if self.config.direction != Direction.ALL and self.config.direction != "all":
            df = df[df["DIRECTION"] == self.config.direction]

        if self.config.min_confluence > 0:
            df = df[df["CONFLUENCE_SCORE"] >= self.config.min_confluence]

        if self.config.min_rvol is not None and "RVOL" in df.columns:
            df = df[df["RVOL"] >= self.config.min_rvol]

        return df

    def _get_results(self) -> pd.DataFrame:
        if self._cached_results is not None:
            return self._cached_results
        return self.scan(use_cache=True)

    def _get_data(self) -> pd.DataFrame:
        """Implementation for ExportMixin."""
        return self._get_results()

    @nw.narwhalify
    def _prepare_enriched_data(self, df: Any) -> Any:
        """Prepare DataFrame with canonical names and human-readable factor columns."""
        if len(df) == 0:
            return df

        # Add visual strength signs
        if "DIRECTION" in df.columns:
            # Vectorized generation of STRENGTH_SIGN using Narwhals
            # Handle potential absence of CONFLUENCE_SCORE gracefully
            if "CONFLUENCE_SCORE" in df.columns:
                scores = nw.col("CONFLUENCE_SCORE").cast(nw.Float64).fill_null(0)
            else:
                scores = nw.lit(0)

            directions = nw.col("DIRECTION").cast(nw.String).str.to_lowercase()
            is_long = directions == Direction.LONG.value

            df = df.with_columns(
                STRENGTH_SIGN=nw.when((scores >= 3) & is_long)
                .then(nw.lit("🟢🟢"))
                .otherwise(
                    nw.when((scores >= 3) & (~is_long))
                    .then(nw.lit("🔴🔴"))
                    .otherwise(
                        nw.when((scores >= 1) & is_long)
                        .then(nw.lit("🟢"))
                        .otherwise(
                            nw.when((scores >= 1) & (~is_long))
                            .then(nw.lit("🔴"))
                            .otherwise(nw.lit("⚪"))
                        )
                    )
                )
            )
        else:
            df = df.with_columns(STRENGTH_SIGN=nw.lit(""))

        return df

    def export(self, path: str, format_name: str, label: str = "signals", **kwargs) -> None:
        """Export results using ExportMixin logic."""
        super().export(path, format_name, label=label, **kwargs)
