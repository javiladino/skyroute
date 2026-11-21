"""Silver fx_daily: un tipo por (dia natural, divisa) desde skyroute_<env>_bronze.fx.

Lee solo la particion `_ingest_date = D` de Bronze. El generador (fx/ecb.py) escribe un
archivo por dia natural; sabados, domingos y festivos llevan los tipos de la ultima publicacion
del BCE <= D con su `rate_date` real, que aqui queda en `source_date`. `rate_per_eur` es la
cotizacion del BCE sin transformar: unidades de la divisa por 1 EUR (amount_eur = amount /
rate_per_eur).

Sin arrastre en Silver: el arrastre de fin de semana lo hace solo el generador (un archivo por
dia natural con la ultima publicacion <= D y su rate_date). Si falta D en Bronze, fx_daily no
publica; Silver nunca rellena D con el tipo de otro dia.

Reemplazo por fecha: DELETE de `fx_date = D` e INSERT del lote, ambos en la rama WAP. Si Bronze no
trae ningun tipo para D el job registra un fallo de check `fx_rate_available` y no publica
(Design Decision 6). Si el lote trae la misma (fx_date, currency) con tipo o source_date
distintos, falla `fx_conflicting_rates` en vez de elegir uno. Checks: spark/checks/fx_daily.yaml.

    python -m jobs.silver.fx_daily --run-date 2026-01-01 --warehouse s3://<bucket>/silver
"""

import copy
import logging
import sys
from pathlib import Path

from jobs.silver.bookings_scd2 import DEFAULT_CHECKS_DIR
from lib.args import parse_args
from lib.checks import Failure
from lib.session import build_spark
from lib.wap import WapCheckError, branch_name, run_wap
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

LOG = logging.getLogger("silver.fx_daily")

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    fx_date date,
    currency string,
    rate_per_eur decimal(18,6),
    source_date date
) USING iceberg
PARTITIONED BY (fx_date)
TBLPROPERTIES (
    'format-version' = '2',
    'write.wap.enabled' = 'true',
    'write.merge.mode' = 'copy-on-write',
    'write.update.mode' = 'copy-on-write',
    'write.delete.mode' = 'copy-on-write'
)
"""


def _extra_args(parser):
    parser.add_argument("--bronze-database", help="por defecto skyroute_<env>_bronze")
    parser.add_argument("--silver-database", help="por defecto skyroute_<env>_silver")
    parser.add_argument("--checks-dir", type=Path, default=DEFAULT_CHECKS_DIR)


def rates_from_bronze(bronze, run_date: str):
    """Tipos del dia D sin filas exactamente repetidas; los conflictos los detecta write_rates."""
    day = F.to_date(F.lit(run_date))
    typed = bronze.where((F.col("_ingest_date") == day) & (F.col("base") == "EUR")).select(
        day.alias("fx_date"),
        "currency",
        F.col("rate").cast("decimal(18,6)").alias("rate_per_eur"),
        F.to_date("rate_date").alias("source_date"),
    )
    return typed.distinct()


def write_rates(spark: SparkSession, target: str, rates, run_date: str) -> int:
    rows = rates.count()
    if rows == 0:
        failure = Failure("fx_rate_available", f"Bronze sin tipos para {run_date}", 0)
        raise WapCheckError(branch_name(run_date), [failure])
    conflicts = rates.groupBy("fx_date", "currency").count().where(F.col("count") > 1).count()
    if conflicts:
        message = f"{conflicts} divisas de {run_date} con tipo o source_date distintos en Bronze"
        raise WapCheckError(
            branch_name(run_date), [Failure("fx_conflicting_rates", message, conflicts)]
        )
    rates.createOrReplaceTempView("_fx_batch")
    spark.sql(f"DELETE FROM {target} WHERE fx_date = DATE '{run_date}'")
    spark.sql(f"INSERT INTO {target} SELECT * FROM _fx_batch")
    return rows


def run(spark: SparkSession, args) -> dict:
    tz = spark.conf.get("spark.sql.session.timeZone")
    assert tz == "UTC", f"spark.sql.session.timeZone debe ser UTC, es {tz!r}"
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    source = f"{args.catalog_name}.{bronze_db}.fx"
    target = f"{args.catalog_name}.{silver_db}.fx_daily"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))

    rates = rates_from_bronze(spark.table(source), args.run_date).cache()
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_rates(session, target, rates, args.run_date)

    try:
        run_wap(spark, target, args.run_date, write, args.checks_dir / "fx_daily.yaml")
    finally:
        rates.unpersist()
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver fx_daily %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    spark = build_spark(args)
    last_ok = None
    for day in args.dates:
        day_args = copy.copy(args)
        day_args.run_date = day
        try:
            run(spark, day_args)
        except Exception:
            resume = f"--from {day}" + (f" --to {args.date_to}" if args.date_to else "")
            LOG.error("fallo en %s; ultima fecha OK: %s; reanuda con %s", day, last_ok, resume)
            raise
        last_ok = day
    return 0


if __name__ == "__main__":
    sys.exit(main())
