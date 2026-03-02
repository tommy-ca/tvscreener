"""Risk management utilities for forex trading."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tvscreener.core.enums import Direction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskConfig:
    """Risk management configuration."""

    account_balance: float = 10000.0
    risk_per_trade_pct: float = 1.0
    min_risk_reward_ratio: float = 1.5
    atr_multiplier: float = 2.0
    pip_value: float = 10.0


RISK_DEFAULTS = RiskConfig()


class RiskEngine:
    """Engine for applying risk management calculations to DataFrames."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate stop loss, take profit and position sizing using vectorized operations."""
        if df.empty:
            return df

        df = df.copy()

        # Drop existing risk columns to avoid duplicates
        risk_cols = ["STOP_LOSS", "TAKE_PROFIT", "RR_RATIO", "POSITION_SIZE"]
        df = df.drop(columns=[c for c in risk_cols if c in df.columns], errors="ignore")

        # Try to find a representative ATR for the pair
        # We'll use the first available ATR column
        atr_cols = [
            c for c in df.columns if c.upper().startswith("ATR|") or c.upper().startswith("ATR_")
        ]

        # Vectorized data extraction
        entry = (
            df["PRICE"]
            if "PRICE" in df.columns
            else df.get("Price", pd.Series(0.0, index=df.index))
        )
        direction = (
            df["DIRECTION"].astype(str).str.lower()
            if "DIRECTION" in df.columns
            else pd.Series("long", index=df.index)
        )

        # Get ATR by coalescing ATR columns (first non-null)
        if atr_cols:
            atr = df[atr_cols].bfill(axis=1).iloc[:, 0]
        else:
            atr = pd.Series(None, index=df.index, dtype=float)

        # Vectorized calculations
        df["STOP_LOSS"] = calculate_stop_loss(
            entry, direction, atr, multiplier=self.config.atr_multiplier
        )
        df["TAKE_PROFIT"] = calculate_take_profit(
            entry, df["STOP_LOSS"], direction, min_rr=self.config.min_risk_reward_ratio
        )
        df["RR_RATIO"] = calculate_risk_reward_ratio(entry, df["STOP_LOSS"], df["TAKE_PROFIT"])

        # Position sizing
        stop_dist = (entry - df["STOP_LOSS"]).abs()
        df["POSITION_SIZE"] = calculate_position_size(
            self.config.account_balance,
            self.config.risk_per_trade_pct / 100.0,  # Convert percentage to decimal
            stop_dist,
            pip_value=self.config.pip_value,
        )

        return df


def calculate_stop_loss(
    entry: float | pd.Series,
    direction: Direction | str | pd.Series,
    atr: float | pd.Series | None,
    multiplier: float = 2.0,
) -> float | pd.Series:
    """Calculate ATR-based stop loss (supports vectorized Pandas operations).

    Args:
        entry: Entry price(s)
        direction: Trade direction(s) (long/short)
        atr: Average True Range value(s)
        multiplier: ATR multiplier for stop distance

    Returns:
        Stop loss price level(s)
    """
    if atr is None:
        return entry

    # Handle both scalar and series/array
    sl_distance = atr * multiplier

    # Vectorized logic using numpy where possible
    if isinstance(direction, pd.Series) or isinstance(entry, pd.Series):
        # Convert everything to pandas series for alignment if they aren't already
        entry_s = pd.Series(entry) if not isinstance(entry, pd.Series) else entry
        direction_s = pd.Series(direction) if not isinstance(direction, pd.Series) else direction
        atr_s = pd.Series(atr) if not isinstance(atr, pd.Series) else atr

        is_long = (direction_s == Direction.LONG) | (direction_s == "long")
        sl = np.where(is_long, entry_s - sl_distance, entry_s + sl_distance)

        # Handle null/zero ATR
        invalid_atr = (atr_s.isna()) | (atr_s <= 0)
        sl = np.where(invalid_atr, entry_s, sl)

        return pd.Series(sl, index=entry_s.index)

    # Scalar fallback
    if atr <= 0:
        return entry

    if direction == Direction.LONG or direction == "long":
        return entry - sl_distance
    return entry + sl_distance


def calculate_take_profit(
    entry: float | pd.Series | None,
    stop_loss: float | pd.Series | None,
    direction: Direction | str | pd.Series,
    min_rr: float = 2.0,
) -> float | pd.Series:
    """Calculate take profit based on R:R ratio (supports vectorized Pandas operations).

    Args:
        entry: Entry price(s)
        stop_loss: Stop loss price(s)
        direction: Trade direction(s) (long/short)
        min_rr: Minimum risk:reward ratio

    Returns:
        Take profit price level(s)
    """
    if stop_loss is None or entry is None:
        return entry if entry is not None else 0.0

    # Vectorized logic
    if (
        isinstance(direction, pd.Series)
        or isinstance(entry, pd.Series)
        or isinstance(stop_loss, pd.Series)
    ):
        entry_s = pd.Series(entry) if not isinstance(entry, pd.Series) else entry
        stop_loss_s = pd.Series(stop_loss) if not isinstance(stop_loss, pd.Series) else stop_loss
        direction_s = pd.Series(direction) if not isinstance(direction, pd.Series) else direction

        risk = (entry_s - stop_loss_s).abs()
        reward = risk * min_rr

        is_long = (direction_s == Direction.LONG) | (direction_s == "long")
        tp = np.where(is_long, entry_s + reward, entry_s - reward)

        return pd.Series(tp, index=entry_s.index)

    # Scalar fallback
    risk = abs(entry - stop_loss)
    reward = risk * min_rr
    if direction == Direction.LONG or direction == "long":
        return entry + reward
    return entry - reward


def calculate_position_size(
    account_balance: float,
    risk_per_trade: float,
    stop_distance: float | pd.Series,
    pip_value: float = 10.0,
) -> float | pd.Series:
    """Calculate position size in lots (supports vectorized Pandas operations).

    Args:
        account_balance: Account balance in currency units
        risk_per_trade: Risk per trade as decimal (e.g., 0.01 for 1%)
        stop_distance: Stop loss distance in price terms
        pip_value: Value per pip/lot (default 10 for standard lots)

    Returns:
        Position size in lots
    """
    risk_amount = account_balance * risk_per_trade

    if isinstance(stop_distance, pd.Series):
        # Use np.where to handle division by zero or negative stop distance
        pos_size = np.where(stop_distance > 0, risk_amount / (stop_distance * pip_value), 0.0)
        return pd.Series(pos_size, index=stop_distance.index)

    # Scalar fallback
    if stop_distance <= 0:
        return 0.0
    return risk_amount / (stop_distance * pip_value)


def calculate_risk_reward_ratio(
    entry: float | pd.Series | None,
    stop_loss: float | pd.Series | None,
    take_profit: float | pd.Series | None,
) -> float | pd.Series:
    """Calculate risk:reward ratio (supports vectorized Pandas operations).

    Args:
        entry: Entry price(s)
        stop_loss: Stop loss price(s)
        take_profit: Take profit price(s)

    Returns:
        Risk:reward ratio
    """
    if stop_loss is None or take_profit is None or entry is None:
        return 0.0

    # Vectorized logic
    if (
        isinstance(entry, pd.Series)
        or isinstance(stop_loss, pd.Series)
        or isinstance(take_profit, pd.Series)
    ):
        entry_s = pd.Series(entry) if not isinstance(entry, pd.Series) else entry
        stop_loss_s = pd.Series(stop_loss) if not isinstance(stop_loss, pd.Series) else stop_loss
        take_profit_s = (
            pd.Series(take_profit) if not isinstance(take_profit, pd.Series) else take_profit
        )

        risk = (entry_s - stop_loss_s).abs()
        reward = (take_profit_s - entry_s).abs()

        # Handle division by zero
        rr = np.where(risk > 0, reward / risk, 0.0)
        return pd.Series(rr, index=entry_s.index)

    # Scalar fallback
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    if risk <= 0:
        return 0.0
    return reward / risk
