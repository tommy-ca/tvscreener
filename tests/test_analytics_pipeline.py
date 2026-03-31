import narwhals as nw
import pandas as pd
import pytest
from tvscreener_ext.query import EdgeQueryClient


def test_3_step_pipeline():
    # Setup
    df = pd.DataFrame(
        {
            "symbol": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"],
            "price": [150.0, 2800.0, 300.0, 700.0, 3300.0],
            "volume": [1000, 500, 1200, 800, 600],
        }
    )

    client = EdgeQueryClient(db_path=":memory:")

    # Define a 3+ step pipeline
    # 1. SQL Filter
    # 2. Narwhals Transformation (Add column)
    # 3. SQL Aggregation
    # 4. Narwhals Transformation (Sort)

    pipeline = (
        client.pipeline(df)
        .sql("SELECT * FROM df WHERE price > 200")
        .transform(lambda x: x.with_columns(notional=nw.col("price") * nw.col("volume")))
        .sql(
            "SELECT *, notional / 1000 as notional_k FROM df WHERE volume > {{ min_vol }}",
            params={"min_vol": 600},
        )
        .transform(lambda x: x.sort("notional_k", descending=True))
    )

    result = pipeline.collect()

    # Assertions
    assert isinstance(result, pd.DataFrame)
    assert (
        len(result) == 2
    )  # TSLA (700*800=560k), MSFT (300*1200=360k). GOOGL and AMZN have vol <= 600 in the filtered set?
    # Wait: GOOGL (500), AMZN (600). So only MSFT (1200) and TSLA (800) pass volume > 600.

    assert list(result["symbol"]) == ["TSLA", "MSFT"]
    assert "notional_k" in result.columns
    assert result["notional_k"].iloc[0] == (700 * 800) / 1000
    assert result["notional_k"].iloc[1] == (300 * 1200) / 1000


def test_pipeline_with_minijinja():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    client = EdgeQueryClient(db_path=":memory:")

    # Use MiniJinja {{ df }} explicitly
    pipeline = client.pipeline(df).sql(
        "SELECT * FROM {{ df }} WHERE a >= {{ limit }}", params={"limit": 2}
    )

    result = pipeline.execute()
    assert len(result) == 2
    assert result["a"].min() == 2


if __name__ == "__main__":
    pytest.main([__file__])
