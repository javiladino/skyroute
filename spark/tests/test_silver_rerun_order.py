"""Tests de independencia del orden sobre las seis tablas Silver: U18 y U22. Todo local, sin AWS."""

from conftest import Lake
from jobs.silver import bookings_current as current_job
from jobs.silver import bookings_eur, bookings_scd2, fx_daily
from lib.wap import list_branches
from test_bookings_scd2 import SILVER, day, seed_bronze, silver_argv
from test_silver_events import hmac_key, run_events  # noqa: F401
from test_silver_fx import fx_rows, ingest_fx
from test_silver_sessions import ingest_world, run_sessions

TABLES = {
    "events": ("event_id",),
    "sessions": ("session_key",),
    "bookings_scd2": ("booking_id", "history_id"),
    "bookings_current": ("booking_id",),
    "fx_daily": ("fx_date", "currency"),
    "bookings_eur": ("booking_id",),
}


def seed_world(lake: Lake, days) -> None:
    seed_bronze(lake, days=days)
    for n in days:
        ingest_fx(lake, day(n), fx_rows(day(n), day(n), {"USD": 1.1 + n / 100, "GBP": 0.85}))
    ingest_world(lake, days)


def run_day(lake: Lake, n: int) -> None:
    """Las seis tablas Silver de un dia; events antes que sessions."""
    argv = silver_argv(lake, day(n))
    assert fx_daily.main(argv) == 0
    assert bookings_scd2.main(argv) == 0
    assert current_job.main(argv) == 0
    assert bookings_eur.main(argv) == 0
    run_events(lake, day(n))
    run_sessions(lake, n)


def snapshot(lake: Lake) -> dict[str, list[dict]]:
    out = {}
    for name, order in TABLES.items():
        table = f"{lake.catalog}.{SILVER}.{name}"
        out[name] = [r.asDict() for r in lake.spark.table(table).orderBy(*order).collect()]
        assert list_branches(lake.spark, table) == ["main"]
    return out


def assert_all_populated(rows: dict[str, list[dict]]) -> None:
    for name, table_rows in rows.items():
        assert table_rows, f"{name} vacia: la comparacion no probaria nada"


def test_u18_d_to_d5_then_rerun_d_equals_in_order(lake):
    days = range(6)
    seed_world(lake, days)
    for n in days:
        run_day(lake, n)
    in_order = snapshot(lake)
    assert_all_populated(in_order)

    run_day(lake, 0)  # relanzar D despues de D+5
    assert snapshot(lake) == in_order


def test_u22_first_pass_permutation_equals_in_order(lake, spark, tmp_path):
    ordered = Lake(spark, tmp_path / "ordered")
    days = range(3)
    seed_world(lake, days)
    seed_world(ordered, days)
    for n in days:
        run_day(ordered, n)
    for n in (1, 0, 2):  # D+1, D, D+2 sobre lagos vacios
        run_day(lake, n)

    expected = snapshot(ordered)
    assert_all_populated(expected)
    assert snapshot(lake) == expected
