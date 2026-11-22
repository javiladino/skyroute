"""Silver bookings_scd2: historial SCD2 de Reservas desde skyroute_<env>_bronze.bookings.

Lee solo la particion `_ingest_date = D` de Bronze (sin corte `<= D`: relanzar D en cualquier
momento deja la tabla igual que una ejecucion en orden). Cada fila de Bronze es una version;
la clave unica es (booking_id, history_id) y todo orden usa (changed_at, history_id).

1. Intervalos [valid_from, valid_to) del lote con lead() por reserva.
2. La ultima version del lote toma valid_to del `valid_from` de la primera version posterior
   que ya exista en la tabla (si la hay) y solo queda is_current si no hay ninguna.
3. Cierre acotado de la version previa: con (v0, h0) = (valid_from, history_id) de la primera
   version del lote, se cierran (valid_to = v0, is_current = false) solo las filas con
   (valid_from, history_id) < (v0, h0) y (valid_to IS NULL OR valid_to > v0). Relanzar D tras
   D+1 no toca las versiones de D+1.
   Precondicion (check_versions_within_day): el export de D solo trae changed_at en
   [D, D+1) UTC, asi que el lote nunca se intercala con versiones de otros dias.
4. MERGE de insercion por (booking_id, history_id): las versiones ya existentes no cambian.

Escribe con WAP (rama run_<D>, checks de spark/checks/bookings_scd2.yaml, fast_forward).

    python -m jobs.silver.bookings_scd2 --run-date 2026-01-01 \
        --warehouse s3://<bucket>/silver
"""

import copy
import logging
from pathlib import Path

from lib.args import parse_args
from lib.checks import require_rules_file
from lib.entrypoint import exit_on_error
from lib.session import build_spark
from lib.wap import run_wap
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

LOG = logging.getLogger("silver.bookings_scd2")
DEFAULT_CHECKS_DIR = Path(__file__).resolve().parents[2] / "checks"
TS_FORMAT = "yyyy-MM-dd'T'HH:mm:ssX"
HASH_COLUMNS = (
    "booking_id", "customer_id", "session_id", "campaign_id", "status", "currency",
    "amount", "created_at", "updated_at",
)  # fmt: skip

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    booking_id string,
    history_id bigint,
    customer_id string,
    session_id string,
    campaign_id string,
    status string,
    currency string,
    amount decimal(12,2),
    created_at timestamp,
    updated_at timestamp,
    valid_from timestamp,
    valid_to timestamp,
    is_current boolean,
    row_hash string
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


def amount_decimal():
    """amount a decimal(12,2) con redondeo HALF_EVEN (plan §6); null si no es numerico."""
    return F.bround(F.col("amount").cast("decimal(18,6)"), 2).cast("decimal(12,2)")


def versions_from_bronze(bronze, run_date: str):
    """Versiones del dia D tipadas, sin duplicados de (booking_id, history_id)."""
    day = F.to_date(F.lit(run_date))
    typed = bronze.where(F.col("_ingest_date") == day).select(
        "booking_id",
        "history_id",
        "customer_id",
        "session_id",
        "campaign_id",
        "status",
        "currency",
        amount_decimal().alias("amount"),
        F.to_timestamp("created_at", TS_FORMAT).alias("created_at"),
        F.to_timestamp("updated_at", TS_FORMAT).alias("updated_at"),
        F.to_timestamp("changed_at", TS_FORMAT).alias("valid_from"),
    )
    return typed.dropDuplicates(["booking_id", "history_id"])


def row_hash():
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in HASH_COLUMNS]
    return F.sha2(F.concat_ws("|", *parts), 256)


def build_batch(spark: SparkSession, versions, target: str):
    """Filas del lote con valid_to e is_current ya resueltos contra la tabla actual."""
    order = Window.partitionBy("booking_id").orderBy("valid_from", "history_id")
    newest_first = Window.partitionBy("booking_id").orderBy(
        F.col("valid_from").desc(), F.col("history_id").desc()
    )
    batch = versions.withColumn("_next_vf", F.lead("valid_from").over(order)).withColumn(
        "_rn_desc", F.row_number().over(newest_first)
    )
    last = batch.where(F.col("_rn_desc") == 1).select(
        "booking_id", F.col("valid_from").alias("_lvf"), F.col("history_id").alias("_lhid")
    )
    existing = spark.table(target).select(
        F.col("booking_id").alias("_tb"),
        F.col("valid_from").alias("_tvf"),
        F.col("history_id").alias("_thid"),
    )
    later = last.join(
        existing,
        (F.col("booking_id") == F.col("_tb"))
        & (
            (F.col("_tvf") > F.col("_lvf"))
            | ((F.col("_tvf") == F.col("_lvf")) & (F.col("_thid") > F.col("_lhid")))
        ),
    )
    next_in_target = later.groupBy("booking_id").agg(
        F.min(F.struct("_tvf", "_thid")).getField("_tvf").alias("_target_next_vf")
    )
    joined = batch.join(next_in_target, "booking_id", "left")
    valid_to = F.coalesce(F.col("_next_vf"), F.col("_target_next_vf"))
    return joined.select(
        "booking_id", "history_id", "customer_id", "session_id", "campaign_id", "status",
        "currency", "amount", "created_at", "updated_at", "valid_from",
        valid_to.alias("valid_to"),
        valid_to.isNull().alias("is_current"),
        row_hash().alias("row_hash"),
    )  # fmt: skip


def write_scd2(spark: SparkSession, target: str, versions) -> int:
    batch = build_batch(spark, versions, target).cache()
    rows = batch.count()  # materializa antes de escribir: el lote no se relee tras el MERGE
    try:
        if rows:
            first = batch.groupBy("booking_id").agg(
                F.min(F.struct("valid_from", "history_id")).alias("_f")
            )
            first = first.select(
                "booking_id",
                F.col("_f.valid_from").alias("v0"),
                F.col("_f.history_id").alias("h0"),
            )
            first.createOrReplaceTempView("_scd2_first")
            batch.createOrReplaceTempView("_scd2_batch")
            spark.sql(
                f"""
                MERGE INTO {target} t USING _scd2_first s
                ON t.booking_id = s.booking_id
                   AND (t.valid_from < s.v0 OR (t.valid_from = s.v0 AND t.history_id < s.h0))
                   AND (t.valid_to IS NULL OR t.valid_to > s.v0)
                WHEN MATCHED THEN UPDATE SET t.valid_to = s.v0, t.is_current = false
                """
            )
            spark.sql(
                f"""
                MERGE INTO {target} t USING _scd2_batch s
                ON t.booking_id = s.booking_id AND t.history_id = s.history_id
                WHEN NOT MATCHED THEN INSERT *
                """
            )
    finally:
        batch.unpersist()
    return rows


def check_versions_within_day(versions, run_date: str) -> None:
    """Precondicion: el export de D solo trae changed_at dentro de [D, D+1) UTC.

    Lo garantiza generators/ota/export_bookings.py (WHERE changed_at >= D AND < D+1). Si algun
    valid_from cae fuera, el lote podria intercalarse con versiones de otros dias y dejar
    intervalos solapados; se falla antes de escribir nada.
    """
    start = F.to_timestamp(F.lit(run_date))
    outside = versions.where(
        F.col("valid_from").isNull()
        | (F.col("valid_from") < start)
        | (F.col("valid_from") >= start + F.expr("INTERVAL 1 DAY"))
    )
    bad = outside.count()
    if bad:
        raise ValueError(
            f"{bad} versiones de Bronze con changed_at fuera de [{run_date}, {run_date}+1d) UTC; "
            "el export diario no lo permite, no se escribe nada"
        )


def run(spark: SparkSession, args) -> dict:
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    source = f"{args.catalog_name}.{bronze_db}.bookings"
    target = f"{args.catalog_name}.{silver_db}.bookings_scd2"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))

    versions = versions_from_bronze(spark.table(source), args.run_date)
    check_versions_within_day(versions, args.run_date)
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_scd2(session, target, versions)

    run_wap(spark, target, args.run_date, write, args.checks_dir / "bookings_scd2.yaml")
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver bookings_scd2 %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    require_rules_file(args.checks_dir / "bookings_scd2.yaml")
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
