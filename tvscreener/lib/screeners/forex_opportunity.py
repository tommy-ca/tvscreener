from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from tvscreener.beauty import VisualStyler
from tvscreener.constants.forex import (
    DEFAULT_FOREX_PAIRS,
    DEFAULT_TIMEFRAMES,
    EXCHANGE_PRIORITY,
    LIQUID_EXCHANGES,
)
from tvscreener.core.forex import ForexScreener
from tvscreener.exceptions import (
    FilterConfigurationError,
    InvalidPairError,
)
from tvscreener.field.forex import ForexField
from tvscreener.filter import AtrFilter, RocFilter, ScoreFilter, VolumeFilter
from tvscreener.lib.screeners.base import BaseOpportunityScreener, ScreenerConfig
from tvscreener.lib.screeners.filter_utils import (
    apply_atr_filter,
    apply_contract_type_filter,
    apply_ma_score_filter,
    apply_volume_filter,
)
from tvscreener.lib.screeners.metadata_utils import MetadataCollector

logger = logging.getLogger(__name__)

ContractType = Literal["spot", "cfd", "spreadbet", "all"]


@dataclass(frozen=True, slots=True)
class ForexScreenerConfig(ScreenerConfig):
    score_filters: tuple[ScoreFilter, ...] = field(default_factory=tuple)
    roc_filter: RocFilter | None = None
    volume_filter: VolumeFilter | None = None
    atr_filter: AtrFilter | None = None
    preferred_exchanges: tuple[str, ...] = field(default_factory=lambda: tuple(LIQUID_EXCHANGES))
    contract_type: ContractType = "cfd"
    min_rvol: float | None = None
    show_risk: bool = False


@dataclass
class ForexOpportunityScreener(BaseOpportunityScreener[ForexScreener]):
    pairs: list[str] = field(default_factory=lambda: DEFAULT_FOREX_PAIRS)
    timeframes: list[str] = field(default_factory=lambda: DEFAULT_TIMEFRAMES)
    config: ForexScreenerConfig = field(default_factory=ForexScreenerConfig)
    metadata: MetadataCollector = field(default_factory=MetadataCollector)
    _cached_data: pd.DataFrame | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.symbols = self.pairs
        super().__post_init__()
        # Additional metadata
        self.metadata.update_config(
            {
                "contract_type": self.config.contract_type,
                "preferred_exchanges": list(self.config.preferred_exchanges),
            }
        )

    def _validate_inputs(self) -> None:
        self._validate_pairs()
        self._validate_timeframes()

    def _validate_pairs(self) -> None:
        valid_pairs = DEFAULT_FOREX_PAIRS
        invalid = set(self.pairs) - set(valid_pairs)
        if invalid:
            raise InvalidPairError(f"Invalid forex pairs: {invalid}")

    def _validate_timeframes(self) -> None:
        valid_timeframes = DEFAULT_TIMEFRAMES
        invalid = set(self.timeframes) - set(valid_timeframes)
        if invalid:
            raise FilterConfigurationError(f"Invalid timeframes: {invalid}")

    def _get_screener_instance(self) -> ForexScreener:
        return ForexScreener()

    def _get_field_class(self) -> Any:
        return ForexField

    def __repr__(self) -> str:
        return (
            f"ForexOpportunityScreener("
            f"pairs={len(self.pairs)}, "
            f"timeframes={self.timeframes}, "
            f"score_filters={len(self.config.score_filters)}, "
            f"roc_filter={self.config.roc_filter}, "
            f"volume_filter={self.config.volume_filter}, "
            f"contract_type={self.config.contract_type}, "
            f"preferred_exchanges={len(self.config.preferred_exchanges)})"
        )

    def _get_tickers(self) -> list[str]:
        """Construct all possible tickers for preferred exchanges."""
        return [
            f"{exchange}:{pair}"
            for exchange in self.config.preferred_exchanges
            for pair in self.pairs
        ]

    def _prepare_screener(self, screener: ForexScreener, field_class: Any) -> None:
        """Add asset-specific filters to the screener."""
        if self.config.min_rvol is not None:
            screener.where(self.config.min_rvol < field_class.RELATIVE_VOLUME_10D_CALC)

    def _apply_asset_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._apply_contract_type_filter(df)
        df = self._apply_score_and_roc_filters(df)
        return df

    def _apply_contract_type_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        return apply_contract_type_filter(df, self.config.contract_type)

    def _apply_score_and_roc_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        if self.config.volume_filter:
            df = apply_volume_filter(df, self.config.volume_filter.min_volume)

        if self.config.atr_filter:
            df = apply_atr_filter(df, self.config.atr_filter.max_atr)

        for sf in self.config.score_filters:
            if sf.score_type == "ma":
                df = apply_ma_score_filter(df, sf.threshold)
            else:
                df = self._apply_score_filter(df, sf)

        if self.config.roc_filter:
            df = self._apply_roc_filter(df, self.config.roc_filter)

        if self.config.min_rvol is not None:
            rvol_col = "relative_volume_10d_calc"
            if rvol_col in df.columns:
                df = df[df[rvol_col] >= self.config.min_rvol]

        return df

    def _merge_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        from tvscreener.lib.screeners.transformer import DataTransformer

        return DataTransformer.normalize_forex_pairs(
            df, valid_pairs=DEFAULT_FOREX_PAIRS, exchange_priority=EXCHANGE_PRIORITY
        )

    def _apply_score_filter(self, df: pd.DataFrame, sf: ScoreFilter) -> pd.DataFrame:
        if df.empty:
            return df

        score_type_col = {
            "all": "Recommend All",
            "ma": "Recommend Ma",
            "oscillator": "Recommend Other",
        }

        col_prefix = score_type_col.get(sf.score_type)
        if not col_prefix:
            return df

        score_cols = [c for c in df.columns if c.startswith(col_prefix + "|")]
        if not score_cols:
            return df

        mask = df[score_cols].fillna(-999) >= sf.threshold
        return df[mask.any(axis=1)]

    def _apply_roc_filter(self, df: pd.DataFrame, roc: RocFilter) -> pd.DataFrame:
        if df.empty:
            return df

        mask = pd.Series(True, index=df.index)
        for tf in self.timeframes:
            col = f"Roc|{tf}"
            if col in df.columns:
                if roc.min_roc is not None:
                    mask &= df[col] >= roc.min_roc
                if roc.max_roc is not None:
                    mask &= df[col] <= roc.max_roc

        if not mask.all():
            return df[mask]
        return df

    def _prepare_enriched_data(self, df: Any) -> Any:
        """Prepare DataFrame with canonical names and human-readable factor columns."""
        if len(df) == 0:
            return df

        df = super()._prepare_enriched_data(df)

        # Add visual strength signs as a column for downstream use
        if isinstance(df, pd.DataFrame):
            if "ENSEMBLE_SCORE" in df.columns:
                scores = pd.to_numeric(df["ENSEMBLE_SCORE"], errors="coerce").fillna(0.0)
                df["STRENGTH_SIGN"] = scores.map(
                    lambda v: VisualStyler.opportunity_strength_sign(float(v), is_roc=False)
                )
                df["DIRECTION_SIGN"] = scores.map(lambda v: VisualStyler.direction_emoji(float(v)))
            else:
                df["STRENGTH_SIGN"] = ""
                df["DIRECTION_SIGN"] = ""

        return df

    def export(self, path: str, format_name: str, label: str = "opportunities", **kwargs) -> None:
        """Export results using ExportMixin logic."""
        super().export(path, format_name, label=label, **kwargs)
