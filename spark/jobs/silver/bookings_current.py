"""Silver bookings_current: una fila por booking_id con la ultima version conocida.

Lee la particion `_ingest_date = D` de skyroute_<env>_bronze.bookings, se queda con la ultima
version de cada reserva en el lote por (changed_at, history_id) y hace MERGE condicional:
solo actualiza si la version del lote es posterior a la de la tabla por (changed_at,
history_id). Relanzar D tras D+5 no retrocede la tabla. Escribe con WAP (rama run_<D>,
checks de spark/checks/bookings_current.yaml, fast_forward).

    python -m jobs.silver.bookings_current --run-date 2026-01-01 \
        --warehouse s3://<bucket>/silver
"""

import copy
import logging
from pathlib import Path

from lib.args import parse_args
from lib.checks import require_rules_file
from lib.entrypoint import exit_on_error
from lib.schema_guard import ddl_columns, require_columns
from lib.session import build_spark
from lib.wap import run_wap
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

from jobs.silver.bookings_scd2 import DEFAULT_CHECKS_DIR, TS_FORMAT, amount_decimal

LOG = logging.getLogger("silver.bookings_current")

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    booking_id string,
    history_id bigint,
    customer_id string,
    session_id string,
    campaign_id string,
    origin string,
    destination string,
    travel_date date,
    status string,
    currency string,
    amount decimal(12,2),
    created_at timestamp,
    updated_at timestamp,
    changed_at timestamp
) USING iceberg
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


def latest_per_booking(bronze, run_date: str):
    """Ultima version de cada reserva en la particion de D, por (changed_at, history_id)."""
    day = F.to_date(F.lit(run_date))
    typed = bronze.where(F.col("_ingest_date") == day).select(
        "booking_id",
        "history_id",
        "customer_id",
        "session_id",
        "campaign_id",
        "origin",
        "destination",
        F.to_date("travel_date").alias("travel_date"),
        "status",
        "currency",
        amount_decimal().alias("amount"),
        F.to_timestamp("created_at", TS_FORMAT).alias("created_at"),
        F.to_timestamp("updated_at", TS_FORMAT).alias("updated_at"),
        F.to_timestamp("changed_at", TS_FORMAT).alias("changed_at"),
    )
    newest = Window.partitionBy("booking_id").orderBy(
        F.col("changed_at").desc(), F.col("history_id").desc()
    )
    ranked = typed.withColumn("_rn", F.row_number().over(newest))
    return ranked.where(F.col("_rn") == 1).drop("_rn")


def write_current(spark: SparkSession, target: str, latest) -> int:
    rows = latest.count()
    if rows:
        latest.createOrReplaceTempView("_current_batch")
        spark.sql(
            f"""
            MERGE INTO {target} t USING _current_batch s
            ON t.booking_id = s.booking_id
            WHEN MATCHED AND (
                s.changed_at > t.changed_at
                OR (s.changed_at = t.changed_at AND s.history_id > t.history_id)
            ) THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
            """
        )
    return rows


def run(spark: SparkSession, args) -> dict:
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    source = f"{args.catalog_name}.{bronze_db}.bookings"
    target = f"{args.catalog_name}.{silver_db}.bookings_current"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))
    require_columns(spark, target, ddl_columns(DDL))

    latest = latest_per_booking(spark.table(source), args.run_date).cache()
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_current(session, target, latest)

    try:
        run_wap(spark, target, args.run_date, write, args.checks_dir / "bookings_current.yaml")
    finally:
        latest.unpersist()
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver bookings_current %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    require_rules_file(args.checks_dir / "bookings_current.yaml")
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
