from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import pandas as pd

ScoreType = Literal["all", "ma", "oscillator"]


@dataclass(frozen=True)
class ScoreFilter:
    """Filter for TradingView recommendation scores."""

    score_type: ScoreType
    threshold: float


@dataclass(frozen=True)
class RocFilter:
    """Filter for Rate of Change (momentum)."""

    min_roc: float | None = None
    max_roc: float | None = None


@dataclass(frozen=True)
class VolumeFilter:
    """Filter for trading volume."""

    min_volume: float | None = None


@dataclass(frozen=True)
class AtrFilter:
    """Filter for average volatility (ATR)."""

    max_atr: float | None = None


class DataFrameFilter(ABC):
    """Base class for filters that operate on pandas DataFrame (post-fetch)."""

    @abstractmethod
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply this filter to a DataFrame."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
