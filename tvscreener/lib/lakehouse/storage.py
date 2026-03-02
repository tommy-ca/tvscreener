import logging
from typing import Any

import narwhals as nw
import pyarrow as pa
from pyiceberg.exceptions import NoSuchTableError

from tvscreener.lib.lakehouse import get_catalog

logger = logging.getLogger(__name__)


class IcebergStorage:
    """Iceberg storage backend for exporting dataframes."""

    def __init__(self) -> None:
        self.catalog = get_catalog()

    def write(
        self,
        df_native: Any,
        table_name: str,
        mode: str = "append",
        partition_by: list[str] | None = None,
    ) -> None:
        """Write a native dataframe to an Iceberg table with schema evolution.

        Args:
            df_native: The native dataframe to write.
            table_name: The name of the table to write to.
            mode: The write mode, either "append" or "overwrite".
                  "overwrite" performs a dynamic partition overwrite if the table is partitioned.
            partition_by: Optional list of columns to partition by if the table is created.
        """
        nw_df = nw.from_native(df_native)
        arrow_table = prepare_arrow(nw_df)

        # Use dots for namespaces if provided, otherwise default to "default"
        identifier = table_name if "." in table_name else f"default.{table_name}"

        # Ensure namespace exists
        if "." in identifier:
            namespace = identifier.split(".")[0]
            import contextlib

            with contextlib.suppress(Exception):
                self.catalog.create_namespace(namespace)

        try:
            table = self.catalog.load_table(identifier)
            # Schema evolution: Update table schema to include any new columns from the current dataframe
            # PyIceberg's update_schema().union_by_name(new_schema) handles this
            with table.update_schema() as update:
                update.union_by_name(arrow_table.schema)

            if mode == "overwrite":
                table.overwrite(arrow_table)
                logger.info(
                    "Overwrote data in Iceberg table '%s' (%d rows)", identifier, len(arrow_table)
                )
            else:
                table.append(arrow_table)
                logger.info("Appended %d rows to Iceberg table '%s'", len(arrow_table), identifier)
        except NoSuchTableError:
            # Create table if it doesn't exist
            self.catalog.create_table(identifier, schema=arrow_table.schema)
            table = self.catalog.load_table(identifier)

            if partition_by:
                with table.update_spec() as update:
                    for col in partition_by:
                        update.add_identity_field(col)

            table.append(arrow_table)
            logger.info(
                "Created Iceberg table '%s' and inserted %d rows", identifier, len(arrow_table)
            )


def prepare_arrow(nw_df: nw.DataFrame) -> pa.Table:
    """Cast all datetime64[ns] columns to datetime64[us] before converting to Arrow.

    Iceberg does not support nanosecond precision.
    """
    # Identify datetime columns using Narwhals schema
    datetime_cols = [col for col, dtype in nw_df.schema.items() if isinstance(dtype, nw.Datetime)]

    if datetime_cols:
        # Cast each datetime column to microsecond precision
        nw_df = nw_df.with_columns(
            [nw.col(col).cast(nw.Datetime(time_unit="us")) for col in datetime_cols]
        )

    return nw_df.to_arrow()


def write_iceberg(
    df_native: Any, table_name: str, mode: str = "append", partition_by: list[str] | None = None
) -> None:
    """Helper to write a dataframe to an Iceberg table."""
    storage = IcebergStorage()
    storage.write(df_native, table_name, mode=mode, partition_by=partition_by)
