"""Mantenimiento: expira los snapshots Iceberg anteriores a `run_date - retention_days`.

El corte sale de `--run-date` (00:00 UTC menos `--retention-days`), nunca del reloj: dos
ejecuciones con la misma fecha expiran lo mismo. Siempre se conservan los `--retain-last`
snapshots mas recientes y los que referencian ramas o tags (p. ej. una rama WAP `run_<D>` que
fallo un check y espera inspeccion). El contenido de la tabla en `main` no cambia.

    python -m jobs.maintenance.expire_snapshots --run-date 2026-01-01 --table events \
        --warehouse s3://<bucket>/silver
"""

import copy
import logging
from datetime import date, datetime, time, timedelta

from lib.args import parse_args
from lib.entrypoint import exit_on_error
from lib.session import build_spark
from pyspark.sql import SparkSession

LOG = logging.getLogger("maintenance.expire_snapshots")


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ValueError("debe ser >= 1")
    return number


def _extra_args(parser):
    parser.add_argument("--table", required=True, help="nombre de la tabla, sin base ni catalogo")
    parser.add_argument("--database", help="por defecto skyroute_<env>_silver")
    parser.add_argument("--retention-days", type=_positive, default=7)
    parser.add_argument("--retain-last", type=_positive, default=1)
    parser.add_argument(
        "--force",
        action="store_true",
        help="permite un --run-date posterior al ultimo commit de la tabla + 1 dia",
    )


def older_than(run_date: str, retention_days: int) -> str:
    """Corte en texto `YYYY-MM-DD HH:MM:SS` (UTC) derivado solo de la fecha logica."""
    cutoff = datetime.combine(date.fromisoformat(run_date), time.min) - timedelta(
        days=retention_days
    )
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


def check_run_date_not_in_future(spark: SparkSession, table: str, run_date: str) -> None:
    """Rechaza un `run_date` mas de un dia posterior al ultimo commit de la tabla.

    Un run_date lejano en el futuro (p. ej. un typo 2062 por 2026) pone el corte por encima de
    todos los snapshots y solo `--retain-last` sobreviviria. La comparacion usa la fecha del
    ultimo `committed_at` (UTC), no el reloj, para que siga siendo reproducible.
    """
    last = spark.sql(
        f"SELECT date_format(max(committed_at), 'yyyy-MM-dd') FROM {table}.snapshots"
    ).first()[0]
    if last is None:
        return
    limit = date.fromisoformat(last) + timedelta(days=1)
    if date.fromisoformat(run_date) > limit:
        raise ValueError(
            f"--run-date {run_date} es posterior al ultimo commit de {table} ({last}) + 1 dia; "
            "usa --force si es intencionado"
        )


def run(spark: SparkSession, args) -> dict:
    tz = spark.conf.get("spark.sql.session.timeZone")
    assert tz == "UTC", f"spark.sql.session.timeZone debe ser UTC, es {tz!r}"
    database = args.database or f"skyroute_{args.env}_silver"
    identifier = f"{database}.{args.table}"
    if not args.force:
        check_run_date_not_in_future(spark, f"{args.catalog_name}.{identifier}", args.run_date)
    cutoff = older_than(args.run_date, args.retention_days)
    row = spark.sql(
        f"CALL {args.catalog_name}.system.expire_snapshots("
        f"table => '{identifier}', older_than => TIMESTAMP '{cutoff}', "
        f"retain_last => {args.retain_last})"
    ).first()
    summary = {
        "run_date": args.run_date,
        "table": f"{args.catalog_name}.{identifier}",
        "older_than": cutoff,
        "deleted_data_files": row["deleted_data_files_count"],
        "deleted_manifest_files": row["deleted_manifest_files_count"],
        "deleted_manifest_lists": row["deleted_manifest_lists_count"],
    }
    LOG.info("expire_snapshots %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    spark = build_spark(args)
    for day in args.dates:
        day_args = copy.copy(args)
        day_args.run_date = day
        run(spark, day_args)
    return 0


if __name__ == "__main__":
    exit_on_error(main())
