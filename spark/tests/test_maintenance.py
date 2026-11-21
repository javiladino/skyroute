"""Tests de mantenimiento: U20 (expire_snapshots) y rewrite_data_files. Todo local, sin AWS."""

from datetime import date, timedelta

import pytest
from conftest import Lake
from jobs.maintenance import expire_snapshots, rewrite_data_files

DATABASE = "skyroute_dev_silver"
FUTURE = "2099-01-01"  # los snapshots de los tests son anteriores a este corte
PAST = "2000-01-01"  # y posteriores a este
INSERTS = 4


def make_table(lake: Lake) -> str:
    table = f"{lake.catalog}.{DATABASE}.demo"
    lake.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake.catalog}.{DATABASE}")
    lake.spark.sql(f"CREATE TABLE {table} (id bigint, v string) USING iceberg")
    for n in range(INSERTS):
        lake.spark.sql(f"INSERT INTO {table} VALUES ({n}, 'v{n}')")
    return table


def maintenance_argv(lake: Lake, run_date: str, *extra: str) -> list[str]:
    return [
        "--run-date", run_date,
        "--catalog-name", lake.catalog,
        "--catalog-impl", "hadoop",
        "--warehouse", lake.warehouse,
        "--jars-packages", "none",
        "--table", "demo",
        *extra,
    ]  # fmt: skip


def snapshot_count(lake: Lake, table: str) -> int:
    return lake.spark.sql(f"SELECT count(*) FROM {table}.snapshots").first()[0]


def content(lake: Lake, table: str) -> list[tuple]:
    return [tuple(r) for r in lake.spark.table(table).orderBy("id").collect()]


def test_older_than_comes_from_run_date():
    assert expire_snapshots.older_than("2026-01-10", 7) == "2026-01-03 00:00:00"


def test_u20_expire_snapshots_is_deterministic_and_keeps_content(lake):
    table = make_table(lake)
    before = content(lake, table)
    assert snapshot_count(lake, table) == INSERTS

    assert expire_snapshots.main(maintenance_argv(lake, FUTURE, "--force")) == 0
    after_first = snapshot_count(lake, table)
    assert after_first == 1  # retain_last por defecto
    assert expire_snapshots.main(maintenance_argv(lake, FUTURE, "--force")) == 0
    assert snapshot_count(lake, table) == after_first
    assert content(lake, table) == before


def last_commit_date(lake: Lake, table: str) -> date:
    text = lake.spark.sql(
        f"SELECT date_format(max(committed_at), 'yyyy-MM-dd') FROM {table}.snapshots"
    ).first()[0]
    return date.fromisoformat(text)


def test_expire_snapshots_rejects_run_date_after_last_commit_plus_one_day(lake):
    table = make_table(lake)
    last = last_commit_date(lake, table)
    too_late = (last + timedelta(days=2)).isoformat()
    with pytest.raises(ValueError, match="--force"):
        expire_snapshots.main(maintenance_argv(lake, too_late))
    with pytest.raises(ValueError, match="--force"):
        expire_snapshots.main(maintenance_argv(lake, FUTURE))
    assert snapshot_count(lake, table) == INSERTS  # no expiro nada

    # Hasta el ultimo commit + 1 dia se acepta (el corte, 7 dias antes, no expira nada aqui).
    allowed = (last + timedelta(days=1)).isoformat()
    assert expire_snapshots.main(maintenance_argv(lake, allowed)) == 0
    assert snapshot_count(lake, table) == INSERTS

    # Con --force se permite un corte futuro.
    assert expire_snapshots.main(maintenance_argv(lake, too_late, "--force")) == 0


def test_expire_snapshots_with_past_run_date_expires_nothing(lake):
    table = make_table(lake)
    assert expire_snapshots.main(maintenance_argv(lake, PAST)) == 0
    assert snapshot_count(lake, table) == INSERTS


def test_expire_snapshots_keeps_wap_branch(lake):
    table = make_table(lake)
    branch = "run_2026-01-01"
    lake.spark.sql(f"ALTER TABLE {table} SET TBLPROPERTIES ('write.wap.enabled'='true')")
    lake.spark.sql(f"ALTER TABLE {table} CREATE BRANCH `{branch}`")
    # La rama tiene un snapshot propio (como un run que fallo un check) que main no tiene.
    lake.spark.conf.set("spark.wap.branch", branch)
    try:
        lake.spark.sql(f"INSERT INTO {table} VALUES (100, 'wap')")
    finally:
        lake.spark.conf.unset("spark.wap.branch")

    def branch_content() -> list[tuple]:
        df = lake.spark.read.option("branch", branch).table(table).orderBy("id")
        return [tuple(r) for r in df.collect()]

    main_before = content(lake, table)
    branch_before = branch_content()
    assert (100, "wap") in branch_before and (100, "wap") not in main_before

    assert expire_snapshots.main(maintenance_argv(lake, FUTURE, "--force")) == 0
    branches = lake.spark.sql(f"SELECT name FROM {table}.refs WHERE type = 'BRANCH'").collect()
    assert sorted(r["name"] for r in branches) == ["main", branch]
    assert branch_content() == branch_before
    assert content(lake, table) == main_before


def test_expire_snapshots_rejects_non_positive_retention(lake):
    with pytest.raises(SystemExit):
        expire_snapshots.main(maintenance_argv(lake, FUTURE, "--retention-days", "0"))


def test_rewrite_data_files_rejects_a_date_range(lake):
    argv = [
        "--from", "2026-01-01",
        "--to", "2026-01-02",
        "--catalog-name", lake.catalog,
        "--catalog-impl", "hadoop",
        "--warehouse", lake.warehouse,
        "--jars-packages", "none",
        "--table", "demo",
    ]  # fmt: skip
    with pytest.raises(SystemExit, match="solo admite --run-date"):
        rewrite_data_files.main(argv)


def test_rewrite_data_files_compacts_and_keeps_content(lake):
    table = make_table(lake)
    before = content(lake, table)
    files_before = lake.spark.sql(f"SELECT count(*) FROM {table}.files").first()[0]
    assert files_before == INSERTS

    argv = maintenance_argv(lake, "2026-01-01", "--min-input-files", "2")
    assert rewrite_data_files.main(argv) == 0
    files_after = lake.spark.sql(f"SELECT count(*) FROM {table}.files").first()[0]
    assert files_after < files_before
    assert content(lake, table) == before
