"""Tests de Silver ad_spend_daily (rerun, guard schema_mismatch, checks). Todo local, sin AWS."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from jobs.bronze import ingest
from jobs.silver import ad_spend_daily
from lib.schema_guard import SchemaMismatch
from lib.wap import WapCheckError, list_branches
from test_bookings_scd2 import SILVER, silver_argv
from test_schema_guard import old_ddl

GENERATORS = Path(__file__).resolve().parents[2] / "generators"
if str(GENERATORS) not in sys.path:
    sys.path.insert(0, str(GENERATORS))

from ota import ad_spend, keys, model  # noqa: E402

D = "2026-01-05"
D1 = "2026-01-06"


def ingest_spend(lake, run_date: str) -> None:
    ad_spend.write_export(run_date, str(lake.root))
    assert ingest.main(lake.argv("ad_spend", run_date)) == 0


def run_spend(lake, run_date: str) -> None:
    assert ad_spend_daily.main(silver_argv(lake, run_date)) == 0


def spend_table(lake) -> str:
    return f"{lake.catalog}.{SILVER}.ad_spend_daily"


def spend_rows(lake) -> list[dict]:
    frame = lake.spark.table(spend_table(lake)).orderBy("spend_date", "campaign_id")
    return [r.asDict() for r in frame.collect()]


def test_ad_spend_daily_rerun(lake):
    ingest_spend(lake, D)
    ingest_spend(lake, D1)
    run_spend(lake, D)
    run_spend(lake, D1)
    rows = spend_rows(lake)
    assert len(rows) == 2 * len(model.CAMPAIGNS)
    first = {r["campaign_id"]: r for r in rows if r["spend_date"] == date(2026, 1, 5)}
    for src in ad_spend.build_rows(D):
        row = first[src["campaign_id"]]
        assert row["spend"] == Decimal(str(src["spend"])).quantize(Decimal("0.01"))
        assert (row["impressions"], row["clicks"], row["currency"]) == (
            src["impressions"],
            src["clicks"],
            "EUR",
        )
        assert row["_source_file"] == f"landing/ad_spend/ingest_date={D}/part.json.gz"

    run_spend(lake, D)  # relanzar no cambia filas ni conteo
    run_spend(lake, D1)
    assert spend_rows(lake) == rows
    assert list_branches(lake.spark, spend_table(lake)) == ["main"]


def test_ad_spend_conflicting_rows_fail_instead_of_picking_one(lake):
    rows = ad_spend.build_rows(D)
    lake.write_landing(
        f"landing/ad_spend/ingest_date={D}/part.json.gz",
        rows + [{**rows[0], "spend": rows[0]["spend"] + 1}],
    )
    assert ingest.main(lake.argv("ad_spend", D)) == 0
    with pytest.raises(WapCheckError) as err:
        run_spend(lake, D)
    assert [f.rule for f in err.value.failures] == ["ad_spend_conflicting_rows"]
    assert spend_rows(lake) == []


def test_ad_spend_date_mismatch_fails_without_writing(lake):
    rows = ad_spend.build_rows(D)
    lake.write_landing(
        f"landing/ad_spend/ingest_date={D}/part.json.gz",
        rows[1:] + [{**rows[0], "spend_date": D1}],
    )
    assert ingest.main(lake.argv("ad_spend", D)) == 0
    with pytest.raises(WapCheckError) as err:
        run_spend(lake, D)
    assert [f.rule for f in err.value.failures] == ["ad_spend_date_mismatch"]
    assert spend_rows(lake) == []


def test_accepted_campaign_ids_match_generator():
    rules = yaml.safe_load((ad_spend_daily.DEFAULT_CHECKS_DIR / "ad_spend_daily.yaml").read_text())
    accepted = next(
        c["values"]
        for c in rules["checks"]
        if c["type"] == "accepted_values" and c["column"] == "campaign_id"
    )
    assert accepted == [keys.campaign_id(n) for n in range(1, len(model.CAMPAIGNS) + 1)]


def test_ad_spend_unknown_campaign_and_negative_spend_are_not_published(lake):
    rows = ad_spend.build_rows(D)
    bad = [{**rows[0], "campaign_id": "CMP-9999"}, {**rows[1], "spend": -1.0}]
    lake.write_landing(f"landing/ad_spend/ingest_date={D}/part.json.gz", bad)
    assert ingest.main(lake.argv("ad_spend", D)) == 0
    with pytest.raises(WapCheckError) as err:
        run_spend(lake, D)
    rules = {f.rule for f in err.value.failures}
    assert {"accepted_values:campaign_id", "expression:spend_not_negative"} <= rules
    assert list_branches(lake.spark, spend_table(lake)) == [f"run_{D}"]


def test_schema_mismatch_ad_spend_daily(lake):
    ingest_spend(lake, D)
    target = spend_table(lake)
    lake.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake.catalog}.{SILVER}")
    lake.spark.sql(old_ddl(ad_spend_daily.DDL, dropped=("clicks",)).format(table=target))

    with pytest.raises(SchemaMismatch, match="schema_mismatch") as err:
        run_spend(lake, D)
    assert "clicks" in str(err.value)
    assert lake.spark.table(target).count() == 0
    assert list_branches(lake.spark, target) == []
