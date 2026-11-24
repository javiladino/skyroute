"""Tests de Silver bookings_scd2: U5-U8 y U21 (WAP al relanzar). Todo local, sin AWS."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from conftest import Lake
from jobs.bronze import ingest
from jobs.silver import bookings_scd2
from lib.checks import run_checks
from lib.wap import WapCheckError, list_branches

D0 = date(2026, 1, 1)
SILVER = "skyroute_dev_silver"

# (history_id, booking_id, status, dia relativo a D0, hora). history_id crece con changed_at.
VERSIONS = [
    (1, "B1", "pending", 0, "08:00:00"),
    (2, "B1", "confirmed", 0, "09:00:00"),
    (3, "B2", "pending", 0, "09:30:00"),
    (4, "B1", "cancelled", 1, "10:00:00"),
    (5, "B2", "confirmed", 2, "11:00:00"),
    (6, "B3", "pending", 3, "12:00:00"),
    (7, "B3", "confirmed", 5, "08:00:00"),
    (8, "B2", "cancelled", 5, "09:00:00"),
]


def day(n: int) -> str:
    return (D0 + timedelta(days=n)).isoformat()


def bookings_key(run_date: str) -> str:
    return f"landing/bookings/ingest_date={run_date}/part.json.gz"


def version_row(history_id, booking_id, status, run_date, hour, amount=100.0):
    stamp = f"{run_date}T{hour}Z"
    return {
        "history_id": history_id,
        "booking_id": booking_id,
        "customer_id": f"C-{booking_id}",
        "session_id": f"S-{booking_id}",
        "campaign_id": "CMP1",
        "origin": "CDG",
        "destination": "LHR",
        "travel_date": "2026-03-01",
        "status": status,
        "currency": "EUR",
        "amount": amount,
        "created_at": f"{day(0)}T08:00:00Z",
        "updated_at": stamp,
        "changed_at": stamp,
    }


def rows_for_day(n: int) -> list[dict]:
    return [
        version_row(h, b, s, day(n), t) for (h, b, s, offset, t) in VERSIONS if offset == n
    ]


def ingest_day(lake: Lake, run_date: str, rows: list[dict]) -> None:
    lake.write_landing(bookings_key(run_date), rows)
    assert ingest.main(lake.argv("bookings", run_date)) == 0


def seed_bronze(lake: Lake, days=range(6)) -> None:
    for n in days:
        ingest_day(lake, day(n), rows_for_day(n))


def silver_argv(lake: Lake, run_date: str, checks_dir=None) -> list[str]:
    argv = [
        "--run-date", run_date,
        "--catalog-name", lake.catalog,
        "--catalog-impl", "hadoop",
        "--warehouse", lake.warehouse,
        "--jars-packages", "none",
    ]  # fmt: skip
    if checks_dir is not None:
        argv += ["--checks-dir", str(checks_dir)]
    return argv


def run_scd2(lake: Lake, n: int, checks_dir=None) -> None:
    assert bookings_scd2.main(silver_argv(lake, day(n), checks_dir)) == 0


def scd2_rows(lake: Lake) -> list[dict]:
    table = lake.spark.table(f"{lake.catalog}.{SILVER}.bookings_scd2")
    return [r.asDict() for r in table.orderBy("booking_id", "history_id").collect()]


def scd2_table(lake: Lake) -> str:
    return f"{lake.catalog}.{SILVER}.bookings_scd2"


@pytest.fixture
def lake_b(spark, tmp_path):
    """Segundo lago aislado, para comparar con la ejecucion en orden."""
    return Lake(spark, tmp_path / "ordered")


def assert_integrity(rows: list[dict]) -> None:
    keys = [(r["booking_id"], r["history_id"]) for r in rows]
    assert len(keys) == len(set(keys))
    for booking in {r["booking_id"] for r in rows}:
        mine = [r for r in rows if r["booking_id"] == booking]
        assert sum(r["is_current"] for r in mine) == 1
    for r in rows:
        assert r["valid_to"] is None or r["valid_to"] >= r["valid_from"]
        assert r["is_current"] == (r["valid_to"] is None)


def test_u5_rerun_day_has_no_duplicates_and_one_current_per_booking(lake):
    seed_bronze(lake, days=range(2))
    run_scd2(lake, 0)
    first = scd2_rows(lake)
    assert len(first) == 3
    run_scd2(lake, 0)
    second = scd2_rows(lake)

    assert second == first
    assert_integrity(second)


def test_u6_rerun_d_after_d1_keeps_d1_version_current(lake):
    seed_bronze(lake, days=range(2))
    run_scd2(lake, 0)
    run_scd2(lake, 1)
    after_order = scd2_rows(lake)
    run_scd2(lake, 0)  # relanzar D despues de D+1
    rows = scd2_rows(lake)

    assert rows == after_order
    assert_integrity(rows)
    b1 = {r["history_id"]: r for r in rows if r["booking_id"] == "B1"}
    assert b1[4]["is_current"] is True and b1[4]["valid_to"] is None
    assert b1[2]["is_current"] is False and b1[2]["valid_to"] == b1[4]["valid_from"]
    assert b1[1]["valid_to"] == b1[2]["valid_from"]


def test_u7_same_changed_at_two_rows_tie_broken_by_history_id(lake):
    same = "10:00:00"
    ingest_day(
        lake,
        day(0),
        [
            version_row(11, "BX", "confirmed", day(0), same),
            version_row(10, "BX", "pending", day(0), same),
        ],
    )
    run_scd2(lake, 0)
    rows = scd2_rows(lake)

    assert [r["history_id"] for r in rows] == [10, 11]
    first, second = rows
    assert first["valid_from"] == second["valid_from"] == datetime(2026, 1, 1, 10, 0, 0)
    assert first["valid_to"] == second["valid_from"] and first["is_current"] is False
    assert second["valid_to"] is None and second["is_current"] is True
    assert_integrity(rows)


def test_u8_d_to_d5_then_rerun_d_equals_in_order(lake, lake_b):
    seed_bronze(lake)
    seed_bronze(lake_b)
    for n in range(6):
        run_scd2(lake, n)
        run_scd2(lake_b, n)
    run_scd2(lake, 0)

    rows = scd2_rows(lake)
    assert rows == scd2_rows(lake_b)
    assert len(rows) == len(VERSIONS)
    assert_integrity(rows)
    # Dia sin filas (D+4) y relanzado de un dia intermedio tampoco cambian nada.
    run_scd2(lake, 4)
    run_scd2(lake, 2)
    assert scd2_rows(lake) == rows


def test_fresh_lake_first_pass_out_of_order_equals_in_order(lake, lake_b):
    seed_bronze(lake)
    seed_bronze(lake_b)
    for n in range(6):
        run_scd2(lake, n)
    for n in (1, 0, 5, 3, 2, 4):  # lago nuevo: D+1 antes que D, y el resto desordenado
        run_scd2(lake_b, n)

    rows = scd2_rows(lake_b)
    assert rows == scd2_rows(lake)
    assert len(rows) == len(VERSIONS)
    assert_integrity(rows)


def typed_version(history_id: int, booking_id: str, status: str, valid_from: datetime):
    return (
        booking_id, history_id, f"C-{booking_id}", f"S-{booking_id}", "CMP1", "CDG", "LHR",
        date(2026, 3, 1), status, "EUR", Decimal("100.00"), valid_from, valid_from, valid_from,
    )  # fmt: skip


VERSION_SCHEMA = (
    "booking_id string, history_id bigint, customer_id string, session_id string, "
    "campaign_id string, origin string, destination string, travel_date date, "
    "status string, currency string, amount decimal(12,2), "
    "created_at timestamp, updated_at timestamp, valid_from timestamp"
)


def test_changed_at_tie_across_batches_orders_by_history_id_in_both_orders(lake):
    stamp = datetime(2026, 1, 1, 10, 0, 0)
    early = lake.spark.createDataFrame([typed_version(10, "BT", "pending", stamp)], VERSION_SCHEMA)
    late = lake.spark.createDataFrame([typed_version(11, "BT", "confirmed", stamp)], VERSION_SCHEMA)
    results = []
    for name, order in (("fwd", (early, late)), ("rev", (late, early))):
        target = f"{lake.catalog}.{SILVER}_{name}.bookings_scd2"
        lake.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake.catalog}.{SILVER}_{name}")
        lake.spark.sql(bookings_scd2.DDL.format(table=target))
        for batch in order:
            bookings_scd2.write_scd2(lake.spark, target, batch)
        rows = [r.asDict() for r in lake.spark.table(target).orderBy("history_id").collect()]
        assert_integrity(rows)
        assert [(r["history_id"], r["is_current"]) for r in rows] == [(10, False), (11, True)]
        assert rows[0]["valid_to"] == stamp
        results.append(rows)
    assert results[0] == results[1]


def test_batch_with_changed_at_outside_the_day_fails_before_writing(lake):
    ingest_day(lake, day(0), [version_row(1, "BO", "pending", day(1), "08:00:00")])

    with pytest.raises(ValueError, match="fuera de"):
        run_scd2(lake, 0)
    table = lake.spark.table(scd2_table(lake))
    assert table.count() == 0
    assert list_branches(lake.spark, scd2_table(lake)) == []  # sin rama run_<D> ni snapshot


def test_current_amount_rounds_half_even_and_checks_reject_two_current(lake):
    frame = lake.spark.createDataFrame(
        [("B1", 10, True), ("B1", 11, True), ("B2", 12, False), ("B2", 13, True)],
        "booking_id string, history_id bigint, is_current boolean",
    )
    shipped = (bookings_scd2.DEFAULT_CHECKS_DIR / "bookings_scd2.yaml").read_text()
    rules = "\n".join(
        line for line in shipped.splitlines() if line.startswith("checks:") or "where:" in line
    )
    rules_found = {f.rule for f in run_checks(frame, rules)}
    assert "unique:booking_id[is_current]" in rules_found

    amounts = lake.spark.createDataFrame([("0.125",), ("0.135",), ("2.5",)], "amount string")
    rounded = amounts.select(bookings_scd2.amount_decimal().alias("a")).collect()
    assert [str(r["a"]) for r in rounded] == ["0.12", "0.14", "2.50"]


def test_u21_wap_rerun_publishes_and_leaves_no_branch(lake, lake_b):
    seed_bronze(lake, days=range(2))
    seed_bronze(lake_b, days=range(2))
    run_scd2(lake, 0)
    run_scd2(lake, 1)
    run_scd2(lake, 0)  # el fast_forward del relanzamiento no falla
    run_scd2(lake_b, 0)
    run_scd2(lake_b, 1)

    assert list_branches(lake.spark, scd2_table(lake)) == ["main"]
    assert scd2_rows(lake) == scd2_rows(lake_b)


def test_u21_failing_check_keeps_branch_and_next_run_publishes(lake, lake_b, tmp_path):
    seed_bronze(lake, days=range(2))
    seed_bronze(lake_b, days=range(2))
    run_scd2(lake, 0)
    published = scd2_rows(lake)

    bad = tmp_path / "bad_checks"
    bad.mkdir()
    (bad / "bookings_scd2.yaml").write_text("checks:\n  - {type: min_rows, value: 1000}\n")
    with pytest.raises(WapCheckError):
        run_scd2(lake, 1, checks_dir=bad)

    assert scd2_rows(lake) == published  # main no cambio
    assert list_branches(lake.spark, scd2_table(lake)) == ["main", f"run_{day(1)}"]

    run_scd2(lake, 1)  # la siguiente ejecucion borra la rama y publica
    run_scd2(lake_b, 0)
    run_scd2(lake_b, 1)
    assert list_branches(lake.spark, scd2_table(lake)) == ["main"]
    assert scd2_rows(lake) == scd2_rows(lake_b)
    assert_integrity(scd2_rows(lake))


def test_route_and_travel_date_enter_scd2_and_row_hash(lake):
    ingest_day(lake, day(0), rows_for_day(0))
    run_scd2(lake, 0)
    rows = scd2_rows(lake)
    assert {(r["origin"], r["destination"], r["travel_date"]) for r in rows} == {
        ("CDG", "LHR", date(2026, 3, 1))
    }
    assert {"origin", "destination", "travel_date"} <= set(bookings_scd2.HASH_COLUMNS)
