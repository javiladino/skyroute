import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ota.clickstream import generate  # noqa: E402
from ota.keys import landing_key, seed_for  # noqa: E402
from ota.model import BOOKINGS_PER_DAY  # noqa: E402
from ota.seed_postgres import rows_for_day  # noqa: E402

DAY = "2026-05-01"
EMAIL = re.compile(r"^u[0-9a-f]{12}@example\.com$")
FORBIDDEN = {"name", "first_name", "last_name", "phone", "address", "street", "city"}


def _events(day):
    out = []
    for slot in range(96):
        text = gzip.decompress(generate(day, slot)).decode("utf-8")
        out.extend(json.loads(line) for line in text.splitlines())
    return out


def test_seed_is_sha256_based_and_stable():
    assert seed_for(DAY, 17, "clickstream") == seed_for(DAY, 17, "clickstream")
    assert seed_for(DAY, 17, "clickstream") != seed_for(DAY, 18, "clickstream")


def test_landing_key_format():
    assert landing_key(DAY, 5) == (
        "landing/clickstream/ingest_date=2026-05-01/slot=05/part.json.gz"
    )


def test_ts_u3_purchase_booking_ids_exist_in_rows():
    rows = {r["booking_id"]: r for r in rows_for_day(DAY)}
    assert len(rows) == BOOKINGS_PER_DAY
    purchases = [e for e in _events(DAY) if e["event_type"] == "purchase"]
    assert {e["booking_id"] for e in purchases} == set(rows)
    for event in purchases:
        row = rows[event["booking_id"]]
        assert row["customer_id"] == event["customer_id"]
        assert row["session_id"] == event["session_id"]
        assert row["currency"] == event["currency"]
        assert row["amount"] == event["amount"]
        assert row["created_at"] == event["event_ts"]


def test_booking_id_only_in_purchases():
    for event in _events(DAY):
        assert ("booking_id" in event) == (event["event_type"] == "purchase")


def test_ts_u4_email_format_and_no_pii_fields():
    emails = 0
    for event in _events(DAY):
        assert not (set(event) & FORBIDDEN)
        if "email" in event:
            emails += 1
            assert EMAIL.match(event["email"])
    assert emails > 0


def test_duplicates_and_late_events_exist():
    events = _events(DAY)
    ids = [e["event_id"] for e in events]
    assert len(ids) > len(set(ids))
    assert any(e["event_ts"][:10] < DAY for e in events)
