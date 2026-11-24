"""Silver ad_spend_daily: gasto por (dia, campana) desde skyroute_<env>_bronze.ad_spend.

Lee solo la particion `_ingest_date = D` de Bronze. El generador (generators/ota/ad_spend.py)
escribe un archivo por dia con una fila por campana; `spend` viene en EUR y pasa a
decimal(10,2) con HALF_EVEN. Lleva tambien las columnas tecnicas de Bronze
(lib/technical_columns.py) para trazar cada fila a su archivo de landing.

Reemplazo por fecha, como fx_daily: DELETE de `spend_date = D` e INSERT del lote, ambos en la rama
WAP; relanzar D deja la tabla igual (Idempotency). Si el lote trae la misma
(spend_date, campaign_id) con valores distintos, falla `ad_spend_conflicting_rows` en vez de
elegir uno. Antes de escribir, el guard `schema_mismatch` (lib/schema_guard.py) exige que la tabla
existente tenga todas las columnas del DDL. Checks: spark/checks/ad_spend_daily.yaml.

    python -m jobs.silver.ad_spend_daily --run-date 2026-01-01 --warehouse s3://<bucket>/silver
"""

import copy
import logging
from pathlib import Path

from lib.args import parse_args
from lib.checks import Failure, require_rules_file
from lib.entrypoint import exit_on_error
from lib.schema_guard import ddl_columns, require_columns
from lib.session import build_spark
from lib.technical_columns import TECHNICAL_COLUMNS
from lib.wap import WapCheckError, branch_name, run_wap
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from jobs.silver.bookings_scd2 import DEFAULT_CHECKS_DIR

LOG = logging.getLogger("silver.ad_spend_daily")
KEY = ("spend_date", "campaign_id")

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    spend_date date,
    campaign_id string,
    spend decimal(10,2),
    currency string,
    impressions int,
    clicks int,
    _ingested_at timestamp,
    _batch_id string,
    _source_file string,
    _ingest_date date
) USING iceberg
PARTITIONED BY (spend_date)
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


def spend_from_bronze(bronze, run_date: str):
    """Gasto del dia D tipado, sin filas exactamente repetidas; conflictos en write_spend."""
    day = F.to_date(F.lit(run_date))
    typed = bronze.where(F.col("_ingest_date") == day).select(
        F.to_date("spend_date").alias("spend_date"),
        "campaign_id",
        F.bround(F.col("spend").cast("decimal(18,6)"), 2).cast("decimal(10,2)").alias("spend"),
        "currency",
        F.col("impressions").cast("int").alias("impressions"),
        F.col("clicks").cast("int").alias("clicks"),
        *TECHNICAL_COLUMNS,
    )
    return typed.distinct()


def write_spend(spark: SparkSession, target: str, spend, run_date: str) -> int:
    rows = spend.count()
    conflicts = spend.groupBy(*KEY).count().where(F.col("count") > 1).count()
    if conflicts:
        message = f"{conflicts} campanas de {run_date} con valores distintos en Bronze"
        raise WapCheckError(
            branch_name(run_date), [Failure("ad_spend_conflicting_rows", message, conflicts)]
        )
    spend.createOrReplaceTempView("_ad_spend_batch")
    spark.sql(f"DELETE FROM {target} WHERE spend_date = DATE '{run_date}'")
    if rows:
        spark.sql(f"INSERT INTO {target} SELECT * FROM _ad_spend_batch")
    return rows


def run(spark: SparkSession, args) -> dict:
    tz = spark.conf.get("spark.sql.session.timeZone")
    assert tz == "UTC", f"spark.sql.session.timeZone debe ser UTC, es {tz!r}"
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    source = f"{args.catalog_name}.{bronze_db}.ad_spend"
    target = f"{args.catalog_name}.{silver_db}.ad_spend_daily"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))
    require_columns(spark, target, ddl_columns(DDL))

    spend = spend_from_bronze(spark.table(source), args.run_date).cache()
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_spend(session, target, spend, args.run_date)

    try:
        run_wap(spark, target, args.run_date, write, args.checks_dir / "ad_spend_daily.yaml")
    finally:
        spend.unpersist()
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver ad_spend_daily %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    require_rules_file(args.checks_dir / "ad_spend_daily.yaml")
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
    exit_on_error(main())
