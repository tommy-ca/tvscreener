from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

from tvscreener_ext.config import load_settings
from tvscreener_ext.lakehouse import get_manager


def _warehouse_uri() -> str:
    s = load_settings(None).lakehouse
    if s.catalog.mode == "local":
        base = s.catalog.local.base_dir
        base_path = Path(base).expanduser() if base else (Path.home() / ".tvscreener" / "lakehouse")
        wh = (base_path / s.catalog.local.warehouse_dir).absolute()
        return f"file://{wh}"
    assert s.catalog.remote is not None
    return str(s.catalog.remote.warehouse)


def _catalog_uri() -> str:
    s = load_settings(None).lakehouse
    if s.catalog.mode == "local":
        base = s.catalog.local.base_dir
        base_path = Path(base).expanduser() if base else (Path.home() / ".tvscreener" / "lakehouse")
        db = (base_path / s.catalog.local.catalog_db).absolute()
        return f"sqlite:////{db}"
    assert s.catalog.remote is not None
    return str(s.catalog.remote.uri)


def _print_table_summary(*, table_name: str) -> None:
    lh = get_manager()
    arrow = lh.read_table_arrow(table_name)
    print(f"table={table_name} rows={arrow.num_rows} cols={arrow.num_columns}")
    print("schema=")
    for f in arrow.schema:
        print(f"- {f.name}: {f.type}")


def _print_signals_latest_overview(*, table_name: str, limit_groups: int) -> None:
    lh = get_manager()
    arrow = lh.read_table_arrow(table_name)
    con = duckdb.connect(database=":memory:")
    con.register("signals_latest", arrow)

    df = con.execute(
        """
        SELECT asset_type,
               instrument_type,
               universe,
               count(*) AS n,
               max(fetched_at_utc) AS max_fetched_at_utc,
               min(fetched_at_utc) AS min_fetched_at_utc
        FROM signals_latest
        GROUP BY 1,2,3
        ORDER BY 1,2,3
        """
    ).df()

    if limit_groups:
        df = df.head(int(limit_groups))
    print(df.to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    p = argparse.ArgumentParser(description="Audit extensions lakehouse tables")
    p.add_argument(
        "--signals-latest",
        default=os.getenv("TVSCREENER_SIGNALS_LATEST_TABLE", "tvscreener.signals_latest"),
        help="Iceberg identifier to audit (default: tvscreener.signals_latest)",
    )
    p.add_argument("--print-schema", action="store_true")
    p.add_argument("--groups", type=int, default=50)
    args = p.parse_args((sys.argv if argv is None else argv)[1:])

    s = load_settings(None).lakehouse
    print(f"lakehouse.mode={s.catalog.mode}")
    if s.catalog.mode == "local":
        print(f"lakehouse.base_dir={s.catalog.local.base_dir}")
        print(f"lakehouse.catalog_db={s.catalog.local.catalog_db}")
        print(f"lakehouse.warehouse_dir={s.catalog.local.warehouse_dir}")
    print(f"lakehouse.catalog_uri={_catalog_uri()}")
    print(f"lakehouse.warehouse_uri={_warehouse_uri()}")

    table = str(args.signals_latest)
    try:
        if args.print_schema:
            _print_table_summary(table_name=table)
        else:
            _print_signals_latest_overview(table_name=table, limit_groups=int(args.groups))
    except Exception as e:
        print(f"Audit failed for table {table}: {e}")

    # Hint for where local data lives.
    if s.catalog.mode == "local":
        base = s.catalog.local.base_dir
        base_path = Path(base).expanduser() if base else (Path.home() / ".tvscreener" / "lakehouse")
        if base_path.exists():
            print(f"lakehouse.local_exists=1 path={base_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
