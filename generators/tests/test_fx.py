import gzip
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fx import ecb

XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
    xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <Cube>
    <Cube time="2026-01-05">
      <Cube currency="USD" rate="1.1700"/><Cube currency="GBP" rate="0.8700"/></Cube>
    <Cube time="2026-01-02">
      <Cube currency="USD" rate="1.1600"/><Cube currency="GBP" rate="0.8600"/></Cube>
  </Cube>
</gesmes:Envelope>
"""
EMPTY = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
    xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube/></gesmes:Envelope>
"""


def _files(root):
    return sorted(p for p in Path(root).rglob("*") if p.is_file())


def test_g6_empty_response_is_an_error_and_writes_nothing(tmp_path):
    with pytest.raises(ecb.FxError):
        ecb.export_range(EMPTY, "2026-01-05", "2026-01-05", str(tmp_path))
    assert _files(tmp_path) == []


def test_g6_no_publication_on_or_before_the_day_is_an_error_and_writes_nothing(tmp_path):
    with pytest.raises(ecb.FxError):
        ecb.export_range(XML, "2026-01-01", "2026-01-05", str(tmp_path))
    assert _files(tmp_path) == []


def test_invalid_xml_is_an_error(tmp_path):
    with pytest.raises(ecb.FxError):
        ecb.export_range(b"<html>", "2026-01-05", "2026-01-05", str(tmp_path))
    assert _files(tmp_path) == []


def test_weekend_carries_last_business_day_with_its_real_rate_date(tmp_path):
    written = ecb.export_range(XML, "2026-01-03", "2026-01-05", str(tmp_path))
    assert [p.parent.name for p in written] == [
        "ingest_date=2026-01-03", "ingest_date=2026-01-04", "ingest_date=2026-01-05",
    ]
    text = gzip.decompress(written[0].read_bytes()).decode()
    saturday = [json.loads(x) for x in text.splitlines()]
    assert {r["rate_date"] for r in saturday} == {"2026-01-02"}
    assert {r["fx_date"] for r in saturday} == {"2026-01-03"}
    assert {r["currency"]: r["rate"] for r in saturday} == {"GBP": 0.86, "USD": 1.16}
    monday = [json.loads(x) for x in gzip.decompress(written[2].read_bytes()).decode().splitlines()]
    assert {r["rate_date"] for r in monday} == {"2026-01-05"}


def test_business_day_without_its_own_publication_is_an_error(tmp_path):
    with pytest.raises(ecb.FxError):
        ecb.export_range(XML, "2026-01-06", "2026-01-06", str(tmp_path))
    assert _files(tmp_path) == []


def test_weekend_without_later_publication_is_an_error(tmp_path):
    only_friday = XML.split(b'<Cube time="2026-01-05">')[0] + b"</Cube></gesmes:Envelope>"
    with pytest.raises(ecb.FxError):
        ecb.export_range(only_friday, "2026-01-03", "2026-01-03", str(tmp_path))
    assert _files(tmp_path) == []


def test_weekend_with_later_publication_takes_last_rate_before_it(tmp_path):
    written = ecb.export_range(XML, "2026-01-04", "2026-01-04", str(tmp_path))
    rows = [json.loads(x) for x in gzip.decompress(written[0].read_bytes()).decode().splitlines()]
    assert {r["rate_date"] for r in rows} == {"2026-01-02"}


def test_needs_full_series_only_when_date_is_older_than_85_days():
    series = ecb.parse_series(XML)
    assert not ecb.needs_full_series(series, "2025-10-15")
    assert ecb.needs_full_series(series, "2025-10-01")


def test_export_is_byte_identical_in_two_runs(tmp_path):
    first = ecb.export_range(XML, "2026-01-02", "2026-01-05", str(tmp_path / "a"))
    second = ecb.export_range(XML, "2026-01-02", "2026-01-05", str(tmp_path / "b"))
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


def test_fetch_retries_then_fails_without_inventing_rates(monkeypatch):
    calls = []

    def boom(url, timeout):
        calls.append(url)
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(ecb.urllib.request, "urlopen", boom)
    with pytest.raises(ecb.FxError):
        ecb.fetch("https://example.invalid/fx.xml", retries=3, sleep=lambda s: None)
    assert len(calls) == 3


def test_range_end_before_start_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        ecb.export_range(XML, "2026-01-05", "2026-01-03", str(tmp_path))
