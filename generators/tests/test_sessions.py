import gzip
import itertools
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ota.clickstream import MAX_LATE_SECONDS, generate
from ota.seed_postgres import rows_for_day

DAY = "2026-05-01"
GAP = timedelta(minutes=30)


def _parse(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@lru_cache(maxsize=4)
def _by_slot(day):
    out = {}
    for slot in range(96):
        text = gzip.decompress(generate(day, slot)).decode("utf-8")
        out[slot] = [json.loads(line) for line in text.splitlines()]
    return out


def _sessions(day):
    sessions = defaultdict(list)
    for events in _by_slot(day).values():
        for event in events:
            sessions[event["session_id"]].append(event)
    return sessions


def test_g1_session_with_several_events_ends_in_purchase_of_a_booking():
    booking_ids = {r["booking_id"] for r in rows_for_day(DAY)}
    linked = 0
    for events in _sessions(DAY).values():
        purchases = [e for e in events if e["event_type"] == "purchase"]
        if not purchases:
            continue
        unique = {e["event_id"]: e for e in events}.values()
        ordered = sorted(unique, key=lambda e: (e["event_ts"], e["event_id"]))
        assert len(ordered) >= 2
        assert len({e["customer_id"] for e in ordered}) == 1
        assert ordered[-1]["event_type"] == "purchase"
        assert ordered[-1]["booking_id"] in booking_ids
        gaps = [
            _parse(b["event_ts"]) - _parse(a["event_ts"]) for a, b in itertools.pairwise(ordered)
        ]
        assert all(gap < GAP for gap in gaps)
        linked += 1
    assert linked == len(booking_ids)


def test_navigation_sessions_have_several_events_of_one_customer():
    multi = 0
    for events in _sessions(DAY).values():
        assert len({e["customer_id"] for e in events}) == 1
        if len({e["event_id"] for e in events}) >= 2:
            multi += 1
    assert multi > 100


def test_g5_late_events_within_72h_and_duplicates_stay_in_their_file():
    seen_in = {}
    for slot, events in _by_slot(DAY).items():
        base = datetime.strptime(DAY, "%Y-%m-%d").replace(tzinfo=UTC) + timedelta(minutes=15 * slot)
        for event in events:
            ts = _parse(event["event_ts"])
            assert ts >= base - timedelta(seconds=MAX_LATE_SECONDS) - timedelta(hours=2)
            assert seen_in.setdefault(event["event_id"], slot) == slot
    all_events = [e for events in _by_slot(DAY).values() for e in events]
    assert len(all_events) > len(seen_in)


# --- gold-dbt fase 1: recorridos multi-campana, funnel y navegacion de fondo ---

from ota import model  # noqa: E402
from ota.clickstream import build_events, journey_event_n, journey_events  # noqa: E402

MULTI_CAMPAIGN_MIN_SHARE = 0.30  # Open question 1 del plan: umbral recomendado, no fijado
MULTI_CAMPAIGN_DAYS = 30
MULTI_CAMPAIGN_START = "2026-05-01"
FUNNEL_ORDER = ["search", "product_view", "add_to_cart", "begin_checkout", "purchase"]
LATE_FUNNEL = {"add_to_cart", "begin_checkout", "purchase"}


def _day(start, offset):
    return (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=offset)).strftime("%Y-%m-%d")


def _journey_ids(day):
    ids = set()
    for slot in range(96):
        for journey in model.journeys_for_slot(day, slot):
            ids.update(e["event_id"] for e in journey_events(day, slot, journey))
    return ids


def test_multi_campaign_share():
    multi = total = 0
    for offset in range(MULTI_CAMPAIGN_DAYS):
        for sessions in model.booking_journeys(_day(MULTI_CAMPAIGN_START, offset)):
            total += 1
            multi += len({s["campaign_id"] for s in sessions}) >= 2
    assert multi / total >= MULTI_CAMPAIGN_MIN_SHARE


def test_last_touch_is_booking_campaign():
    bookings = {b["booking_id"]: b for b in model.bookings_for_day(DAY)}
    journeys = model.booking_journeys(DAY)
    assert len(journeys) == len(bookings)
    for sessions in journeys:
        booking = bookings[sessions[0]["booking_id"]]
        assert 1 <= len(sessions) <= 4
        assert sessions[-1]["campaign_id"] == booking["campaign_id"]
        assert sessions[-1]["session_id"] == booking["session_id"]
        assert all(e["campaign_id"] == booking["campaign_id"] for e in sessions[-1]["events"])
        assert [s["touch_seq"] for s in sessions] == list(range(len(sessions)))
    purchases = [e for e in _all_events(DAY) if e["event_type"] == "purchase"]
    assert {e["booking_id"]: e["campaign_id"] for e in purchases} == {
        b["booking_id"]: b["campaign_id"] for b in bookings.values()
    }


def _all_events(day):
    return [e for events in _by_slot(day).values() for e in events]


def test_funnel_never_inverted():
    rank = {t: i for i, t in enumerate(FUNNEL_ORDER)}
    checked = reaching_checkout = 0
    for events in _sessions(DAY).values():
        unique = {e["event_id"]: e for e in events}.values()
        ordered = sorted(unique, key=lambda e: (e["event_ts"], e["event_id"]))
        ranks = [rank[e["event_type"]] for e in ordered if e["event_type"] in rank]
        assert ranks == sorted(ranks)
        checked += 1
        reaching_checkout += any(e["event_type"] == "begin_checkout" for e in ordered)
    assert checked > 100
    assert reaching_checkout > 0


def test_background_has_no_late_funnel_steps():
    journey_ids = _journey_ids(DAY)
    purchase_ids = {e["event_id"] for e in _all_events(DAY) if e["event_type"] == "purchase"}
    background = [e for e in _all_events(DAY)
                  if e["event_id"] not in journey_ids | purchase_ids]
    assert background
    assert {e["event_type"] for e in background} <= set(model.BACKGROUND_EVENT_TYPES)
    assert not {e["event_type"] for e in background} & LATE_FUNNEL
    assert "product_view" in {e["event_type"] for e in background}
    assert set(model.BACKGROUND_EVENT_TYPES) | LATE_FUNNEL <= set(model.EVENT_TYPES)


def test_background_still_emits_consent_with_email():
    seen = set()
    consents = 0
    for offset in range(3):
        day = _day(DAY, offset)
        journey_ids = _journey_ids(day)
        for slot in range(96):
            for event in build_events(day, slot):
                if event["event_id"] in journey_ids or event["event_type"] == "purchase":
                    continue
                seen.add(event["event_type"])
                if event["event_type"] == "consent":
                    consents += 1
                    assert event.get("email")
                else:
                    assert "email" not in event
    assert consents > 0
    assert "page_view" in seen


def test_journey_event_ids_reserved_range():
    assert journey_event_n(0, 0) == 2000
    assert journey_event_n(3, 99) == 2000 + 3 * 100 + 99
    last_of_j = journey_event_n(5, 99)
    assert last_of_j < journey_event_n(6, 0)
    # maximo del modelo: 4 sesiones de 5 pasos, ninguna rebasa el rango de su recorrido
    for day in (DAY, _day(DAY, 1)):
        for journey in model.customer_journeys(day):
            assert len(journey["events"]) <= 5
    with pytest.raises(ValueError):
        journey_event_n(1, 100)
    full = {"j": 1, "events": [{"n": k, "event_type": "page_view"} for k in range(100)]}
    assert len(journey_events(DAY, 0, full)) == 100
    with pytest.raises(ValueError):
        journey_events(DAY, 0, {"j": 1, "events": full["events"] + [{"n": 100}]})


def test_touchpoints_in_window():
    emitted = 0
    for sessions in model.booking_journeys(DAY):
        booking_day = datetime.strptime(DAY, "%Y-%m-%d")
        for session in sessions:
            emit = datetime.strptime(session["emit_date"], "%Y-%m-%d")
            assert booking_day - timedelta(days=6) <= emit <= booking_day
            for event in session["events"]:
                ts = datetime.strptime(event["event_ts"], "%Y-%m-%dT%H:%M:%SZ")
                assert ts >= booking_day - timedelta(days=6)
                assert ts.date() <= booking_day.date()
            out = build_events(session["emit_date"], session["slot"])
            ids = {e["event_id"] for e in out if e["session_id"] == session["session_id"]}
            assert len(ids) >= len(session["events"])
            assert all(
                e["session_id"] == session["session_id"]
                for e in out
                if e["event_id"] in ids
            )
            emitted += 1
    assert emitted >= model.BOOKINGS_PER_DAY


def test_event_ids_unique_per_run_date():
    for day in (DAY, _day(DAY, 3)):
        for slot in range(96):
            events = build_events(day, slot)
            by_id = {}
            for event in events:
                by_id.setdefault(event["event_id"], []).append(event)
            for same in by_id.values():
                # duplicados exactos intencionados (3 %); un id nunca tiene contenido distinto
                assert all(e == same[0] for e in same)
        ids = [e["event_id"] for e in journey_events_of_day(day)]
        assert len(ids) == len(set(ids))


def journey_events_of_day(day):
    return [e for slot in range(96) for j in model.journeys_for_slot(day, slot)
            for e in journey_events(day, slot, j)]


def test_cached_journeys_are_not_shared_with_callers():
    before = model.customer_journeys(DAY)
    for journey in model.customer_journeys(DAY):
        journey["events"].clear()
        journey["campaign_id"] = "X"
    for sessions in model.booking_journeys(DAY):
        sessions[0]["events"].clear()
    for journey in model.journeys_for_slot(DAY, 0):
        journey["events"].clear()
    assert model.customer_journeys(DAY) == before
