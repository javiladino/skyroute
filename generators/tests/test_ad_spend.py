import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from ota import ad_spend, model
from ota.keys import AD_SPEND_PREFIX, daily_key

DAY = "2026-05-01"


def _rows(payload):
    return [json.loads(line) for line in gzip.decompress(payload).decode("utf-8").splitlines()]


def test_daily_key_format():
    assert daily_key(AD_SPEND_PREFIX, DAY) == "landing/ad_spend/ingest_date=2026-05-01/part.json.gz"


def test_one_row_per_campaign_with_landing_schema():
    rows = _rows(ad_spend.generate(DAY))
    assert [r["campaign_id"] for r in rows] == [f"CMP-{n:04d}" for n in range(1, 9)]
    assert len(rows) == len(model.CAMPAIGNS)
    for row in rows:
        assert set(row) == {"spend_date", "campaign_id", "spend", "currency", "impressions",
                            "clicks"}
        assert row["spend_date"] == DAY
        assert row["currency"] == "EUR"
        assert row["spend"] >= 0 and round(row["spend"], 2) == row["spend"]
        assert 0 <= row["clicks"] <= row["impressions"]


def test_cli_rerun_gives_same_bytes_and_path(tmp_path):
    assert ad_spend.main(["--run-date", DAY, "--out-dir", str(tmp_path / "a")]) == 0
    assert ad_spend.main(["--run-date", DAY, "--out-dir", str(tmp_path / "b")]) == 0
    first = (tmp_path / "a" / daily_key(AD_SPEND_PREFIX, DAY)).read_bytes()
    second = (tmp_path / "b" / daily_key(AD_SPEND_PREFIX, DAY)).read_bytes()
    assert first == second == ad_spend.generate(DAY)


def test_range_output_is_byte_identical_to_each_single_day(tmp_path):
    days = ["2026-04-29", "2026-04-30", "2026-05-01", "2026-05-02"]
    rng = tmp_path / "range"
    assert ad_spend.main(["--from", days[0], "--to", days[-1], "--out-dir", str(rng)]) == 0
    written = sorted(p.relative_to(rng) for p in rng.rglob("*.json.gz"))
    assert written == sorted(Path(daily_key(AD_SPEND_PREFIX, d)) for d in days)
    for d in days:
        single = tmp_path / d
        assert ad_spend.main(["--run-date", d, "--out-dir", str(single)]) == 0
        key = daily_key(AD_SPEND_PREFIX, d)
        assert (rng / key).read_bytes() == (single / key).read_bytes()


def test_range_args_are_validated(tmp_path):
    out = str(tmp_path)
    assert ad_spend.main(["--from", "2026-05-02", "--to", "2026-05-01", "--out-dir", out]) == 2
    with pytest.raises(SystemExit):
        ad_spend.main(["--run-date", DAY, "--from", DAY, "--to", DAY, "--out-dir", out])
    with pytest.raises(SystemExit):
        ad_spend.main(["--from", DAY, "--out-dir", out])
    with pytest.raises(SystemExit):
        ad_spend.main(["--run-date", DAY, "--to", DAY, "--out-dir", out])
    assert not list(tmp_path.rglob("*.json.gz"))


def test_invalid_date_is_rejected(tmp_path):
    assert ad_spend.main(["--run-date", "2026-13-01", "--out-dir", str(tmp_path)]) == 2
    with pytest.raises(ValueError):
        ad_spend.generate("nope")
