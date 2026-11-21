import gzip
import itertools
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

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
