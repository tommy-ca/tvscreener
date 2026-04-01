from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import pandas as pd
from tvscreener.field import Field
from tvscreener.filter import ExtraFilter, FilterOperator

ScoreType = Literal["all", "ma", "oscillator"]


class FieldCondition:
    """Represents a comparison condition on a field."""

    def __init__(self, field: Any, operation: FilterOperator, value: Any):
        self.field = field
        self.operation = operation
        self.value = value

    def to_filter(self) -> Filter:
        """Convert this condition to a Filter object."""
        return Filter(self.field, self.operation, self.value)

    def __repr__(self) -> str:
        name = getattr(self.field, "name", str(self.field))
        return f"FieldCondition({name}, {self.operation.name}, {self.value})"


class Filter:
    def __init__(self, field: Field | ExtraFilter, operation: FilterOperator, values: Any):
        self.field = field
        self.operation = operation
        self.values = values if isinstance(values, list) else [values]

    def to_dict(self) -> dict[str, Any]:
        right = [
            v.field_name if hasattr(v, "field_name") else v.value if isinstance(v, Enum) else v
            for v in self.values
        ]
        right = right[0] if len(right) == 1 else right
        left = getattr(self.field, "field_name", str(self.field))
        return {"left": left, "operation": self.operation.value, "right": right}


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
