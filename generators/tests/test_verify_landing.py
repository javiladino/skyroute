import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_landing  # noqa: E402

D = "2026-11-13"


def test_ts_u10_complete_listing_has_no_diff():
    keys = verify_landing.expected_keys(D)
    assert len(keys) == 182 * 96
    report = verify_landing.compare(keys, D)
    assert report["missing"] == [] and report["extra"] == []
    assert set(report["per_day"].values()) == {96}


def test_missing_key_is_named_and_day_has_95():
    keys = set(verify_landing.expected_keys(D))
    gone = "landing/clickstream/ingest_date=2026-11-12/slot=95/part.json.gz"
    keys.remove(gone)
    report = verify_landing.compare(keys, D)
    assert report["missing"] == [gone]
    assert report["per_day"]["2026-11-12"] == 95


def test_extra_key_is_named():
    keys = set(verify_landing.expected_keys(D))
    extra = "landing/clickstream/ingest_date=2026-11-12/slot=96/part.json.gz"
    keys.add(extra)
    assert verify_landing.compare(keys, D)["extra"] == [extra]


def test_keys_from_d_onward_are_ignored():
    keys = set(verify_landing.expected_keys(D))
    keys.add("landing/clickstream/ingest_date=2026-11-13/slot=00/part.json.gz")
    keys.add("landing/clickstream/ingest_date=2026-11-20/slot=00/part.json.gz")
    report = verify_landing.compare(keys, D)
    assert report["missing"] == [] and report["extra"] == []


def test_main_exit_codes(tmp_path, capsys):
    keys = sorted(verify_landing.expected_keys(D))
    listing = tmp_path / "ok.json"
    listing.write_text(json.dumps({"Contents": [{"Key": k} for k in keys]}))
    assert verify_landing.main(["--listing", str(listing), "--d", D]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"Contents": [{"Key": k} for k in keys[1:]]}))
    assert verify_landing.main(["--listing", str(bad), "--d", D]) == 1
    assert keys[0] in capsys.readouterr().out
