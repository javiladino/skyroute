import gzip
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import UTC

from ota.export_bookings import build_payload, rows_in_day, write_export
from ota.keys import BOOKINGS_PREFIX, daily_key
from ota.seed_postgres import replay_history

START = "2026-05-01"
END = "2026-05-04"
DAY = "2026-05-02"


def _history():
    return replay_history(START, END)


def _lines(payload):
    return [json.loads(line) for line in gzip.decompress(payload).decode("utf-8").splitlines()]


def test_daily_key_format():
    assert daily_key(BOOKINGS_PREFIX, DAY) == "landing/bookings/ingest_date=2026-05-02/part.json.gz"


def test_g4_export_is_byte_identical_in_two_runs(tmp_path):
    first = write_export(DAY, rows_in_day(_history(), DAY), str(tmp_path / "a")).read_bytes()
    second = write_export(DAY, rows_in_day(_history(), DAY), str(tmp_path / "b")).read_bytes()
    assert first == second
    assert first == build_payload(rows_in_day(_history(), DAY))


def test_g4_export_holds_only_the_logical_day_ordered_by_history_id():
    rows = _lines(build_payload(rows_in_day(_history(), DAY)))
    assert rows
    assert all(r["changed_at"][:10] == DAY for r in rows)
    ids = [r["history_id"] for r in rows]
    assert ids == sorted(ids)


def test_g4_export_can_hold_several_versions_of_one_booking_in_a_day():
    history = _history()
    found = False
    for offset in range(4):
        day = f"2026-05-0{1 + offset}"
        counts = Counter(r["booking_id"] for r in _lines(build_payload(rows_in_day(history, day))))
        if any(n >= 2 for n in counts.values()):
            found = True
    assert found


def test_normalize_tz_aware_and_decimal_match_the_string_path():
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from ota import model

    row = dict(_history()[0])
    typed = dict(row)
    for field in ("created_at", "updated_at", "changed_at"):
        naive = datetime.strptime(row[field], "%Y-%m-%dT%H:%M:%SZ")
        # mismo instante expresado en UTC+2: normalize debe devolver UTC con 'Z'
        typed[field] = naive.replace(tzinfo=UTC).astimezone(timezone(timedelta(hours=2)))
    typed["amount"] = Decimal(str(row["amount"]))
    assert model.fmt_ts(typed["changed_at"].astimezone(UTC)) == row["changed_at"]
    assert build_payload([typed]) == build_payload([row])


def test_export_has_route_and_travel_date():
    rows = _lines(build_payload(rows_in_day(_history(), DAY)))
    assert rows
    for row in rows:
        assert row["origin"] and row["destination"] and row["origin"] != row["destination"]
        assert row["travel_date"] > row["created_at"][:10]
        assert len(row["travel_date"]) == 10


def test_range_output_is_byte_identical_to_each_single_day(tmp_path, monkeypatch):
    from ota import export_bookings

    history = _history()
    calls = []

    def fake_fetch(dsn, run_date):
        calls.append(run_date)
        return rows_in_day(history, run_date)

    monkeypatch.setattr(export_bookings, "fetch_rows", fake_fetch)
    days = ["2026-05-01", "2026-05-02", "2026-05-03"]
    rng = tmp_path / "range"
    assert export_bookings.main(["--from", days[0], "--to", days[-1], "--out-dir", str(rng)]) == 0
    assert calls == days
    written = sorted(p.relative_to(rng) for p in rng.rglob("*.json.gz"))
    assert written == sorted(Path(daily_key(BOOKINGS_PREFIX, d)) for d in days)
    for d in days:
        single = tmp_path / d
        assert export_bookings.main(["--run-date", d, "--out-dir", str(single)]) == 0
        key = daily_key(BOOKINGS_PREFIX, d)
        assert (rng / key).read_bytes() == (single / key).read_bytes()


def test_range_args_are_validated(tmp_path, monkeypatch):
    import pytest
    from ota import export_bookings

    monkeypatch.setattr(export_bookings, "fetch_rows", lambda dsn, d: [])
    out = str(tmp_path)
    assert export_bookings.main(["--from", END, "--to", START, "--out-dir", out]) == 2
    with pytest.raises(SystemExit):
        export_bookings.main(["--run-date", DAY, "--from", DAY, "--to", DAY, "--out-dir", out])
    with pytest.raises(SystemExit):
        export_bookings.main(["--from", DAY, "--out-dir", out])
    assert not list(tmp_path.rglob("*.json.gz"))


def test_normalize_serializes_date_columns():
    from datetime import date

    row = dict(_history()[0])
    row["travel_date"] = date.fromisoformat(row["travel_date"])
    assert build_payload([row]) == build_payload([_history()[0]])
