from enum import Enum


class Direction(str, Enum):
    """Unified direction representation."""

    LONG = "long"
    SHORT = "short"
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    ALL = "all"

    @classmethod
    def from_score(cls, score: float) -> "Direction":
        """Map a score to a direction."""
        if score > 0:
            return cls.LONG
        elif score < 0:
            return cls.SHORT
        return cls.NEUTRAL

    @classmethod
    def from_sentiment(cls, sentiment: float) -> "Direction":
        """Map sentiment score to bullish/bearish."""
        if sentiment > 0:
            return cls.BULLISH
        elif sentiment < 0:
            return cls.BEARISH
        return cls.NEUTRAL

    def to_sentiment(self) -> "Direction":
        """Map long/short to bullish/bearish."""
        if self == Direction.LONG:
            return Direction.BULLISH
        if self == Direction.SHORT:
            return Direction.BEARISH
        return self

    def to_trade(self) -> "Direction":
        """Map bullish/bearish to long/short."""
        if self == Direction.BULLISH:
            return Direction.LONG
        if self == Direction.BEARISH:
            return Direction.SHORT
        return self
