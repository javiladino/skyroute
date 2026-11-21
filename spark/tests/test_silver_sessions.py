"""Tests de Silver sessions: U15-U17, U19 y U23. Todo local, sin AWS."""

import gzip
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from conftest import Lake
from jobs.bronze import ingest
from jobs.silver import events as silver_events
from jobs.silver import sessions as silver_sessions
from lib.wap import WapCheckError, list_branches
from test_bookings_scd2 import SILVER, day, lake_b, silver_argv  # noqa: F401
from test_silver_events import (  # noqa: F401
    clickstream_key,
    ev,
    event_rows,
    hmac_key,
    ingest_clicks,
    run_events,
)

GENERATORS = Path(__file__).resolve().parents[2] / "generators"
if str(GENERATORS) not in sys.path:
    sys.path.insert(0, str(GENERATORS))

from ota import model  # noqa: E402
from ota.clickstream import generate  # noqa: E402
from ota.keys import SLOTS_PER_DAY, landing_key  # noqa: E402

# (dia de ingesta, event_id, dia del evento, hora, cliente, tipo, booking_id). Cada dia lleva un
# evento de relleno (Bronze falla sin archivos y una ingesta vacia no crea la tabla).
WORLD = [
    (0, "E01", 0, "23:50:00", "C1", "page_view", None),  # cruza medianoche con E02
    (0, "E03", 0, "12:20:00", "C2", "page_view", None),
    (0, "F0", 0, "03:00:00", "C9", "page_view", None),
    (1, "E02", 1, "00:10:00", "C1", "search", None),
    (1, "E05", 1, "09:00:00", "C3", "page_view", None),
    (1, "E06", 1, "09:20:00", "C3", "search", None),
    (1, "E07", 1, "10:00:00", "C3", "page_view", None),  # hueco de 40 min: otra sesion
    (1, "F1", 1, "03:00:00", "C9", "page_view", None),
    (2, "E04", 0, "12:00:00", "C2", "page_view", None),  # tardio de d0: pasa a ser el primero
    (2, "E08", 2, "15:00:00", "C4", "page_view", None),
    (2, "E09", 2, "15:10:00", "C4", "add_to_cart", None),
    (2, "E10", 2, "15:20:00", "C4", "purchase", "B1"),
    (2, "F2", 2, "03:00:00", "C9", "page_view", None),
    (3, "E13", 3, "00:10:00", "C5", "page_view", None),
    (3, "E11", 3, "08:00:00", "C6", "page_view", None),
    (3, "F3", 3, "03:00:00", "C9", "page_view", None),
    (4, "E12", 2, "23:55:00", "C5", "page_view", None),  # tardio de d2: adelanta la sesion de C5
    (4, "F4", 4, "03:00:00", "C9", "page_view", None),
    (5, "F5", 5, "03:00:00", "C9", "page_view", None),
    # H1: C7 cruza medianoche; el tardio de 00:15 (ingesta d4, <= 72 h) une las dos mitades
    (0, "E14", 0, "23:50:00", "C7", "page_view", None),
    (1, "E15", 1, "00:40:00", "C7", "page_view", None),
    (4, "E16", 1, "00:15:00", "C7", "page_view", None),
]


def _long_session_rows() -> list[tuple]:
    """C8: un evento cada 30 min de d0 12:00 a d1 12:30 (nunca hay hueco > 30 min).

    El evento de d1 12:00 cumple 24 h desde el primero: abre sesion nueva (tope de 24 h).
    """
    rows = []
    for index in range(50):
        minutes = 12 * 60 + 30 * index
        offset, rest = divmod(minutes, 24 * 60)
        hour, minute = divmod(rest, 60)
        rows.append((offset, f"G{index:02d}", offset, f"{hour:02d}:{minute:02d}:00", "C8",
                     "page_view", None))
    # a 24 h - 1 s del primero: sigue en la primera sesion (fija el `>=` del tope)
    rows.append((1, "GX", 1, "11:59:59", "C8", "page_view", None))
    return rows


WORLD += _long_session_rows()


def world_rows(ingest_day: int) -> list[dict]:
    rows = []
    for ing, event_id, offset, hour, customer, etype, booking in WORLD:
        if ing != ingest_day:
            continue
        extra = {"booking_id": booking} if booking else {}
        rows.append(ev(event_id, f"{day(offset)}T{hour}Z", customer, etype, **extra))
    if ingest_day == 2:  # duplicado exacto dentro del archivo
        rows.append(dict(rows[-2]))
    return rows


def ingest_world(lake: Lake, days) -> None:
    for n in days:
        ingest_clicks(lake, day(n), world_rows(n))


def run_sessions(lake: Lake, n: int, extra=None) -> None:
    assert silver_sessions.main(silver_argv(lake, day(n)) + (extra or [])) == 0


def sessions_table(lake: Lake) -> str:
    return f"{lake.catalog}.{SILVER}.sessions"


def session_rows(lake: Lake) -> list[dict]:
    frame = lake.spark.table(sessions_table(lake)).orderBy("session_key")
    return [r.asDict() for r in frame.collect()]


def key_of(customer: str, first_event_id: str) -> str:
    return hashlib.sha256(f"{customer}|{first_event_id}".encode()).hexdigest()


def pipeline(lake: Lake, days) -> None:
    """events y sessions de cada dia, en el orden dado."""
    for n in days:
        run_events(lake, day(n))
        run_sessions(lake, n)


def test_u15_gap_threshold_31_minutes_splits_and_29_does_not(lake):
    d0 = day(0)
    ingest_clicks(
        lake,
        d0,
        [
            ev("A1", f"{d0}T10:00:00Z", "C1"),
            ev("A2", f"{d0}T10:31:00Z", "C1"),  # 31 min: 2 sesiones
            ev("B1", f"{d0}T10:00:00Z", "C2"),
            ev("B2", f"{d0}T10:29:00Z", "C2"),  # 29 min: 1 sesion
            ev("D1", f"{d0}T10:00:00Z", "C3"),
            ev("D2", f"{d0}T10:30:00Z", "C3"),  # 30 min exactos: 1 sesion (hueco > umbral abre)
            ev("P1", f"{d0}T10:00:00Z", "C4"),
            ev("P2", f"{d0}T10:10:00Z", "C4", "purchase", booking_id="BK1"),
        ],
    )
    run_events(lake, d0)
    run_sessions(lake, 0)

    by_customer = defaultdict(list)
    for r in session_rows(lake):
        by_customer[r["customer_id"]].append(r)
    assert sorted(len(v) for v in by_customer.values()) == [1, 1, 1, 2]
    assert {r["n_events"] for r in by_customer["C1"]} == {1}
    (c2,) = by_customer["C2"]
    assert (c2["n_events"], c2["session_start"], c2["session_end"]) == (
        2,
        datetime(2026, 1, 1, 10, 0),
        datetime(2026, 1, 1, 10, 29),
    )
    assert c2["session_start_date"] == date(2026, 1, 1) and c2["converted"] is False
    assert len(by_customer["C3"]) == 1
    (c4,) = by_customer["C4"]
    assert (c4["converted"], c4["booking_id"], c4["n_events"]) == (True, "BK1", 2)
    assert c4["session_key"] == key_of("C4", "P1")

    # el umbral es configurable: con 60 min C1 pasa a una sesion y la clave antigua no queda
    run_sessions(lake, 0, ["--session-gap-minutes", "60"])
    after = defaultdict(list)
    for r in session_rows(lake):
        after[r["customer_id"]].append(r)
    assert sorted(len(v) for v in after.values()) == [1, 1, 1, 1]
    assert after["C1"][0]["n_events"] == 2
    assert list_branches(lake.spark, sessions_table(lake)) == ["main"]


def write_generated_day(lake: Lake, run_date: str) -> None:
    for slot in range(SLOTS_PER_DAY):
        target = lake.root / landing_key(run_date, slot)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(generate(run_date, slot))


def generator_sessions(run_date: str) -> dict[str, frozenset]:
    """session_id del generador -> event_ids, sin los tardios (event_ts antes de su slot)."""
    start = model.parse_day(run_date)
    booking_sessions = {b["session_id"] for b in model.bookings_for_day(run_date)}
    groups = defaultdict(set)
    for slot in range(SLOTS_PER_DAY):
        base = start + timedelta(minutes=15 * slot)
        for line in gzip.decompress(generate(run_date, slot)).decode("utf-8").splitlines():
            event = json.loads(line)
            stamp = datetime.strptime(event["event_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            # recorridos y compras (sesion de una reserva) no son tardios aunque salgan del slot
            if event["session_id"] in booking_sessions or stamp >= base:
                groups[event["session_id"]].add(event["event_id"])
    return {sid: frozenset(ids) for sid, ids in groups.items()}


def test_u16_generated_day_sessions_match_generator_session_ids(lake):
    run_date = "2026-05-01"
    write_generated_day(lake, run_date)
    assert ingest.main(lake.argv("clickstream", run_date)) == 0
    assert silver_events.main(silver_argv(lake, run_date)) == 0

    oracle = generator_sessions(run_date)
    keep = lake.spark.createDataFrame(
        [(i,) for ids in oracle.values() for i in ids], "event_id string"
    )
    events = lake.spark.table(f"{lake.catalog}.{SILVER}.events").join(keep, "event_id")
    labeled = silver_sessions.assign_sessions(events, 30)
    derived = defaultdict(set)
    for r in labeled.select("session_key", "event_id").collect():
        derived[r["session_key"]].add(r["event_id"])

    assert len(oracle) > 100
    assert sorted(map(sorted, derived.values())) == sorted(map(sorted, oracle.values()))


def test_u17_rerun_sessions_is_idempotent(lake, lake_b, spark, tmp_path):  # noqa: F811
    third = Lake(spark, tmp_path / "third")
    for lk in (lake, lake_b, third):
        ingest_world(lk, range(2))
    pipeline(lake, [0, 1])
    expected = session_rows(lake)
    assert len(expected) > 0

    pipeline(lake_b, [0, 1])
    run_sessions(lake_b, 0)  # D, D+1, D otra vez
    assert session_rows(lake_b) == expected

    pipeline(third, [0, 1])
    for n in (0, 1):  # D, D+1, D, D+1
        run_sessions(third, n)
    assert session_rows(third) == expected
    for lk in (lake, lake_b, third):
        assert list_branches(lk.spark, sessions_table(lk)) == ["main"]


def test_u19_late_event_that_becomes_first_leaves_no_orphan_session(lake, lake_b):  # noqa: F811
    ingest_world(lake, range(3))
    ingest_world(lake_b, range(3))
    # E03 abre la sesion de C2 en d0; E04 (tardio, ingesta d2) la adelanta
    pipeline(lake, [0, 1, 2])

    for r in event_rows(lake):  # el tardio esta en Silver con su event_ts de d0
        assert r["event_id"] != "E04" or r["event_ts"] == datetime(2026, 1, 1, 12, 0)
    c2 = [r for r in session_rows(lake) if r["customer_id"] == "C2"]
    assert [(r["session_key"], r["n_events"]) for r in c2] == [(key_of("C2", "E04"), 2)]
    assert key_of("C2", "E03") not in {r["session_key"] for r in session_rows(lake)}

    # sin pasos intermedios: todos los eventos antes de sesionizar
    for n in range(3):
        run_events(lake_b, day(n))
    for n in range(3):
        run_sessions(lake_b, n)
    assert session_rows(lake_b) == session_rows(lake)


def test_u23_session_crossing_midnight_into_d_minus_4_belongs_to_its_first_day(
    lake, lake_b, spark, tmp_path  # noqa: F811
):
    third = Lake(spark, tmp_path / "third")
    for lk in (lake, lake_b, third):
        ingest_world(lk, range(6))  # E01 (23:50 de d0) y E02 (00:10 de d1) son de C1
    pipeline(lake, [0, 1, 2, 3, 4, 5])  # en orden; D = d5, D-4 = d1, D-5 = d0
    c1 = [r for r in session_rows(lake) if r["customer_id"] == "C1"]
    assert [(r["session_key"], r["session_start_date"], r["n_events"]) for r in c1] == [
        (key_of("C1", "E01"), date(2026, 1, 1), 2)
    ]

    for n in range(6):
        run_events(lake_b, day(n))
    run_sessions(lake_b, 0)  # sesion de D-5 ya escrita
    run_sessions(lake_b, 5)  # ejecutar D: la lee como contexto pero no la reescribe ni la parte
    c1_b = [r for r in session_rows(lake_b) if r["customer_id"] == "C1"]
    assert c1_b == c1

    # sin sesion previa de d0: D no inventa una sesion nueva en D-4 con el evento de 00:10
    for n in range(6):
        run_events(third, day(n))
    run_sessions(third, 5)
    assert [r for r in session_rows(third) if r["customer_id"] == "C1"] == []


def test_h1_late_event_bridging_midnight_keeps_one_session_in_any_order(lake, lake_b):  # noqa: F811
    for lk in (lake, lake_b):
        ingest_world(lk, range(5))
    pipeline(lake, range(5))
    c7 = [r for r in session_rows(lake) if r["customer_id"] == "C7"]
    assert [(r["session_key"], r["session_start_date"], r["n_events"]) for r in c7] == [
        (key_of("C7", "E14"), date(2026, 1, 1), 3)
    ]

    pipeline(lake_b, range(4))
    run_events(lake_b, day(4))
    run_sessions(lake_b, 4)
    run_sessions(lake_b, 1)  # relanzar un dia intermedio despues del tardio
    run_sessions(lake_b, 0)
    assert session_rows(lake_b) == session_rows(lake)


def test_session_is_split_when_it_reaches_24_hours(lake):
    ingest_world(lake, range(2))
    pipeline(lake, range(2))
    c8 = [r for r in session_rows(lake) if r["customer_id"] == "C8"]
    c8.sort(key=lambda r: r["session_start"])
    shape = [(r["session_key"], r["session_start"], r["session_end"], r["n_events"]) for r in c8]
    assert shape == [
        (key_of("C8", "G00"), datetime(2026, 1, 1, 12, 0), datetime(2026, 1, 2, 11, 59, 59), 49),
        (key_of("C8", "G48"), datetime(2026, 1, 2, 12, 0), datetime(2026, 1, 2, 12, 30), 2),
    ]
    assert [r["session_start_date"] for r in c8] == [date(2026, 1, 1), date(2026, 1, 2)]


def test_sessions_fail_while_bronze_partition_of_the_day_is_not_in_events(lake):
    d0, d1 = day(0), day(1)
    ingest_clicks(lake, d0, [ev("E1", f"{d0}T10:00:00Z")])
    with pytest.raises(WapCheckError) as err:  # events todavia no ejecutado
        run_sessions(lake, 0)
    assert [f.rule for f in err.value.failures] == ["events_missing_for_ingest_day"]

    # falso negativo de la comprobacion antigua: events corrio D+1 (con un tardio de d0) pero no D
    ingest_clicks(lake, d1, [ev("E2", f"{d0}T11:00:00Z")])
    run_events(lake, d1)
    with pytest.raises(WapCheckError) as err:
        run_sessions(lake, 0)
    assert [f.rule for f in err.value.failures] == ["events_missing_for_ingest_day"]

    run_events(lake, d0)
    run_sessions(lake, 0)
    assert len(session_rows(lake)) == 2  # E1 (10:00) y el tardio E2 (11:00): hueco de 60 min

    # sin particion Bronze de d2 no se bloquea (no hay nada que esperar de events)
    run_sessions(lake, 2)
    assert len(session_rows(lake)) == 2


def test_sessions_fail_when_a_long_chain_touches_the_read_boundary(lake):
    d4 = day(4)
    # gap de 12 h: lectura desde d-2 12:00; la cadena (un evento cada 12 h, sin huecos > gap)
    # empieza ahi, dura 48 h y su tercera sesion empieza en d0 = D-4
    stamps = [(-2, "12:00"), (-1, "00:00"), (-1, "12:00"), (0, "00:00"), (0, "12:00")]
    rows = [ev(f"L{i}", f"{day(n)}T{hm}:00Z", "C1") for i, (n, hm) in enumerate(stamps)]
    ingest_clicks(lake, d4, rows)
    run_events(lake, d4)

    with pytest.raises(WapCheckError) as err:
        run_sessions(lake, 4, ["--session-gap-minutes", "720"])
    assert [f.rule for f in err.value.failures] == ["sessions_chain_touches_context"]
    assert session_rows(lake) == []
