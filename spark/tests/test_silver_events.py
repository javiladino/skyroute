"""Tests de Silver events: U13 y U14 (y la clave HMAC sin AWS). Todo local, sin AWS."""

import hashlib
import hmac
from datetime import datetime

import pytest
from conftest import Lake
from jobs.bronze import ingest
from jobs.silver import events as silver_events
from lib.wap import WapCheckError, list_branches
from test_bookings_scd2 import SILVER, day, silver_argv

KEY = "test-hmac-key"


@pytest.fixture(autouse=True)
def hmac_key(monkeypatch):
    """Clave fija por entorno: ningun test llama a SSM."""
    monkeypatch.setenv(silver_events.HMAC_KEY_ENV, KEY)


def clickstream_key(run_date: str, slot: int = 0) -> str:
    return f"landing/clickstream/ingest_date={run_date}/slot={slot:02d}/part.json.gz"


def ev(event_id: str, ts: str, customer: str = "C1", etype: str = "page_view", **extra) -> dict:
    row = {
        "event_id": event_id,
        "event_type": etype,
        "event_ts": ts,
        "customer_id": customer,
        "session_id": f"S-{customer}",
        "campaign_id": "CMP-0001",
        "currency": "EUR",
        "amount": None,
        "consent_ts": "2025-01-01T00:00:00Z",
    }
    row.update(extra)
    return row


def ingest_clicks(lake: Lake, run_date: str, rows: list[dict], slot: int = 0) -> None:
    lake.write_landing(clickstream_key(run_date, slot), rows)
    assert ingest.main(lake.argv("clickstream", run_date)) == 0


def run_events(lake: Lake, run_date: str) -> None:
    assert silver_events.main(silver_argv(lake, run_date)) == 0


def events_table(lake: Lake) -> str:
    return f"{lake.catalog}.{SILVER}.events"


def event_rows(lake: Lake) -> list[dict]:
    frame = lake.spark.table(events_table(lake)).orderBy("event_id")
    return [r.asDict() for r in frame.collect()]


def expected_hmac(email: str) -> str:
    return hmac.new(KEY.encode(), email.encode(), hashlib.sha256).hexdigest()


def test_u13_duplicates_and_late_event_rerun_do_not_duplicate(lake):
    d0, d1, d2 = day(0), day(1), day(2)
    first = ev("E1", f"{d0}T10:00:00Z")
    ingest_clicks(lake, d0, [first, dict(first), ev("E2", f"{d0}T10:05:00Z")])  # duplicado exacto
    ingest_clicks(lake, d1, [ev("E3", f"{d1}T09:00:00Z")])
    # D+2 trae un tardio de D (event_ts en d0) y un evento propio
    ingest_clicks(lake, d2, [ev("E4", f"{d2}T09:00:00Z"), ev("L1", f"{d0}T11:00:00Z", "C2")])
    for d in (d0, d1, d2):
        run_events(lake, d)

    rows = event_rows(lake)
    assert [r["event_id"] for r in rows] == ["E1", "E2", "E3", "E4", "L1"]

    def per_partition() -> dict:
        frame = lake.spark.sql(
            "SELECT partition.event_ts_day AS d, record_count AS n "
            f"FROM {events_table(lake)}.partitions"
        )
        return {str(r["d"]): r["n"] for r in frame.collect()}

    # E1, E2 y el tardio L1 estan en la particion de D (d0), no en la de su ingesta
    assert per_partition() == {d0: 3, d1: 1, d2: 1}

    run_events(lake, d2)  # relanzar D+2 con su tardio: ni duplica ni cambia nada
    run_events(lake, d0)
    assert event_rows(lake) == rows
    assert per_partition() == {d0: 3, d1: 1, d2: 1}
    assert list_branches(lake.spark, events_table(lake)) == ["main"]


def test_u14_email_replaced_by_hmac_and_consent_kept(lake):
    d0 = day(0)
    email = "ana.lopez@example.com"
    consent = ev(
        "E1",
        f"{d0}T10:00:00Z",
        "C1",
        "consent",
        email="  Ana.Lopez@Example.COM ",  # HMAC sobre lower(trim(email))
        consent_ts="2025-03-04T00:00:00Z",
    )
    other = ev("E2", f"{d0}T10:01:00Z", "C1", "add_to_cart", amount=123.455)
    ingest_clicks(lake, d0, [consent, other])
    run_events(lake, d0)

    table = lake.spark.table(events_table(lake))
    assert "email" not in table.columns
    rows = {r["event_id"]: r for r in event_rows(lake)}
    assert rows["E1"]["email_hmac"] == expected_hmac(email)
    assert len(rows["E1"]["email_hmac"]) == 64
    assert rows["E1"]["consent_ts"] == datetime(2025, 3, 4)
    assert rows["E2"]["email_hmac"] is None
    assert rows["E2"]["consent_ts"] == datetime(2025, 1, 1)
    assert str(rows["E2"]["amount"]) == "123.46"  # HALF_EVEN de 123.455 sobre el double del JSON


def test_events_with_same_id_and_different_content_fail_instead_of_picking_one(lake):
    d0 = day(0)
    ingest_clicks(
        lake, d0, [ev("E1", f"{d0}T10:00:00Z"), ev("E1", f"{d0}T10:00:00Z", etype="search")]
    )

    with pytest.raises(WapCheckError) as err:
        run_events(lake, d0)
    assert [f.rule for f in err.value.failures] == ["events_conflicting_ids"]
    assert event_rows(lake) == []


def test_event_id_already_published_with_different_content_fails(lake):
    d0, d1 = day(0), day(1)
    ingest_clicks(lake, d0, [ev("E1", f"{d0}T10:00:00Z")])
    run_events(lake, d0)
    published = event_rows(lake)
    changed = ev("E1", f"{d0}T10:00:00Z", etype="search")
    ingest_clicks(lake, d1, [changed, ev("E2", f"{d1}T09:00:00Z")])

    with pytest.raises(WapCheckError) as err:
        run_events(lake, d1)
    assert [f.rule for f in err.value.failures] == ["events_conflicting_published"]
    assert event_rows(lake) == published  # tampoco se publica E2


def test_rotated_hmac_key_does_not_break_rerun_of_a_day_with_consent_events(lake, monkeypatch):
    d0, d1 = day(0), day(1)
    consent = ev("E1", f"{d0}T10:00:00Z", "C1", "consent", email="ana@example.com")
    ingest_clicks(lake, d0, [consent])
    run_events(lake, d0)
    published = event_rows(lake)

    monkeypatch.setenv(silver_events.HMAC_KEY_ENV, "rotated-key")
    ingest_clicks(lake, d1, [dict(consent), ev("E2", f"{d1}T09:00:00Z")])  # reentrega de E1
    run_events(lake, d1)

    rows = {r["event_id"]: r for r in event_rows(lake)}
    assert rows["E1"] == published[0]  # el hash viejo se queda: el MERGE solo inserta
    assert set(rows) == {"E1", "E2"}


def test_purchase_without_booking_id_is_not_published(lake):
    d0 = day(0)
    ingest_clicks(lake, d0, [ev("E1", f"{d0}T10:00:00Z", etype="purchase")])

    with pytest.raises(WapCheckError) as err:
        run_events(lake, d0)
    assert [f.rule for f in err.value.failures] == ["expression:purchase_has_booking"]
    assert event_rows(lake) == []


def test_hmac_key_comes_from_env_then_ssm_and_never_from_argv():
    class FakeSsm:
        def __init__(self):
            self.calls = []

        def get_parameter(self, **kwargs):
            self.calls.append(kwargs)
            return {"Parameter": {"Value": "ssm-key"}}

    ssm = FakeSsm()
    env_key = silver_events.resolve_hmac_key("/p", "eu-west-3", {"SKYROUTE_HMAC_KEY": "k"}, ssm)
    assert env_key == b"k" and ssm.calls == []
    ssm_key = silver_events.resolve_hmac_key("/skyroute/dev/hmac-email-key", "eu-west-3", {}, ssm)
    assert ssm_key == b"ssm-key"
    assert ssm.calls == [{"Name": "/skyroute/dev/hmac-email-key", "WithDecryption": True}]
    with pytest.raises(ValueError, match="vacia"):
        silver_events.resolve_hmac_key("/p", "eu-west-3", {"SKYROUTE_HMAC_KEY": ""}, FakeSsmEmpty())


class FakeSsmEmpty:
    def get_parameter(self, **kwargs):
        return {"Parameter": {"Value": ""}}


def test_hmac_failure_does_not_leak_the_email():
    email = "ana.lopez@example.com"
    with pytest.raises(ValueError) as caught:
        silver_events.make_hmac_fn(None)(email)  # clave invalida: hmac.new lanza TypeError
    assert email not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert silver_events.make_hmac_fn(b"k")("  ") is None


def test_missing_checks_file_fails_before_writing(lake, tmp_path):
    with pytest.raises(FileNotFoundError, match="events.yaml"):
        silver_events.main(silver_argv(lake, day(1), tmp_path))
    assert not lake.spark.catalog.tableExists(f"{lake.catalog}.{SILVER}.events")
