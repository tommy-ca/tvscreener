import pandas as pd
import pytest

from tvscreener.score import ScoringEngine


def test_scoring_with_arrow_backend():
    # Attempt to use pyarrow backend if available
    import importlib.util

    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    dtype_backend = "pyarrow"

    engine = ScoringEngine(timeframes=["15", "60"], tf_weights={"15": 0.4, "60": 0.6})

    # Create Arrow-backed DataFrame
    df = pd.DataFrame(
        {
            "Recommend All|15": [1.0, -1.0, 0.5],
            "Recommend All|60": [0.5, -0.5, 1.0],
            "Recommend Ma|15": [0.8, -0.8, 0.4],
            "Recommend Ma|60": [0.6, -0.6, 0.8],
            "Recommend Other|15": [0.4, -0.4, 0.2],
            "Recommend Other|60": [0.2, -0.2, 0.4],
            "Roc|15": [1.0, -1.0, 0.5],
            "Roc|60": [2.0, -2.0, 1.0],
        }
    ).convert_dtypes(dtype_backend=dtype_backend)

    # Verify dtypes are indeed arrow-backed
    for col in df.columns:
        assert "arrow" in str(df[col].dtype) or "pyarrow" in str(df[col].dtype)

    # Run ranking pipeline
    result = engine.rank_opportunities(df)

    # Verify results
    assert "ENSEMBLE_SCORE" in result.columns
    assert "DIRECTION" in result.columns
    assert "GRID_PCT" in result.columns
    assert "GRADE" in result.columns

    # First row should be long
    assert result.iloc[0]["DIRECTION"] == "long"
    assert result.iloc[0]["ENSEMBLE_SCORE"] > 0

    # Second row should be short (it might be moved due to sorting, but let's check the values)
    short_rows = result[result["DIRECTION"] == "short"]
    assert len(short_rows) > 0
    assert (short_rows["ENSEMBLE_SCORE"] < 0).all()

    # Verify confluence
    # For first row:
    # TREND_15=1.0, TREND_60=0.5 -> both > 0
    # MA_15=0.8, MA_60=0.6 -> both > 0
    # OSC_15=0.4, OSC_60=0.2 -> both > 0
    # ROC_15=1.0, ROC_60=2.0 -> both > 0
    # Total 8 columns, all aligned with LONG.
    # GRID_PCT should be 100.

    # Let's find the original first row in the result
    row1 = result[result["Recommend All|15"] == 1.0].iloc[0]
    assert row1["GRID_PCT"] == 100
    assert row1["GRADE"] == "A+"


if __name__ == "__main__":
    pytest.main([__file__])
