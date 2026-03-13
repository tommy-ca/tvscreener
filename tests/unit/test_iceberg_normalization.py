import pandas as pd

from tvscreener.lib.screeners.base import normalize_iceberg_count_like_columns


def test_normalize_iceberg_count_like_columns_rounds_and_int_casts():
    df = pd.DataFrame(
        {
            "Volume": [1.2, 2.8, None],
            "GRID_ALIGNED": [3.1, 4.0, 5.9],
            "OTHER": ["x", "y", "z"],
        }
    )

    out = normalize_iceberg_count_like_columns(df)
    assert str(out["Volume"].dtype) == "Int64"
    assert str(out["GRID_ALIGNED"].dtype) == "Int64"
    assert out["Volume"].tolist() == [1, 3, pd.NA]
    assert out["GRID_ALIGNED"].tolist() == [3, 4, 6]
