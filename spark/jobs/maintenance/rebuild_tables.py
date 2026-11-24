"""Mantenimiento destructivo: DROP TABLE ... PURGE de la lista cerrada de Bronze y Silver.

Uso unico por entorno para el backfill de la Fase 4 (Ruling "Bronze rebuild exception" de
gold-dbt): una vez en dev y una vez en prod al cierre. Fuera de ese backfill no se ejecuta;
Medallion layers e Idempotency siguen en vigor. Runbook: docs/runbooks/gold-dbt-backfill.md.

Salvaguardas, en este orden: `--env` obligatorio; `--catalog-name` debe ser un identificador
simple (`^[a-z_][a-z0-9_]*$`); `--env prod` exige `--confirm-prod`; la identidad de
`sts:GetCallerIdentity` debe ser el rol `skyroute-<env>-local-data` del mismo entorno en la
cuenta 437266392155 (campo `Account` y cuenta del ARN); imprime la lista cerrada; `--dry-run`
termina ahi sin borrar; si no, pide teclear el nombre del entorno
y solo entonces borra, registrando cada DROP.

    python -m jobs.maintenance.rebuild_tables --env dev --warehouse s3://<bucket>/silver --dry-run
"""

import argparse
import logging
import re
import sys
from types import SimpleNamespace

from lib.args import DEFAULT_PACKAGES, DEFAULT_REGION
from lib.entrypoint import exit_on_error
from lib.session import build_spark

LOG = logging.getLogger("maintenance.rebuild_tables")

# Lista cerrada (plan gold-dbt, componente rebuild_tables). No se acepta ninguna tabla por
# argumento: cambiarla exige una PR.
BRONZE_TABLES = ("clickstream", "bookings", "fx", "ad_spend")
SILVER_TABLES = (
    "bookings_scd2",
    "bookings_current",
    "fx_daily",
    "bookings_eur",
    "events",
    "sessions",
    "ad_spend_daily",
)
# Cuenta unica del proyecto (Convention "Bootstrap identity"); constante, no argumento.
ACCOUNT_ID = "437266392155"
CATALOG_NAME_RE = re.compile(r"[a-z_][a-z0-9_]*")


class RebuildRefused(Exception):
    """Una salvaguarda rechaza la ejecucion; no se ha borrado nada."""


def closed_list(env: str) -> list[str]:
    """Identificadores `base.tabla` (sin catalogo) del entorno, en el orden del DROP."""
    bronze = [f"skyroute_{env}_bronze.{t}" for t in BRONZE_TABLES]
    silver = [f"skyroute_{env}_silver.{t}" for t in SILVER_TABLES]
    return bronze + silver


def expected_role(env: str) -> str:
    return f"skyroute-{env}-local-data"


def sts_identity(region: str) -> dict:
    """`sts:GetCallerIdentity` real; los tests inyectan otra funcion."""
    import boto3  # perezoso: sin boto3 falla aqui, antes de borrar nada

    return boto3.client("sts", region_name=region).get_caller_identity()


def check_identity(identity: dict, env: str) -> str:
    """Exige `arn:aws:sts::437266392155:assumed-role/skyroute-<env>-local-data/<sesion>`."""
    arn = identity.get("Arn", "")
    parts = arn.split(":", 5)
    resource = parts[5] if len(parts) == 6 else ""
    pieces = resource.split("/")
    role = pieces[1] if len(pieces) == 3 and pieces[0] == "assumed-role" else None
    arn_account = parts[4] if len(parts) == 6 else None
    if (
        parts[:3] != ["arn", "aws", "sts"]
        or role != expected_role(env)
        or identity.get("Account") != ACCOUNT_ID
        or arn_account != ACCOUNT_ID
    ):
        raise RebuildRefused(
            f"identidad {arn!r} no es el rol {expected_role(env)} de la cuenta {ACCOUNT_ID} "
            f"para --env {env}; no se borra nada"
        )
    return arn


def check_catalog_name(name: str) -> str:
    """El catalogo se interpola en el DROP: solo un identificador simple."""
    if not CATALOG_NAME_RE.fullmatch(name):
        raise RebuildRefused(
            f"--catalog-name {name!r} no es un identificador valido; no se borra nada"
        )
    return name


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    parser.add_argument("--env", choices=("dev", "prod"), required=True)
    parser.add_argument("--confirm-prod", action="store_true", help="obligatorio con --env prod")
    parser.add_argument("--dry-run", action="store_true", help="imprime la lista y no borra")
    parser.add_argument("--catalog-name", default="skyroute")
    parser.add_argument("--catalog-impl", choices=("glue", "hadoop"), default="glue")
    parser.add_argument("--warehouse", required=True)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--jars-packages", default=DEFAULT_PACKAGES)
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    if args.catalog_impl == "glue" and not args.warehouse.startswith("s3://"):
        parser.error(f"con catalogo glue --warehouse debe empezar por s3://: {args.warehouse!r}")
    return args


def run(args, identity_fn=sts_identity, input_fn=input, spark_fn=build_spark) -> list[str]:
    """Devuelve los identificadores borrados; lanza RebuildRefused sin borrar si algo falla."""
    check_catalog_name(args.catalog_name)
    if args.env == "prod" and not args.confirm_prod:
        raise RebuildRefused("--env prod exige --confirm-prod; no se borra nada")
    arn = check_identity(identity_fn(args.region), args.env)
    LOG.info("rebuild_tables env=%s identidad=%s", args.env, arn)
    tables = closed_list(args.env)
    print(f"rebuild_tables --env {args.env}: lista cerrada ({len(tables)} tablas)", flush=True)
    for table in tables:
        print(f"  {args.catalog_name}.{table}", flush=True)
    if args.dry_run:
        print("--dry-run: no se borra nada", flush=True)
        return []
    typed = input_fn(f"Escribe el nombre del entorno ({args.env}) para borrar: ").strip()
    if typed != args.env:
        raise RebuildRefused(f"confirmacion {typed!r} distinta de {args.env!r}; no se borra nada")
    spark = spark_fn(SimpleNamespace(**vars(args), dates=[f"rebuild-{args.env}"]))
    dropped = []
    for table in tables:
        identifier = f"{args.catalog_name}.{table}"
        spark.sql(f"DROP TABLE IF EXISTS {identifier} PURGE")
        LOG.info("rebuild_tables env=%s DROP PURGE %s", args.env, identifier)
        dropped.append(identifier)
    LOG.info("rebuild_tables env=%s terminado: %d tablas", args.env, len(dropped))
    return dropped


def main(argv=None, identity_fn=sts_identity, input_fn=input, spark_fn=build_spark) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv)
    try:
        run(args, identity_fn=identity_fn, input_fn=input_fn, spark_fn=spark_fn)
    except RebuildRefused as exc:
        LOG.error("rebuild_tables rechazado: %s", exc)
        print(f"rechazado: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    exit_on_error(main())
