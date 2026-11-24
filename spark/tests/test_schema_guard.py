"""Tests del guard schema_mismatch (lib/schema_guard.py). Todo local, sin AWS."""

import pytest
from jobs.silver import bookings_current, bookings_eur, bookings_scd2
from lib.schema_guard import SchemaMismatch, ddl_columns, require_columns
from lib.wap import list_branches
from test_bookings_scd2 import SILVER, day, seed_bronze, silver_argv

NEW_BOOKING_COLUMNS = ("origin", "destination", "travel_date")


def old_ddl(ddl: str, dropped=NEW_BOOKING_COLUMNS) -> str:
    """El DDL anterior a la Fase 4: sin las columnas nuevas."""
    keep = [line for line in ddl.splitlines() if line.strip().split(" ")[0] not in dropped]
    return "\n".join(keep)


def create_old_table(lake, job, name: str) -> str:
    target = f"{lake.catalog}.{SILVER}.{name}"
    lake.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake.catalog}.{SILVER}")
    lake.spark.sql(old_ddl(job.DDL).format(table=target))
    return target


def test_ddl_columns_reads_names_in_order():
    names = ddl_columns(bookings_scd2.DDL)
    assert names[:3] == ["booking_id", "history_id", "customer_id"]
    assert set(NEW_BOOKING_COLUMNS) <= set(names)
    assert names[-1] == "row_hash"
    assert "format" not in " ".join(names)  # TBLPROPERTIES no cuenta


def test_require_columns_passes_and_lists_missing(lake):
    target = create_old_table(lake, bookings_current, "guard_probe")
    require_columns(lake.spark, target, ["booking_id", "AMOUNT"])  # sin distinguir mayusculas
    with pytest.raises(SchemaMismatch, match="schema_mismatch") as err:
        require_columns(lake.spark, target, ddl_columns(bookings_current.DDL))
    for column in NEW_BOOKING_COLUMNS:
        assert column in str(err.value)


@pytest.mark.parametrize(
    ("job", "name"),
    [
        (bookings_scd2, "bookings_scd2"),
        (bookings_current, "bookings_current"),
        (bookings_eur, "bookings_eur"),
    ],
)
def test_schema_mismatch_booking_jobs(lake, job, name):
    seed_bronze(lake, days=range(1))
    target = create_old_table(lake, job, name)

    with pytest.raises(SchemaMismatch, match="schema_mismatch") as err:
        job.main(silver_argv(lake, day(0)))
    assert "travel_date" in str(err.value)
    assert lake.spark.table(target).count() == 0
    assert list_branches(lake.spark, target) == []  # sin rama run_<D> ni snapshot
