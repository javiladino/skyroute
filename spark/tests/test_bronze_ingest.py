"""Tests de Bronze generico (U1-U4) y de los helpers WAP/checks. Todo local, sin AWS."""

import gzip
import hashlib
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from conftest import Lake
from jobs.bronze import ingest
from lib.args import parse_args
from lib.checks import run_checks
from lib.wap import WapCheckError, list_branches, run_wap

# Generadores reales (solo lectura): los tests de esquema ingestan sus bytes tal cual.
GENERATORS = Path(__file__).resolve().parents[2] / "generators"
if str(GENERATORS) not in sys.path:
    sys.path.insert(0, str(GENERATORS))

D = "2026-01-01"
D1 = "2026-01-02"


def clickstream_key(day: str, slot: int) -> str:
    return f"landing/clickstream/ingest_date={day}/slot={slot:02d}/part.json.gz"


def daily_key(source: str, day: str) -> str:
    return f"landing/{source}/ingest_date={day}/part.json.gz"


def ts(day: str, hour: int, minute: int) -> datetime:
    y, m, d = map(int, day.split("-"))
    # collect() devuelve datetime naive en la zona del proceso; conftest fija TZ=UTC.
    return datetime(y, m, d, hour, minute)


def batch_id(run_date: str, source_file: str) -> str:
    return hashlib.sha256(f"{run_date}|{source_file}".encode()).hexdigest()


def seed_clickstream(lake, day=D, n_per_slot=2):
    for slot in (0, 5, 95):
        rows = [
            {"event_id": f"E{slot:02d}{i}", "email": f"u{i}@example.com", "event_type": "view"}
            for i in range(n_per_slot)
        ]
        lake.write_landing(clickstream_key(day, slot), rows)


def test_clickstream_technical_columns_from_run_date_and_slot(lake):
    seed_clickstream(lake)
    assert ingest.main(lake.argv("clickstream", D)) == 0

    rows = lake.rows("clickstream", "event_id")
    assert len(rows) == 6
    by_slot = {}
    for row in rows:
        slot = int(row["_source_file"].split("slot=")[1][:2])
        by_slot.setdefault(slot, []).append(row)
        assert row["_source_file"] == clickstream_key(D, slot)
        assert row["_batch_id"] == batch_id(D, clickstream_key(D, slot))
        assert row["_ingest_date"].isoformat() == D
        assert row["email"].endswith("@example.com")  # el payload llega integro
    assert by_slot[0][0]["_ingested_at"] == ts(D, 0, 0)
    assert by_slot[5][0]["_ingested_at"] == ts(D, 1, 15)
    assert by_slot[95][0]["_ingested_at"] == ts(D, 23, 45)


@pytest.mark.parametrize(
    ("source", "payload"),
    [
        ("bookings", {"history_id": 1, "booking_id": "B1", "status": "confirmed", "amount": 10.5}),
        ("fx", {"currency": "USD", "rate": 1.1, "fx_date": "2026-01-01"}),
    ],
)
def test_daily_sources_use_slot_zero(lake, source, payload):
    lake.write_landing(daily_key(source, D), [payload, {**payload, "currency": "GBP"}])
    assert ingest.main(lake.argv(source, D)) == 0

    rows = lake.spark.table(lake.table(source)).collect()
    assert len(rows) == 2
    for row in rows:
        assert row["_ingested_at"] == ts(D, 0, 0)
        assert row["_source_file"] == daily_key(source, D)
        assert row["_batch_id"] == batch_id(D, daily_key(source, D))
        assert row["_ingest_date"].isoformat() == D


def test_rerun_same_day_gives_same_table_and_replaces_partition(lake):
    seed_clickstream(lake, D)
    seed_clickstream(lake, D1, n_per_slot=1)
    ingest.main(lake.argv("clickstream", D))
    ingest.main(lake.argv("clickstream", D1))
    first = lake.rows("clickstream", "event_id")
    day1_before = [r for r in first if r["_ingest_date"].isoformat() == D1]
    time.sleep(1.1)
    ingest.main(lake.argv("clickstream", D))
    assert lake.rows("clickstream", "event_id") == first  # U1: igual fila a fila, sin duplicar

    # Reemplazo de particion: D cambia en landing; D1 queda intacta.
    lake.write_landing(clickstream_key(D, 0), [{"event_id": "EONLY", "email": "z@example.com"}])
    ingest.main(lake.argv("clickstream", D))
    after = lake.rows("clickstream", "event_id")
    day0 = [r for r in after if r["_ingest_date"].isoformat() == D]
    day1 = [r for r in after if r["_ingest_date"].isoformat() == D1]
    assert sorted(r["event_id"] for r in day0) == sorted(
        ["EONLY"] + [f"E05{i}" for i in range(2)] + [f"E95{i}" for i in range(2)]
    )
    assert day1 == day1_before


def test_missing_input_fails_and_keeps_previous_partition(lake):
    seed_clickstream(lake, D)
    ingest.main(lake.argv("clickstream", D))
    before = lake.rows("clickstream", "event_id")

    with pytest.raises(ingest.NoInputFiles):
        ingest.main(lake.argv("clickstream", D1))  # no hay landing para D1
    assert lake.rows("clickstream", "event_id") == before


def test_technical_columns_do_not_depend_on_the_clock(lake):
    lake.write_landing(daily_key("fx", D), [{"currency": "USD", "rate": 1.1}])
    ingest.main(lake.argv("fx", D))
    first = lake.rows("fx", "currency")
    time.sleep(1.1)  # otro instante de reloj: las columnas tecnicas no cambian
    ingest.main(lake.argv("fx", D))
    second = lake.rows("fx", "currency")
    assert first == second
    assert second[0]["_ingested_at"] == ts(D, 0, 0)  # run_date, no "ahora"


def test_empty_daily_file_clears_the_partition(lake):
    lake.write_landing(daily_key("bookings", D), [{"history_id": 1, "booking_id": "B1"}])
    lake.write_landing(daily_key("bookings", D1), [{"history_id": 2, "booking_id": "B2"}])
    ingest.main(lake.argv("bookings", D))
    ingest.main(lake.argv("bookings", D1))
    assert lake.spark.table(lake.table("bookings")).count() == 2
    lake.write_landing(daily_key("bookings", D), [])  # dia sin cambios: gzip vacio valido
    summary = ingest.run(lake.spark, parse_args(lake.argv("bookings", D), extra=ingest._extra_args))
    assert summary["rows_read"] == 0
    assert summary["rows_written"] == 0
    rows = lake.rows("bookings", "history_id")
    assert [r["booking_id"] for r in rows] == ["B2"]  # D vacia, D1 intacta


def test_run_date_must_be_a_logical_date():
    with pytest.raises(SystemExit):
        parse_args(["--run-date", "2026-1-1", "--warehouse", "s3://b"])
    with pytest.raises(SystemExit):
        parse_args(["--warehouse", "s3://b"])


def test_glue_catalog_requires_s3_scheme_warehouse():
    base = ["--run-date", D, "--catalog-impl", "glue"]
    assert parse_args([*base, "--warehouse", "s3://bucket/bronze"]).dates == [D]
    for bad in ("s3a://bucket/bronze", "/tmp/warehouse", "bucket/bronze"):
        with pytest.raises(SystemExit):
            parse_args([*base, "--warehouse", bad])
    local = ["--run-date", D, "--catalog-impl", "hadoop", "--warehouse", "/tmp/warehouse"]
    assert parse_args(local).dates == [D]


def test_date_range_arguments():
    common = ["--warehouse", "s3://b"]
    args = parse_args(["--from", "2026-02-27", "--to", "2026-03-02", *common])
    assert args.dates == ["2026-02-27", "2026-02-28", "2026-03-01", "2026-03-02"]
    assert parse_args(["--from", D, "--to", D, *common]).dates == [D]
    for bad in (
        ["--from", D1, "--to", D],  # --to antes que --from
        ["--from", D],  # falta --to
        ["--run-date", D, "--from", D, "--to", D1],  # ambos modos
    ):
        with pytest.raises(SystemExit):
            parse_args([*bad, *common])


# --- esquema explicito (H1), rangos (H2), fx de fin de semana (M1), claves reales (L3) -----


def range_argv(lake, source, date_from, date_to):
    argv = lake.argv(source, date_from)
    i = argv.index("--run-date")
    return [*argv[:i], "--from", date_from, "--to", date_to, *argv[i + 2 :]]


def test_type_drift_between_days_ingests_both(lake):
    # Dia D con enteros, D+1 con decimales: con inferencia el esquema de D1 romperia la tabla.
    lake.write_landing(
        daily_key("bookings", D), [{"history_id": 1, "booking_id": "B1", "amount": 10}]
    )
    lake.write_landing(
        daily_key("bookings", D1), [{"history_id": 2, "booking_id": "B2", "amount": 10.55}]
    )
    lake.write_landing(daily_key("fx", D), [{"currency": "USD", "rate": 1}])
    lake.write_landing(daily_key("fx", D1), [{"currency": "USD", "rate": 1.0825}])
    for source in ("bookings", "fx"):
        ingest.main(lake.argv(source, D))
        ingest.main(lake.argv(source, D1))
    assert [r["amount"] for r in lake.rows("bookings", "history_id")] == [10.0, 10.55]
    assert [r["rate"] for r in lake.rows("fx", "_ingest_date")] == [1.0, 1.0825]


def test_null_then_value_and_optional_field_absent_then_present(lake):
    lake.write_landing(
        clickstream_key(D, 0),
        [{"event_id": "E1", "event_type": "page_view", "amount": None}],  # sin email ni booking_id
    )
    lake.write_landing(
        clickstream_key(D1, 0),
        [
            {
                "event_id": "E2",
                "event_type": "purchase",
                "amount": 99.5,
                "email": "u@example.com",
                "booking_id": "B1",
            }
        ],
    )
    ingest.main(lake.argv("clickstream", D))
    ingest.main(lake.argv("clickstream", D1))
    first, second = lake.rows("clickstream", "event_id")
    assert (first["amount"], first["email"], first["booking_id"]) == (None, None, None)
    assert (second["amount"], second["email"], second["booking_id"]) == (
        99.5,
        "u@example.com",
        "B1",
    )


def test_corrupt_line_fails_the_run_and_keeps_the_partition(lake):
    seed_clickstream(lake, D)
    ingest.main(lake.argv("clickstream", D))
    before = lake.rows("clickstream", "event_id")
    bad = lake.root / clickstream_key(D, 7)
    bad.parent.mkdir(parents=True)
    bad.write_bytes(gzip.compress(b'{"event_id": "E1"}\n{esto no es json\n', mtime=0))
    with pytest.raises(Exception):  # noqa: B017 - Py4JJavaError / AnalysisException segun version
        ingest.main(lake.argv("clickstream", D))
    assert lake.rows("clickstream", "event_id") == before


def test_real_generator_payloads_ingest_with_the_declared_schema(lake):
    from lib.schemas import SCHEMAS
    from ota import clickstream, model
    from ota.export_bookings import write_export
    from ota.keys import landing_key
    from ota.seed_postgres import versions_for_range

    # clickstream: slot real, clave real (L3)
    slot = 7
    key = landing_key(D, slot)
    target = lake.root / key
    target.parent.mkdir(parents=True)
    target.write_bytes(clickstream.generate(D, slot))
    events = clickstream.build_events(D, slot)
    ingest.main(lake.argv("clickstream", D))
    rows = lake.rows("clickstream", "event_id")
    assert len(rows) == len(events)  # duplicados incluidos: Bronze no deduplica
    assert {r["_source_file"] for r in rows} == {key}
    assert {r["_ingested_at"] for r in rows} == {ts(D, 1, 45)}  # slot 7 = 7 x 15 min
    assert {k for e in events for k in e} <= set(SCHEMAS["clickstream"].fieldNames())
    for field in SCHEMAS["clickstream"].fieldNames():
        expected = sum(1 for e in events if e.get(field) is not None)
        assert sum(1 for r in rows if r[field] is not None) == expected, field

    # bookings: filas del historial con los campos exactos del export
    versions = versions_for_range(D, D)
    history = [
        {**v, "history_id": n, "changed_at": v["updated_at"]} for n, v in enumerate(versions, 1)
    ]
    out = write_export(D, history, str(lake.root))
    assert out == lake.root / daily_key("bookings", D)
    ingest.main(lake.argv("bookings", D))
    booking_rows = lake.rows("bookings", "history_id")
    assert len(booking_rows) == len(history)
    assert {r["history_id"] for r in booking_rows} == {h["history_id"] for h in history}
    assert all(r["amount"] is not None and r["created_at"].endswith("Z") for r in booking_rows)
    assert model.fmt_ts  # el modulo real se uso para los timestamps


def test_weekend_fx_file_with_earlier_rate_date_ingests(lake):
    from fx.ecb import build_payload
    from ota.keys import FX_PREFIX
    from ota.keys import daily_key as real_daily_key

    saturday = "2026-01-03"  # sabado: lleva la publicacion del viernes con su rate_date real
    target = lake.root / real_daily_key(FX_PREFIX, saturday)
    target.parent.mkdir(parents=True)
    target.write_bytes(build_payload(saturday, "2026-01-02", {"USD": 1.1, "GBP": 0.87}))
    ingest.main(lake.argv("fx", saturday))
    rows = lake.rows("fx", "currency")
    assert [(r["currency"], r["rate"]) for r in rows] == [("GBP", 0.87), ("USD", 1.1)]
    assert {(r["rate_date"], r["fx_date"], r["base"]) for r in rows} == {
        ("2026-01-02", saturday, "EUR")
    }
    assert {r["_ingest_date"].isoformat() for r in rows} == {saturday}


def test_range_equals_single_day_runs_in_one_session(lake, tmp_path):
    days = ["2026-01-01", "2026-01-02", "2026-01-03"]
    for day in days:
        seed_clickstream(lake, day, n_per_slot=1)
    other = Lake(lake.spark, tmp_path / "single")
    for day in days:  # mismo landing, tablas distintas
        for slot in (0, 5, 95):
            (other.root / clickstream_key(day, slot)).parent.mkdir(parents=True, exist_ok=True)
            data = (lake.root / clickstream_key(day, slot)).read_bytes()
            (other.root / clickstream_key(day, slot)).write_bytes(data)
    for day in days:
        ingest.main(other.argv("clickstream", day))

    started = time.perf_counter()
    assert ingest.main(range_argv(lake, "clickstream", days[0], days[-1])) == 0
    elapsed = time.perf_counter() - started
    print(f"\nRANGE_3_DAYS_SECONDS={elapsed:.1f}")  # noqa: T201

    assert lake.rows("clickstream", "event_id") == other.rows("clickstream", "event_id")
    assert len(lake.rows("clickstream", "event_id")) == 9


def test_range_stops_at_first_failure_and_keeps_committed_days(lake, caplog):
    seed_clickstream(lake, D, n_per_slot=1)
    seed_clickstream(lake, D1, n_per_slot=1)  # 2026-01-03 no tiene landing
    with caplog.at_level("ERROR", logger="bronze.ingest"):
        with pytest.raises(ingest.NoInputFiles):
            ingest.main(range_argv(lake, "clickstream", D, "2026-01-04"))
    days = {r["_ingest_date"].isoformat() for r in lake.rows("clickstream", "event_id")}
    assert days == {D, D1}
    assert "ultima fecha OK: 2026-01-02" in caplog.text
    assert "--from 2026-01-03 --to 2026-01-04" in caplog.text


# --- WAP y checks (U4) ---------------------------------------------------------------------

RULES = """
checks:
  - {type: min_rows, value: 1}
  - {type: not_null, column: v}
  - {type: unique, columns: [id]}
"""


def wap_table(lake) -> str:
    table = f"{lake.catalog}.db.wap_t"
    lake.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake.catalog}.db")
    lake.spark.sql(
        f"CREATE TABLE {table} (id bigint, v string) USING iceberg "
        "TBLPROPERTIES ('write.wap.enabled'='true')"
    )
    lake.spark.sql(f"INSERT INTO {table} VALUES (1, 'a')")
    return table


def test_wap_failed_check_leaves_main_unchanged_and_branch_unpublished(lake):
    table = wap_table(lake)

    def bad_write(spark):
        spark.sql(f"INSERT INTO {table} VALUES (2, NULL)")

    with pytest.raises(WapCheckError) as err:
        run_wap(lake.spark, table, D, bad_write, RULES)
    assert [f.rule for f in err.value.failures] == ["not_null:v"]
    assert [r["id"] for r in lake.spark.table(table).collect()] == [1]  # main sin cambios
    assert list_branches(lake.spark, table) == ["main", f"run_{D}"]  # rama conservada

    # La siguiente ejecucion de D borra la rama vieja y publica (U21, parte del check fallido).
    def good_write(spark):
        spark.sql(f"INSERT INTO {table} VALUES (2, 'b')")

    assert run_wap(lake.spark, table, D, good_write, RULES) == f"run_{D}"
    assert sorted(r["id"] for r in lake.spark.table(table).collect()) == [1, 2]
    assert list_branches(lake.spark, table) == ["main"]


def test_checks_report_each_rule_type(lake):
    frame = lake.spark.createDataFrame(
        [(1, "a", "x"), (1, None, "y"), (3, "c", "z")], "id int, v string, status string"
    )
    rules = """
checks:
  - {type: min_rows, value: 10}
  - {type: not_null, column: v}
  - {type: unique, columns: [id]}
  - {type: accepted_values, column: status, values: [x, y]}
  - {type: expression, name: id_small, sql: "id < 3"}
"""
    rules_found = sorted(f.rule for f in run_checks(frame, rules))
    assert rules_found == [
        "accepted_values:status",
        "expression:id_small",
        "min_rows",
        "not_null:v",
        "unique:id",
    ]
    assert run_checks(frame, "checks:\n  - {type: min_rows, value: 3}\n") == []
