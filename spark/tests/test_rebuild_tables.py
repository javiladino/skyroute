"""Tests de rebuild_tables (S8). Catalogo hadoop local; sts e input simulados, sin AWS."""

import pytest
from conftest import Lake
from jobs.maintenance import rebuild_tables

ACCOUNT = "437266392155"


def identity(role: str):
    arn = f"arn:aws:sts::{ACCOUNT}:assumed-role/{role}/botocore-session-1"
    return lambda region: {"Account": ACCOUNT, "Arn": arn, "UserId": "AROAEXAMPLE:x"}


def typed(text: str, prompts: list):
    def _input(prompt: str) -> str:
        prompts.append(prompt)
        return text

    return _input


def never_input(prompt: str) -> str:
    raise AssertionError("no debe pedir confirmacion")


def argv(lake: Lake, *extra: str) -> list[str]:
    return [
        "--catalog-name", lake.catalog,
        "--catalog-impl", "hadoop",
        "--warehouse", lake.warehouse,
        "--jars-packages", "none",
        *extra,
    ]  # fmt: skip


def create_all(lake: Lake, env: str = "dev") -> str:
    """Crea las 11 tablas de la lista y una ajena en Bronze; devuelve la ajena."""
    for identifier in rebuild_tables.closed_list(env):
        database = identifier.split(".")[0]
        lake.spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake.catalog}.{database}")
        lake.spark.sql(f"CREATE TABLE {lake.catalog}.{identifier} (id bigint) USING iceberg")
        lake.spark.sql(f"INSERT INTO {lake.catalog}.{identifier} VALUES (1)")
    other = f"{lake.catalog}.skyroute_{env}_bronze.keep_me"
    lake.spark.sql(f"CREATE TABLE {other} (id bigint) USING iceberg")
    return other


def existing(lake: Lake, env: str = "dev") -> set[str]:
    names = set()
    for layer in ("bronze", "silver"):
        rows = lake.spark.sql(f"SHOW TABLES IN {lake.catalog}.skyroute_{env}_{layer}").collect()
        names |= {f"skyroute_{env}_{layer}.{r['tableName']}" for r in rows}
    return names


def all_present(lake: Lake, env: str = "dev") -> bool:
    return set(rebuild_tables.closed_list(env)) <= existing(lake, env)


def test_rebuild_tables_closed_list(lake):
    other = create_all(lake)
    prompts = []
    rc = rebuild_tables.main(
        argv(lake, "--env", "dev"),
        identity_fn=identity("skyroute-dev-local-data"),
        input_fn=typed("dev", prompts),
    )
    assert rc == 0
    assert existing(lake) == {"skyroute_dev_bronze.keep_me"}
    assert lake.spark.table(other).count() == 0
    assert len(prompts) == 1
    assert len(rebuild_tables.closed_list("dev")) == 11


def test_rebuild_tables_prod_guard(lake, capsys):
    create_all(lake, "prod")
    rc = rebuild_tables.main(
        argv(lake, "--env", "prod"),
        identity_fn=identity("skyroute-prod-local-data"),
        input_fn=never_input,
    )
    assert rc == 2
    assert "--confirm-prod" in capsys.readouterr().err
    assert all_present(lake, "prod")
    with pytest.raises(SystemExit):
        rebuild_tables.main(argv(lake), input_fn=never_input)


@pytest.mark.parametrize(
    "role", ["skyroute-prod-local-data", "skyroute-dev-glue-job", "AWSReservedSSO_Admin"]
)
def test_rebuild_tables_identity_mismatch(lake, role):
    create_all(lake)
    rc = rebuild_tables.main(
        argv(lake, "--env", "dev"), identity_fn=identity(role), input_fn=never_input
    )
    assert rc == 2
    assert all_present(lake)


def test_rebuild_tables_identity_rejects_iam_user(lake):
    create_all(lake)
    user = lambda region: {"Arn": f"arn:aws:iam::{ACCOUNT}:user/skyroute-dev-local-data"}  # noqa: E731
    rc = rebuild_tables.main(argv(lake, "--env", "dev"), identity_fn=user, input_fn=never_input)
    assert rc == 2
    assert all_present(lake)


@pytest.mark.parametrize("text", ["prod", "DEV", "", "yes"])
def test_rebuild_tables_typed_confirmation(lake, capsys, text):
    create_all(lake)
    prompts = []
    rc = rebuild_tables.main(
        argv(lake, "--env", "dev"),
        identity_fn=identity("skyroute-dev-local-data"),
        input_fn=typed(text, prompts),
    )
    assert rc == 2
    assert all_present(lake)
    out = capsys.readouterr().out
    for identifier in rebuild_tables.closed_list("dev"):
        assert f"{lake.catalog}.{identifier}" in out
    assert len(prompts) == 1


def test_rebuild_tables_dry_run(lake, capsys):
    create_all(lake)
    rc = rebuild_tables.main(
        argv(lake, "--env", "dev", "--dry-run"),
        identity_fn=identity("skyroute-dev-local-data"),
        input_fn=never_input,
    )
    assert rc == 0
    assert all_present(lake)
    out = capsys.readouterr().out
    for identifier in rebuild_tables.closed_list("dev"):
        assert f"{lake.catalog}.{identifier}" in out
    assert "no se borra nada" in out
