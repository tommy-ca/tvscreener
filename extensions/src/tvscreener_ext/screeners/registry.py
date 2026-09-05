from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd

if False:  # pragma: no cover
    pass


class ScreenerHandler(Protocol):
    def __call__(self, request: Any) -> int: ...


def _normalize_family(name: str) -> str:
    return (name or "").strip().lower()


@dataclass
class ScreenerFamilyRegistry:
    """Registry of screener families to execution handlers."""

    _handlers: dict[str, ScreenerHandler] = field(default_factory=dict)

    def register(self, family: str, handler: ScreenerHandler) -> None:
        key = _normalize_family(family)
        if not key:
            raise ValueError("Screener family cannot be empty")
        self._handlers[key] = handler

    def run(self, family: str, request: Any) -> int:
        key = _normalize_family(family)
        if key not in self._handlers:
            known = ", ".join(sorted(self._handlers))
            raise ValueError(f"Unknown scanner type: {family}. Registered families: {known}")
        return int(self._handlers[key](request))

    def families(self) -> list[str]:
        return sorted(self._handlers)


DataStage = Callable[[pd.DataFrame], pd.DataFrame]


def compose_stages(stages: Sequence[DataStage]) -> DataStage:
    """Compose rank/filter/strategy stages into one deterministic program."""

    def _run(df: pd.DataFrame) -> pd.DataFrame:
        out = df
        for stage in stages:
            out = stage(out)
            if out.empty:
                return out
        return out

    return _run


def rank_by(column: str, ascending: bool = False) -> DataStage:
    def _rank(df: pd.DataFrame) -> pd.DataFrame:
        if column not in df.columns:
            return df
        return df.sort_values(column, ascending=ascending)

    return _rank


def filter_expr(expr: str) -> DataStage:
    def _filter(df: pd.DataFrame) -> pd.DataFrame:
        if not expr:
            return df
        try:
            return df.query(expr)
        except Exception:
            return df

    return _filter


def strategy_is(strategy_name: str) -> DataStage:
    def _strategy(df: pd.DataFrame) -> pd.DataFrame:
        if "STRATEGY" not in df.columns:
            return df
        return df[df["STRATEGY"] == strategy_name]

    return _strategy
