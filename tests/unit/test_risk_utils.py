"""Tests for risk management utilities."""

import pandas as pd
import pytest

from tvscreener_ext.screeners.risk_utils import (
    RiskConfig,
    RiskEngine,
    calculate_position_size,
    calculate_risk_reward_ratio,
    calculate_stop_loss,
    calculate_take_profit,
)


class TestRiskEngine:
    def test_apply_risk_management(self):
        config = RiskConfig(
            account_balance=10000.0,
            risk_per_trade_pct=1.0,
            min_risk_reward_ratio=2.0,
            atr_multiplier=2.0,
            pip_value=10.0,
        )
        engine = RiskEngine(config)

        df = pd.DataFrame(
            {
                "PAIR": ["EURUSD"],
                "PRICE": [1.1000],
                "DIRECTION": ["long"],
                "ATR_15": [0.0010],
            }
        )

        result = engine.apply(df)

        assert "STOP_LOSS" in result.columns
        assert "TAKE_PROFIT" in result.columns
        assert "RR_RATIO" in result.columns
        assert "POSITION_SIZE" in result.columns

        # Stop loss: 1.1000 - (0.0010 * 2.0) = 1.0980
        assert result.loc[0, "STOP_LOSS"] == pytest.approx(1.0980)

        # Take profit: 1.1000 + (0.0020 * 2.0) = 1.1040
        assert result.loc[0, "TAKE_PROFIT"] == pytest.approx(1.1040)

        # RR Ratio: 0.0040 / 0.0020 = 2.0
        assert result.loc[0, "RR_RATIO"] == pytest.approx(2.0)

        # Position size: (10000 * 0.01) / (0.0020 * 10) = 100 / 0.02 = 5000.0
        assert result.loc[0, "POSITION_SIZE"] == pytest.approx(5000.0)


class TestStopLoss:
    def test_long_stop_loss(self):
        result = calculate_stop_loss(100.0, "long", 0.5, 2.0)
        assert result == 99.0

    def test_short_stop_loss(self):
        result = calculate_stop_loss(100.0, "short", 0.5, 2.0)
        assert result == 101.0

    def test_none_atr_returns_entry(self):
        result = calculate_stop_loss(100.0, "long", None, 2.0)
        assert result == 100.0


class TestTakeProfit:
    def test_long_take_profit(self):
        result = calculate_take_profit(100.0, 98.0, "long", 2.0)
        assert result == 104.0

    def test_short_take_profit(self):
        result = calculate_take_profit(100.0, 102.0, "short", 2.0)
        assert result == 96.0


class TestPositionSize:
    def test_basic_calculation(self):
        result = calculate_position_size(10000, 0.01, 0.02, 10)
        assert result == 500.0

    def test_zero_stop_distance(self):
        result = calculate_position_size(10000, 0.01, 0, 10)
        assert result == 0.0


class TestRiskRewardRatio:
    def test_risk_reward_calculation(self):
        result = calculate_risk_reward_ratio(100.0, 98.0, 104.0)
        assert result == 2.0
