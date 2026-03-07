import pandas as pd
import pytest

from tvscreener.lib.lakehouse.manager import LakehouseManager


@pytest.mark.parametrize(
    "table_name",
    [
        "../../../../../../../../tmp/hacked.table",
        "default/../../../../tmp/hacked",
        "default.my_table/../../../../tmp/hacked",
        "default./tmp/hacked",
        "default../../../etc/passwd",
        "default./tmp/hacked_table",
    ],
)
def test_write_table_rejects_path_like_identifiers(table_name: str) -> None:
    mgr = LakehouseManager()
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(
        ValueError, match="Invalid table identifier|Invalid namespace|Invalid table name"
    ):
        mgr.write_table(df, table_name)


@pytest.mark.parametrize(
    "table_name",
    [
        "tvscreener.gold",
        "tvscreener_gold.screener_snapshot",
        "signals_latest",
    ],
)
def test_normalize_table_identifier_accepts_expected_names(table_name: str) -> None:
    mgr = LakehouseManager()
    normalized = mgr._normalize_table_identifier(table_name)
    assert normalized.count(".") == 1
    assert "/" not in normalized
    assert ".." not in normalized
