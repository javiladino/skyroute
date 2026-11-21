import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ota import model
from ota.seed_postgres import replay_history, sql_for_range

DAY = "2026-05-01"
END = "2026-05-03"
INIT_DIR = Path(__file__).resolve().parents[2] / "docker" / "postgres" / "init"
DDL = INIT_DIR / "002_bookings_history.sql"


def test_g2_some_booking_has_several_versions_with_increasing_updated_at():
    by_booking = defaultdict(list)
    for version in model.booking_versions_for_day(DAY):
        by_booking[version["booking_id"]].append(version)
    assert len(by_booking) == model.BOOKINGS_PER_DAY
    multi = [vs for vs in by_booking.values() if len(vs) >= 2]
    assert multi
    for versions in multi:
        stamps = [v["updated_at"] for v in sorted(versions, key=lambda v: v["version"])]
        assert stamps == sorted(set(stamps))
        assert stamps[0] == versions[0]["created_at"]


def test_final_version_matches_booking_row():
    finals = {}
    for version in model.booking_versions_for_day(DAY):
        finals[version["booking_id"]] = version
    for booking in model.bookings_for_day(DAY):
        assert finals[booking["booking_id"]]["status"] == booking["status"]
        assert finals[booking["booking_id"]]["updated_at"] == booking["updated_at"]


def test_g3_two_regenerations_give_identical_history_including_history_id():
    model._build.cache_clear()
    first = replay_history(DAY, END)
    model._build.cache_clear()
    second = replay_history(DAY, END)
    assert first == second
    assert [h["history_id"] for h in first] == list(range(1, len(first) + 1))
    assert len(first) > len({h["booking_id"] for h in first})


def test_g3_rebuild_sql_is_identical_and_truncates_with_restart_identity():
    model._build.cache_clear()
    first = sql_for_range(DAY, END, rebuild=True)
    model._build.cache_clear()
    second = sql_for_range(DAY, END, rebuild=True)
    assert first == second
    assert "TRUNCATE bookings, bookings_history RESTART IDENTITY;" in first
    assert "TRUNCATE" not in sql_for_range(DAY, END)
    assert "ON CONFLICT (booking_id) DO UPDATE" in first


def test_ddl_declares_history_table_and_trigger_on_updated_at():
    text = DDL.read_text(encoding="utf-8")
    assert "history_id  bigserial PRIMARY KEY" in text
    assert "AFTER INSERT OR UPDATE ON bookings" in text
    assert "NEW.updated_at, NEW.updated_at" in text
