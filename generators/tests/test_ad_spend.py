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


def test_invalid_date_is_rejected(tmp_path):
    assert ad_spend.main(["--run-date", "2026-13-01", "--out-dir", str(tmp_path)]) == 2
    with pytest.raises(ValueError):
        ad_spend.generate("nope")
