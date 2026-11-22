"""Silver bookings_eur: importe de cada reserva en EUR con el tipo del dia de `created_at`.

Lee la particion `_ingest_date = D` de skyroute_<env>_bronze.bookings (ultima version de cada
reserva en el lote, como bookings_current) y busca en silver.fx_daily el tipo de
(fecha UTC de created_at, currency). EUR no lleva tipo en el BCE: se aplica 1. Guarda `currency`,
`amount`, `fx_rate_applied` (cotizacion del BCE: unidades de la divisa por 1 EUR) y
`amount_eur = amount / fx_rate_applied` en decimal(12,2) con HALF_EVEN (plan §6).

El MERGE por `booking_id` solo actualiza si la version del lote es posterior a la de la tabla por
(changed_at, history_id), como bookings_current (ambas columnas se guardan en el target): relanzar
D-1 tras D no retrocede la fila. Hoy el generador no cambia currency/amount/created_at entre
versiones (ota/model.py:90-103), pero la condicion no depende de ello.

Si falta el tipo de algun dia, `fx_rate_applied` queda nulo y el check not_null impide publicar
(correcto: no se publica un importe sin tipo). El fallo indica que falta en silver.fx_daily el
par (fecha UTC de created_at, currency) de esas reservas; carga antes fx_daily de esos dias.

Dependencia con fx_daily: si se corrige fx_daily de un dia X (relanzarlo con otros tipos), las
filas ya publicadas de bookings_eur no se recalculan solas. Hay que relanzar bookings_eur de
los dias en que se ingestaron reservas con created_at en X. Checks: spark/checks/bookings_eur.yaml.

    python -m jobs.silver.bookings_eur --run-date 2026-01-01 --warehouse s3://<bucket>/silver
"""

import copy
import logging
import sys
from pathlib import Path

from lib.args import parse_args
from lib.checks import require_rules_file
from lib.session import build_spark
from lib.wap import run_wap
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from jobs.silver.bookings_current import latest_per_booking
from jobs.silver.bookings_scd2 import DEFAULT_CHECKS_DIR

LOG = logging.getLogger("silver.bookings_eur")

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    booking_id string,
    history_id bigint,
    changed_at timestamp,
    currency string,
    amount decimal(12,2),
    fx_rate_applied decimal(18,6),
    amount_eur decimal(12,2)
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


def convert_to_eur(latest, fx):
    """Une cada reserva con el tipo de su dia de created_at y calcula amount_eur."""
    rates = fx.select(
        F.col("fx_date").alias("_fx_date"),
        F.col("currency").alias("_fx_ccy"),
        F.col("rate_per_eur").alias("_rate"),
    )
    joined = latest.join(
        rates,
        (F.to_date("created_at") == F.col("_fx_date")) & (F.col("currency") == F.col("_fx_ccy")),
        "left",
    )
    applied = F.when(F.col("currency") == "EUR", F.lit(1).cast("decimal(18,6)")).otherwise(
        F.col("_rate")
    )
    converted = joined.withColumn("fx_rate_applied", applied)
    # Numerador a decimal(38,18): el cociente conserva mas decimales antes del bround final.
    amount_eur = F.bround(F.col("amount").cast("decimal(38,18)") / F.col("fx_rate_applied"), 2)
    return converted.select(
        "booking_id",
        "history_id",
        "changed_at",
        "currency",
        "amount",
        "fx_rate_applied",
        amount_eur.cast("decimal(12,2)").alias("amount_eur"),
    )


def write_eur(spark: SparkSession, target: str, converted) -> int:
    rows = converted.count()
    if rows:
        converted.createOrReplaceTempView("_eur_batch")
        spark.sql(
            f"""
            MERGE INTO {target} t USING _eur_batch s
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
    tz = spark.conf.get("spark.sql.session.timeZone")
    assert tz == "UTC", f"spark.sql.session.timeZone debe ser UTC, es {tz!r}"
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    source = f"{args.catalog_name}.{bronze_db}.bookings"
    fx_table = f"{args.catalog_name}.{silver_db}.fx_daily"
    target = f"{args.catalog_name}.{silver_db}.bookings_eur"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))

    latest = latest_per_booking(spark.table(source), args.run_date)
    converted = convert_to_eur(latest, spark.table(fx_table)).cache()
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_eur(session, target, converted)

    try:
        run_wap(spark, target, args.run_date, write, args.checks_dir / "bookings_eur.yaml")
    finally:
        converted.unpersist()
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver bookings_eur %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    require_rules_file(args.checks_dir / "bookings_eur.yaml")
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
