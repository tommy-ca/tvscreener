"""Tests for JPY and multi-pair risk management."""

import pandas as pd
import pytest
from tvscreener_ext.screeners.risk_utils import (
    RiskConfig,
    RiskEngine,
)


class TestJPYRisk:
    def test_jpy_position_sizing(self):
        # Account balance $10,000, 1% risk = $100
        # USD/JPY at 150.00
        # ATR = 1.00 (100 pips)
        # Stop loss = 150.00 - 2.0 * 1.00 = 148.00 (200 pips)
        # Expected position size:
        # Before fix: 100 / (2.00 * 10) = 5.0
        # After fix: 100 / (2.00 * (10 * 0.01)) = 100 / 0.2 = 500.0

        config = RiskConfig(
            account_balance=10000.0,
            risk_per_trade_pct=1.0,
            pip_value=10.0,
        )
        engine = RiskEngine(config)

        df = pd.DataFrame(
            {
                "TICKER": ["USDJPY"],
                "PRICE": [150.00],
                "DIRECTION": ["long"],
                "ATR_14": [1.00],
            }
        )

        result = engine.apply(df)
        pos_size = result.loc[0, "POSITION_SIZE"]

        assert pos_size == pytest.approx(500.0)

    def test_mixed_pairs_position_sizing(self):
        config = RiskConfig(
            account_balance=10000.0,
            risk_per_trade_pct=1.0,
            pip_value=10.0,
        )
        engine = RiskEngine(config)

        df = pd.DataFrame(
            {
                "TICKER": ["EURUSD", "USDJPY", "EURJPY", "GBPUSD"],
                "PRICE": [1.1000, 150.00, 165.00, 1.3000],
                "DIRECTION": ["long", "long", "long", "long"],
                "ATR_14": [0.0010, 0.10, 0.10, 0.0010],  # 10 pips for all
            }
        )

        # All have 2 * ATR stop distance = 20 pips
        # For EURUSD: 0.0020
        # For USDJPY: 0.20
        # For EURJPY: 0.20
        # For GBPUSD: 0.0020

        # For 20 pips stop and $100 risk, all should have the same position size
        # 100 / (0.0020 * 10) = 5000.0

        result = engine.apply(df)

        assert result.loc[0, "POSITION_SIZE"] == pytest.approx(5000.0)  # EURUSD
        assert result.loc[1, "POSITION_SIZE"] == pytest.approx(5000.0)  # USDJPY
        assert result.loc[2, "POSITION_SIZE"] == pytest.approx(5000.0)  # EURJPY
        assert result.loc[3, "POSITION_SIZE"] == pytest.approx(5000.0)  # GBPUSD

    def test_custom_pip_value_column(self):
        config = RiskConfig(
            account_balance=10000.0,
            risk_per_trade_pct=1.0,
            pip_value=10.0,
        )
        engine = RiskEngine(config)

        df = pd.DataFrame(
            {
                "TICKER": ["EURUSD", "USDJPY"],
                "PRICE": [1.1000, 150.00],
                "DIRECTION": ["long", "long"],
                "ATR_14": [0.0010, 0.10],
                "PIP_VALUE": [10.0, 6.67],  # Custom pip value for USDJPY ($1000 / 150 = 6.67)
            }
        )

        # Risk = $100
        # Stop = 20 pips
        # EURUSD: 100 / (20 * 10) = 0.5 lots (or 5000 units in our scale)
        # USDJPY: 100 / (20 * 6.67) = 0.75 lots (or 7500 units in our scale)

        result = engine.apply(df)

        assert result.loc[0, "POSITION_SIZE"] == pytest.approx(5000.0)
        assert result.loc[1, "POSITION_SIZE"] == pytest.approx(7500.0, rel=0.01)
