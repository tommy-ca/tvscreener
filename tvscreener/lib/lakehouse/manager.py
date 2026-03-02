import contextlib
import logging
from pathlib import Path
from typing import Any

import narwhals as nw
import pyarrow as pa
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.exceptions import NoSuchTableError

logger = logging.getLogger(__name__)


class LakehouseManager:
    """Unified manager for Iceberg catalog and storage operations.

    Flattens the previous multi-class hierarchy into a single entry point.
    """

    def __init__(self) -> None:
        self.base_dir = Path.home() / ".tvscreener" / "lakehouse"
        self.catalog_db_path = self.base_dir / "catalog.db"
        self.warehouse_path = self.base_dir / "warehouse"

        # Provision directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.warehouse_path.mkdir(parents=True, exist_ok=True)

        # SQL Catalog URI: sqlite:////abs/path/to/db
        self.uri = f"sqlite:////{self.catalog_db_path.absolute()}"
        self._catalog: Catalog | None = None

    def get_catalog(self) -> Catalog:
        """Loads and returns the Iceberg catalog instance."""
        if self._catalog is None:
            self._catalog = load_catalog(
                "local",
                **{
                    "type": "sql",
                    "uri": self.uri,
                    "warehouse": f"file://{self.warehouse_path.absolute()}",
                },
            )
        return self._catalog

    def write_table(
        self,
        df_native: Any,
        table_name: str,
        mode: str = "append",
        partition_by: list[str] | None = None,
    ) -> None:
        """Write a native dataframe to an Iceberg table with schema evolution."""
        nw_df = nw.from_native(df_native)
        arrow_table = self._prepare_arrow(nw_df)

        catalog = self.get_catalog()
        # Use dots for namespaces if provided, otherwise default to "default"
        identifier = table_name if "." in table_name else f"default.{table_name}"

        # Ensure namespace exists
        if "." in identifier:
            namespace = identifier.split(".")[0]
            with contextlib.suppress(Exception):
                catalog.create_namespace(namespace)

        try:
            table = catalog.load_table(identifier)
            # Schema evolution
            with table.update_schema() as update:
                update.union_by_name(arrow_table.schema)

            if mode == "overwrite":
                table.overwrite(arrow_table)
                logger.info("Overwrote Iceberg table '%s' (%d rows)", identifier, len(arrow_table))
            else:
                table.append(arrow_table)
                logger.info("Appended %d rows to Iceberg table '%s'", len(arrow_table), identifier)
        except NoSuchTableError:
            # Create table if it doesn't exist
            catalog.create_table(identifier, schema=arrow_table.schema)
            table = catalog.load_table(identifier)

            if partition_by:
                with table.update_spec() as update:
                    for col in partition_by:
                        update.add_identity_field(col)

            table.append(arrow_table)
            logger.info("Created Iceberg table '%s' (%d rows)", identifier, len(arrow_table))

    def _prepare_arrow(self, nw_df: nw.DataFrame) -> pa.Table:
        """Cast datetime64[ns] to [us] for Iceberg compatibility."""
        datetime_cols = [
            col for col, dtype in nw_df.schema.items() if isinstance(dtype, nw.Datetime)
        ]
        if datetime_cols:
            nw_df = nw_df.with_columns(
                [nw.col(col).cast(nw.Datetime(time_unit="us")) for col in datetime_cols]
            )
        return nw_df.to_arrow()

    def maintenance(self, table_name: str, operation: str, **kwargs: Any) -> None:
        """Perform table maintenance (expire snapshots, remove orphans)."""
        from datetime import datetime, timedelta, timezone

        from pyiceberg.table.maintenance import MaintenanceTable

        catalog = self.get_catalog()
        table = catalog.load_table(table_name)
        m = MaintenanceTable(table)

        if operation == "expire_snapshots":
            days = kwargs.get("older_than_days", 7)
            ts = datetime.now(timezone.utc) - timedelta(days=days)
            m.expire_snapshots().older_than(ts).commit()
        elif operation == "remove_orphan_files":
            m.remove_orphan_files().commit()
        elif operation == "compact":
            logger.info("Compaction requested for %s (Hook)", table_name)


def get_manager() -> LakehouseManager:
    """Singleton provider for LakehouseManager."""
    if not hasattr(get_manager, "_instance"):
        get_manager._instance = LakehouseManager()
    return get_manager._instance


def write_iceberg(
    df: Any, table_name: str, mode: str = "append", partition_by: list[str] | None = None
) -> None:
    """Legacy helper for write_iceberg."""
    get_manager().write_table(df, table_name, mode=mode, partition_by=partition_by)
