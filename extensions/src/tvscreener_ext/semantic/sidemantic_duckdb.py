from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import duckdb


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _rows(
    con: duckdb.DuckDBPyConnection, sql: str, params: tuple[Any, ...] = ()
) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    out: list[dict[str, Any]] = []
    for r in cur.fetchall():
        out.append({cols[i]: _jsonable(r[i]) for i in range(len(cols))})
    return out


@dataclass(frozen=True, slots=True)
class DuckDBModel:
    name: str
    sql: str

    def run(
        self, con: duckdb.DuckDBPyConnection, *, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        return _rows(con, self.sql, params=params)


TOP_ROWS = DuckDBModel(
    name="top_rows",
    sql=(
        "SELECT entity_id, name, grade, direction, score, bull_count, total_count, fetched_at_utc "
        "FROM results "
        "ORDER BY score DESC "
        "LIMIT ?"
    ),
)

GRADE_SUMMARY = DuckDBModel(
    name="grade_summary",
    sql=(
        "SELECT grade, direction, COUNT(*) AS n "
        "FROM results "
        "GROUP BY 1, 2 "
        "ORDER BY grade, direction"
    ),
)


def write_semantic_tables(
    *,
    results_parquet_path: str,
    out_top_rows_json_path: str,
    out_grade_summary_json_path: str,
    top_rows_limit: int = 25,
) -> None:
    con = duckdb.connect(database=":memory:")
    # DuckDB does not support prepared parameters in CREATE VIEW statements.
    path = str(results_parquet_path).replace("'", "''")
    con.execute(f"CREATE VIEW results AS SELECT * FROM read_parquet('{path}')")

    top_rows = TOP_ROWS.run(con, params=(int(top_rows_limit),))
    grade_summary = GRADE_SUMMARY.run(con)

    with open(out_top_rows_json_path, "w", encoding="utf-8") as f:
        json.dump(top_rows, f, indent=2, sort_keys=True)
    with open(out_grade_summary_json_path, "w", encoding="utf-8") as f:
        json.dump(grade_summary, f, indent=2, sort_keys=True)
