from __future__ import annotations

import pandas as pd
import pytest
from tvscreener_ext.screeners.registry import (
    ScreenerFamilyRegistry,
    compose_stages,
    filter_expr,
    rank_by,
    strategy_is,
)


def test_registry_runs_registered_family():
    registry = ScreenerFamilyRegistry()
    registry.register("opportunity", lambda _request: 7)

    result = registry.run("opportunity", object())

    assert result == 7
    assert registry.families() == ["opportunity"]


def test_registry_raises_for_unknown_family():
    registry = ScreenerFamilyRegistry()
    registry.register("strategy", lambda _request: 1)

    with pytest.raises(ValueError, match="Unknown scanner type"):
        registry.run("missing", object())


def test_compose_stages_rank_filter_strategy():
    df = pd.DataFrame(
        {
            "PAIR": ["A", "B", "C"],
            "ENSEMBLE_SCORE": [0.3, 0.9, 0.6],
            "STRATEGY": ["trend", "trend", "mean_reversion"],
        }
    )

    program = compose_stages(
        [
            rank_by("ENSEMBLE_SCORE", ascending=False),
            filter_expr("ENSEMBLE_SCORE >= 0.5"),
            strategy_is("trend"),
        ]
    )

    out = program(df)

    assert list(out["PAIR"]) == ["B"]
