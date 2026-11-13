import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lambda_handler  # noqa: E402
from ota.clickstream import generate  # noqa: E402
from ota.keys import landing_key  # noqa: E402


class MemoryWriter:
    def __init__(self, keep_bodies=True):
        self.calls = []
        self.objects = {}
        self.keep_bodies = keep_bodies

    def __call__(self, key, body):
        self.calls.append(key)
        if self.keep_bodies:
            self.objects[key] = body


def test_ts_u5_slot_from_scheduled_time():
    f = lambda_handler.slot_from_scheduled_time
    assert f("2026-11-13T10:14:59Z") == ("2026-11-13", 40)
    assert f("2026-11-13T10:15:00Z") == ("2026-11-13", 41)
    assert f("2026-11-13T00:00:00Z") == ("2026-11-13", 0)
    assert f("2026-11-13T23:59:59Z") == ("2026-11-13", 95)
    assert f("2026-11-13T12:00:00+02:00") == ("2026-11-13", 40)


def test_scheduled_event_writes_one_object():
    writer = MemoryWriter()
    out = lambda_handler.handler({"scheduled_time": "2026-11-13T10:14:59Z"}, None, writer=writer)
    assert writer.calls == [landing_key("2026-11-13", 40)]
    assert out["objects"] == 1


def test_ts_u6_backfill_182_days():
    d = date(2026, 11, 13)
    writer = MemoryWriter(keep_bodies=False)
    event = {"from": (d - timedelta(days=182)).isoformat(), "to": (d - timedelta(days=1)).isoformat()}
    out = lambda_handler.handler(event, None, writer=writer, today_fn=lambda: d)
    assert out["objects"] == 182 * 96 == 17472
    assert len(set(writer.calls)) == 17472
    assert not any(f"ingest_date={d.isoformat()}" in k for k in writer.calls)


def test_ts_u7_backfill_to_today_or_future_fails_without_writing():
    d = date(2026, 11, 13)
    for to in (d, d + timedelta(days=3)):
        writer = MemoryWriter()
        event = {"from": "2026-11-01", "to": to.isoformat()}
        with pytest.raises(ValueError):
            lambda_handler.handler(event, None, writer=writer, today_fn=lambda: d)
        assert writer.calls == []


@pytest.mark.parametrize("event", [
    {}, {"from": "2026-11-01"}, {"from": "x", "to": "2026-11-02"},
    {"from": "2026-11-05", "to": "2026-11-02"}, {"scheduled_time": "nope"},
    {"scheduled_time": "2026-11-13T10:00:00"},
])
def test_invalid_events_fail_without_writing(event):
    writer = MemoryWriter()
    with pytest.raises(ValueError):
        lambda_handler.handler(event, None, writer=writer, today_fn=lambda: date(2026, 11, 13))
    assert writer.calls == []


def test_ts_u8_redelivery_same_key_same_bytes():
    writer = MemoryWriter()
    event = {"scheduled_time": "2026-11-13T10:14:59Z"}
    lambda_handler.handler(event, None, writer=writer)
    first = dict(writer.objects)
    lambda_handler.handler(event, None, writer=writer)
    assert len(writer.calls) == 2 and writer.calls[0] == writer.calls[1]
    assert writer.objects == first
    assert writer.objects[writer.calls[0]] == generate("2026-11-13", 40)


def test_boto3_not_imported_with_module():
    assert not hasattr(lambda_handler, "boto3")


def test_one_day_96_slots_timing(capsys):
    """Indicio local para OQ2 (no sustituye V12, que se mide en Lambda)."""
    writer = MemoryWriter(keep_bodies=False)
    start = time.perf_counter()
    out = lambda_handler.handler(
        {"from": "2026-05-01", "to": "2026-05-01"}, None,
        writer=writer, today_fn=lambda: date(2026, 11, 13),
    )
    elapsed = time.perf_counter() - start
    assert out["objects"] == 96
    with capsys.disabled():
        print(f"\nTIMING 96 slots (1 day, local, in-memory writer): {elapsed:.3f} s")
    assert elapsed < 60
