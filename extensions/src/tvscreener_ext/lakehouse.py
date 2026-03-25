from __future__ import annotations

import contextlib
import logging
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.exceptions import NoSuchTableError

from tvscreener_ext.config import load_settings

logger = logging.getLogger(__name__)


class LakehouseManager:
    def __init__(self, *, config_path: str | None = None) -> None:
        self._settings = load_settings(config_path)
        self._catalog: Catalog | None = None
        self._base_dir: Path | None = None
        self._catalog_db_path: Path | None = None
        self._warehouse_path: Path | None = None

        cat = self._settings.lakehouse
        if cat.mode == "local":
            base = cat.local.base_dir
            self._base_dir = base
            self._catalog_db_path = base / cat.local.catalog_db
            self._warehouse_path = base / cat.local.warehouse_dir

            self._base_dir.mkdir(parents=True, exist_ok=True)
            assert self._warehouse_path is not None
            self._warehouse_path.mkdir(parents=True, exist_ok=True)

    def _warehouse_uri(self) -> str:
        cat = self._settings.lakehouse
        if cat.mode == "local":
            assert self._warehouse_path is not None
            return f"file://{self._warehouse_path.absolute()}"
        assert cat.remote is not None
        wh = cat.remote.warehouse
        if "://" in wh:
            return wh
        return f"file://{Path(wh).expanduser().absolute()}"

    def _catalog_uri(self) -> str:
        cat = self._settings.lakehouse
        if cat.mode == "local":
            assert self._catalog_db_path is not None
            return f"sqlite:////{self._catalog_db_path.absolute()}"
        assert cat.remote is not None
        return cat.remote.uri

    def get_catalog(self) -> Catalog:
        if self._catalog is None:
            cat = self._settings.lakehouse
            props: dict[str, Any] = {
                "type": cat.type,
                "uri": self._catalog_uri(),
                "warehouse": self._warehouse_uri(),
                **(cat.properties or {}),
            }
            self._catalog = load_catalog(cat.name, **props)
        return self._catalog

    def write_table(
        self,
        df: pd.DataFrame,
        table_name: str,
        *,
        mode: str = "append",
        partition_by: list[str] | None = None,
    ) -> None:
        identifier = table_name
        if "." not in identifier:
            identifier = f"tvscreener.{identifier}"

        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        catalog = self.get_catalog()
        namespace = identifier.split(".")[0]
        with contextlib.suppress(Exception):
            catalog.create_namespace(namespace)

        try:
            table = catalog.load_table(identifier)
            with table.update_schema() as update:
                update.union_by_name(arrow_table.schema)

            if mode == "overwrite":
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r"Delete operation did not match any records",
                        category=UserWarning,
                        module=r"pyiceberg\..*",
                    )
                    if partition_by:
                        # Overwrite by the partitions present in the new data.
                        from pyiceberg.expressions import AlwaysFalse, And, In, IsNull, Or

                        filters = []
                        for col in partition_by:
                            col_vals = arrow_table.column(col).to_pylist()
                            raw_unique = list(dict.fromkeys(col_vals))
                            unique_vals = [v for v in raw_unique if v is not None]
                            has_null = None in raw_unique
                            col_filter = None
                            if unique_vals:
                                col_filter = In(col, unique_vals)  # type: ignore[call-arg,arg-type]
                            if has_null:
                                null_filter = IsNull(col)  # type: ignore[call-arg,arg-type]
                                col_filter = (
                                    Or(col_filter, null_filter) if col_filter else null_filter
                                )
                            if col_filter:
                                filters.append(col_filter)
                        if not filters:
                            table.overwrite(arrow_table, overwrite_filter=AlwaysFalse())
                        else:
                            final_filter = filters[0] if len(filters) == 1 else And(*filters)
                            table.overwrite(arrow_table, overwrite_filter=final_filter)
                    else:
                        table.overwrite(arrow_table)
                logger.info("Overwrote Iceberg table '%s' (%d rows)", identifier, len(arrow_table))
            else:
                table.append(arrow_table)
                logger.info("Appended %d rows to Iceberg table '%s'", len(arrow_table), identifier)
        except NoSuchTableError:
            catalog.create_table(identifier, schema=arrow_table.schema)
            table = catalog.load_table(identifier)
            if partition_by:
                with table.update_spec() as update:
                    for col in partition_by:
                        update.add_identity(col)
            table.append(arrow_table)
            logger.info("Created Iceberg table '%s' (%d rows)", identifier, len(arrow_table))

    def read_table_arrow(self, table_name: str) -> pa.Table:
        identifier = table_name
        if "." not in identifier:
            identifier = f"tvscreener.{identifier}"
        catalog = self.get_catalog()
        table = catalog.load_table(identifier)
        return table.scan().to_arrow()
