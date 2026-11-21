"""Tests de Silver FX: U10-U12 (fx_daily y bookings_eur). Todo local, sin AWS."""

from datetime import date
from decimal import Decimal

import pytest
from conftest import Lake
from jobs.bronze import ingest
from jobs.silver import bookings_eur, fx_daily
from lib.wap import WapCheckError, list_branches
from test_bookings_scd2 import SILVER, ingest_day, silver_argv, version_row

FRIDAY = date(2026, 1, 2)  # el 3 es sabado y el 4 domingo


def fx_key(run_date: str) -> str:
    return f"landing/fx/ingest_date={run_date}/part.json.gz"


def fx_rows(run_date: str, rate_date: str, rates: dict) -> list[dict]:
    return [
        {"base": "EUR", "currency": c, "rate": r, "rate_date": rate_date, "fx_date": run_date}
        for c, r in sorted(rates.items())
    ]


def ingest_fx(lake: Lake, run_date: str, rows: list[dict]) -> None:
    lake.write_landing(fx_key(run_date), rows)
    assert ingest.main(lake.argv("fx", run_date)) == 0


def run_fx(lake: Lake, run_date: str, checks_dir=None) -> None:
    assert fx_daily.main(silver_argv(lake, run_date, checks_dir)) == 0


def run_eur(lake: Lake, run_date: str) -> None:
    assert bookings_eur.main(silver_argv(lake, run_date)) == 0


def fx_table(lake: Lake) -> str:
    return f"{lake.catalog}.{SILVER}.fx_daily"


def eur_table(lake: Lake) -> str:
    return f"{lake.catalog}.{SILVER}.bookings_eur"


def fx_daily_rows(lake: Lake) -> list[dict]:
    frame = lake.spark.table(fx_table(lake)).orderBy("fx_date", "currency")
    return [r.asDict() for r in frame.collect()]


def eur_rows(lake: Lake) -> list[dict]:
    frame = lake.spark.table(eur_table(lake)).orderBy("booking_id")
    return [r.asDict() for r in frame.collect()]


def booking(history_id, booking_id, currency, amount, created_at):
    row = version_row(history_id, booking_id, "confirmed", created_at[:10], "12:00:00", amount)
    row["currency"] = currency
    row["created_at"] = created_at
    return row


def test_u10_weekend_without_publication_carries_friday(lake):
    friday, saturday = FRIDAY.isoformat(), "2026-01-03"
    rates = {"USD": 1.0850, "GBP": 0.8600}
    ingest_fx(lake, friday, fx_rows(friday, friday, rates))
    # el sabado el BCE no publica: landing lleva la ultima publicacion con su rate_date real
    ingest_fx(lake, saturday, fx_rows(saturday, friday, rates))
    run_fx(lake, friday)
    run_fx(lake, saturday)

    rows = fx_daily_rows(lake)
    fri = {r["currency"]: r for r in rows if r["fx_date"] == FRIDAY}
    sat = {r["currency"]: r for r in rows if r["fx_date"] == date(2026, 1, 3)}
    assert set(sat) == {"USD", "GBP"}
    for ccy in sat:
        assert sat[ccy]["rate_per_eur"] == fri[ccy]["rate_per_eur"]
        assert sat[ccy]["source_date"] == FRIDAY  # dia habil de origen, no el sabado
    assert fri["USD"]["rate_per_eur"] == Decimal("1.085000")

    run_fx(lake, saturday)  # relanzar no duplica
    run_fx(lake, friday)
    assert fx_daily_rows(lake) == rows
    assert list_branches(lake.spark, fx_table(lake)) == ["main"]


def test_u11_no_rate_available_fails_check_and_does_not_publish(lake, tmp_path):
    day1, day2 = "2026-01-05", "2026-01-06"
    ingest_fx(lake, day1, fx_rows(day1, day1, {"USD": 1.1}))
    ingest_fx(lake, day2, [])  # archivo valido sin tipos: no hay tipo que arrastrar
    run_fx(lake, day1)
    published = fx_daily_rows(lake)

    with pytest.raises(WapCheckError) as err:
        run_fx(lake, day2)
    assert [f.rule for f in err.value.failures] == ["fx_rate_available"]
    assert fx_daily_rows(lake) == published  # main no cambio
    assert list_branches(lake.spark, fx_table(lake)) == ["main", f"run_{day2}"]

    # llega el tipo de day2 y se relanza: publica, borra la rama conservada y deja solo main
    ingest_fx(lake, day2, fx_rows(day2, day2, {"USD": 1.2}))
    run_fx(lake, day2)
    assert list_branches(lake.spark, fx_table(lake)) == ["main"]
    assert [(r["fx_date"], r["rate_per_eur"]) for r in fx_daily_rows(lake)] == [
        (date(2026, 1, 5), Decimal("1.100000")),
        (date(2026, 1, 6), Decimal("1.200000")),
    ]


def test_fx_conflicting_duplicates_fail_instead_of_picking_one(lake):
    day = "2026-01-05"
    rows = fx_rows(day, day, {"USD": 1.1}) + fx_rows(day, "2026-01-02", {"USD": 1.2})
    ingest_fx(lake, day, rows)

    with pytest.raises(WapCheckError) as err:
        run_fx(lake, day)
    assert [f.rule for f in err.value.failures] == ["fx_conflicting_rates"]
    assert fx_daily_rows(lake) == []


def test_u11_bookings_eur_without_rate_for_created_day_is_not_published(lake):
    day1 = "2026-01-05"
    ingest_fx(lake, day1, fx_rows(day1, day1, {"USD": 1.1}))
    run_fx(lake, day1)
    # created_at del 2026-01-06: fx_daily no tiene ese dia
    ingest_day(lake, day1, [booking(1, "B1", "USD", 10.0, "2026-01-06T09:00:00Z")])

    with pytest.raises(WapCheckError) as err:
        run_eur(lake, day1)
    assert any(f.rule == "not_null:fx_rate_applied" for f in err.value.failures)
    assert eur_rows(lake) == []
    # tabla nunca publicada: aun no tiene ref `main`, solo la rama conservada
    assert list_branches(lake.spark, eur_table(lake)) == [f"run_{day1}"]


def test_u12_bookings_eur_uses_created_at_rate_and_half_even(lake):
    d0, d1 = "2026-01-05", "2026-01-06"
    ingest_fx(lake, d0, fx_rows(d0, d0, {"USD": 1.25, "XXX": 2.0}))
    ingest_fx(lake, d1, fx_rows(d1, d1, {"USD": 2.0, "XXX": 2.0}))
    run_fx(lake, d0)
    run_fx(lake, d1)
    # Se ingieren el d1, pero created_at decide el tipo; dos versiones de B1 -> una fila.
    ingest_day(
        lake,
        d1,
        [
            booking(1, "B1", "USD", 100.0, "2026-01-05T23:59:59Z"),  # tipo del d0: 1,25
            booking(2, "B1", "USD", 100.0, "2026-01-05T23:59:59Z"),
            booking(3, "B2", "USD", 100.0, "2026-01-06T00:00:00Z"),  # tipo del d1: 2,0
            booking(4, "B3", "XXX", 0.25, "2026-01-06T10:00:00Z"),  # 0,125 -> 0,12 (par)
            booking(5, "B4", "XXX", 0.35, "2026-01-06T10:00:00Z"),  # 0,175 -> 0,18 (par)
            booking(6, "B5", "XXX", 0.45, "2026-01-06T10:00:00Z"),  # 0,225 -> 0,22 (par)
            booking(7, "B6", "EUR", 12.34, "2026-01-06T10:00:00Z"),  # EUR: tipo 1
        ],
    )
    run_eur(lake, d1)

    rows = {r["booking_id"]: r for r in eur_rows(lake)}
    assert set(rows) == {"B1", "B2", "B3", "B4", "B5", "B6"}
    expected = {
        "B1": ("USD", Decimal("1.250000"), Decimal("80.00")),
        "B2": ("USD", Decimal("2.000000"), Decimal("50.00")),
        "B3": ("XXX", Decimal("2.000000"), Decimal("0.12")),
        "B4": ("XXX", Decimal("2.000000"), Decimal("0.18")),
        "B5": ("XXX", Decimal("2.000000"), Decimal("0.22")),
        "B6": ("EUR", Decimal("1.000000"), Decimal("12.34")),
    }
    for booking_id, (currency, rate, eur) in expected.items():
        row = rows[booking_id]
        assert (row["currency"], row["fx_rate_applied"], row["amount_eur"]) == (currency, rate, eur)
    assert rows["B3"]["amount"] == Decimal("0.25")

    before = eur_rows(lake)
    run_eur(lake, d1)  # relanzar: igual fila a fila
    assert eur_rows(lake) == before
    assert list_branches(lake.spark, eur_table(lake)) == ["main"]


def test_u12_rerun_out_of_order_equals_in_order(lake, spark, tmp_path):
    other = Lake(spark, tmp_path / "ordered")
    days = ["2026-01-05", "2026-01-06"]
    for lk in (lake, other):
        for n, d in enumerate(days):
            ingest_fx(lk, d, fx_rows(d, d, {"USD": 1.0 + n}))
        ingest_day(lk, days[0], [booking(1, "B1", "USD", 10.0, "2026-01-05T08:00:00Z")])
        ingest_day(lk, days[1], [booking(2, "B2", "USD", 10.0, "2026-01-06T08:00:00Z")])
    for d in days:
        run_fx(other, d)
        run_eur(other, d)
    for d in (days[1], days[0], days[1]):  # primera pasada fuera de orden y relanzado
        run_fx(lake, d)
    for d in (days[1], days[0], days[0]):
        run_eur(lake, d)

    assert fx_daily_rows(lake) == fx_daily_rows(other)
    assert eur_rows(lake) == eur_rows(other)


def test_u12_amount_eur_matches_decimal_half_even_near_ties(lake):
    from decimal import ROUND_HALF_EVEN, getcontext

    getcontext().prec = 60
    day_ = "2026-01-05"
    cases = [  # (importe, tipo): cocientes cerca de un empate y empates exactos
        ("14.25", "7.002457"),
        ("15.02", "7.002331"),
        ("16.84", "7.002079"),
        ("0.25", "2.000000"),
        ("0.35", "2.000000"),
        ("0.45", "2.000000"),
    ]
    codes = [f"X{n}" for n in range(len(cases))]
    rates = {code: float(rate) for code, (_, rate) in zip(codes, cases, strict=True)}
    ingest_fx(lake, day_, fx_rows(day_, day_, rates))
    run_fx(lake, day_)
    ingest_day(
        lake,
        day_,
        [
            booking(n + 1, f"B{n}", code, float(amount), "2026-01-05T10:00:00Z")
            for n, (code, (amount, _)) in enumerate(zip(codes, cases, strict=True))
        ],
    )
    run_eur(lake, day_)

    rows = {r["booking_id"]: r for r in eur_rows(lake)}
    for n, (amount, rate) in enumerate(cases):
        exact = Decimal(amount) / Decimal(rate)
        assert rows[f"B{n}"]["amount_eur"] == exact.quantize(Decimal("0.01"), ROUND_HALF_EVEN)


def test_u12_bookings_eur_out_of_order_rerun_keeps_newest_version(lake):
    d0, d1 = "2026-01-05", "2026-01-06"
    ingest_fx(lake, d0, fx_rows(d0, d0, {"USD": 2.0}))
    ingest_fx(lake, d1, fx_rows(d1, d1, {"USD": 2.0}))
    run_fx(lake, d0)
    run_fx(lake, d1)
    old = booking(1, "B1", "USD", 100.0, "2026-01-05T08:00:00Z")  # changed_at 01-05T12:00
    new = {**old, "history_id": 2, "amount": 200.0, "changed_at": "2026-01-06T09:00:00Z"}
    ingest_day(lake, d0, [old])
    ingest_day(lake, d1, [new])

    run_eur(lake, d1)
    run_eur(lake, d0)  # D-1 tras D: la version vieja no sobrescribe a la nueva
    run_eur(lake, d1)

    (row,) = eur_rows(lake)
    assert (row["history_id"], row["amount"], row["amount_eur"]) == (
        2,
        Decimal("200.00"),
        Decimal("100.00"),
    )
    assert list_branches(lake.spark, eur_table(lake)) == ["main"]
