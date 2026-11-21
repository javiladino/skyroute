"""Tests de Silver bookings_current: U9. Todo local, sin AWS."""

from jobs.silver import bookings_current
from test_bookings_scd2 import SILVER, lake_b, seed_bronze, silver_argv  # noqa: F401
from test_bookings_scd2 import day as day_str


def run_current(lake, n: int) -> None:
    assert bookings_current.main(silver_argv(lake, day_str(n))) == 0


def current_rows(lake) -> list[dict]:
    table = lake.spark.table(f"{lake.catalog}.{SILVER}.bookings_current")
    return [r.asDict() for r in table.orderBy("booking_id").collect()]


def test_u9_d_to_d5_then_rerun_d_keeps_latest_version(lake, lake_b):  # noqa: F811
    seed_bronze(lake)
    seed_bronze(lake_b)
    for n in range(6):
        run_current(lake, n)
        run_current(lake_b, n)
    run_current(lake, 0)  # relanzar D despues de D+5

    rows = current_rows(lake)
    assert rows == current_rows(lake_b)
    assert {r["booking_id"]: (r["history_id"], r["status"]) for r in rows} == {
        "B1": (4, "cancelled"),
        "B2": (8, "cancelled"),
        "B3": (7, "confirmed"),
    }


def test_u9_fresh_lake_first_pass_out_of_order_equals_in_order(lake, lake_b):  # noqa: F811
    seed_bronze(lake)
    seed_bronze(lake_b)
    for n in range(6):
        run_current(lake, n)
    for n in (5, 1, 3, 0, 4, 2):  # lago nuevo: primera pasada fuera de orden
        run_current(lake_b, n)

    assert current_rows(lake_b) == current_rows(lake)
    assert len(current_rows(lake_b)) == 3
