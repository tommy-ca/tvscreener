import pandera as pa
from pandera.typing import DataFrame, Series


class BronzeSchema(pa.DataFrameModel):
    """Raw TradingView data."""

    symbol: Series[str]
    price: Series[float]
    volume: Series[float] = pa.Field(nullable=True)
    timestamp: Series[pa.DateTime]

    class Config:
        strict = True
        coerce = True


class SilverSchema(pa.DataFrameModel):
    """Enriched data with technical indicators."""

    symbol: Series[str]
    price: Series[float]
    volume: Series[float] = pa.Field(nullable=True)
    timestamp: Series[pa.DateTime]

    # Technical Indicators (dynamic columns are hard in Pandera models,
    # but we can validate common ones)
    rsi: Series[float] = pa.Field(nullable=True, ge=0, le=100)
    atr: Series[float] = pa.Field(nullable=True, ge=0)

    class Config:
        strict = False  # Allow extra indicator columns
        coerce = True


class GoldSchema(pa.DataFrameModel):
    """Final scored signals."""

    symbol: Series[str]
    timestamp: Series[pa.DateTime]
    ensemble_score: Series[float]
    direction: Series[str] = pa.Field(isin=["long", "short"])
    grade: Series[str] = pa.Field(isin=["A+", "A", "B", "C", "D", "F"])
    total_confluence: Series[int] = pa.Field(ge=0)

    class Config:
        strict = True
        coerce = True


def validate_bronze(df: DataFrame) -> DataFrame:
    return BronzeSchema.validate(df)


def validate_silver(df: DataFrame) -> DataFrame:
    return SilverSchema.validate(df)


def validate_gold(df: DataFrame) -> DataFrame:
    return GoldSchema.validate(df)
