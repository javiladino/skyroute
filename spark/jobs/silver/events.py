"""Silver events: eventos de clickstream tipados, deduplicados y con el email como HMAC.

Lee la particion `_ingest_date = D` de skyroute_<env>_bronze.clickstream (sin corte `<= D`:
relanzar D en cualquier momento da el mismo resultado). Tabla particionada por `days(event_ts)`:
un evento tardio de D que llega en la ingesta D+2 cae en la particion de D.

- Duplicados exactos (el generador los deja dentro de un archivo) se reducen a una fila. Si un
  `event_id` llega con contenido distinto en el mismo lote, el check `events_conflicting_ids`
  impide publicar en vez de elegir uno.
- MERGE `WHEN NOT MATCHED THEN INSERT` por `event_id` (Technical Design §1): un evento ya
  publicado no se modifica ni se duplica al relanzar. El conjunto final de filas no depende del
  orden de las ejecuciones.
- Antes de insertar, el lote se compara con lo ya publicado: si un `event_id` existente llega
  con contenido distinto, falla `events_conflicting_published` y no se publica nada.
- `email` desaparece: `email_hmac` = HMAC-SHA256 hexadecimal de `lower(trim(email))`, con la
  clave de la variable de entorno SKYROUTE_HMAC_KEY (local y tests) o, si no esta definida, del
  parametro SSM `/skyroute/<env>/hmac-email-key` (Glue). `consent_ts` se conserva. La clave
  nunca se pasa por argumentos de linea de comandos.
- La rama SSM necesita boto3, preinstalado en Glue; no esta en requirements (local y tests usan
  la variable de entorno).

Checks: spark/checks/events.yaml.

    SKYROUTE_HMAC_KEY=... python -m jobs.silver.events --run-date 2026-01-01 \
        --warehouse s3://<bucket>/silver
"""

import copy
import hashlib
import hmac
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from jobs.silver.bookings_scd2 import DEFAULT_CHECKS_DIR, TS_FORMAT, amount_decimal
from lib.args import parse_args
from lib.checks import Failure, require_rules_file
from lib.session import build_spark
from lib.wap import WapCheckError, branch_name, run_wap
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

LOG = logging.getLogger("silver.events")
HMAC_KEY_ENV = "SKYROUTE_HMAC_KEY"

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    event_id string,
    event_type string,
    event_ts timestamp,
    customer_id string,
    session_id string,
    campaign_id string,
    currency string,
    amount decimal(12,2),
    consent_ts timestamp,
    email_hmac string,
    booking_id string
) USING iceberg
PARTITIONED BY (days(event_ts))
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
    parser.add_argument(
        "--hmac-ssm-parameter",
        help=f"parametro SSM de la clave si {HMAC_KEY_ENV} no esta; por defecto "
        "/skyroute/<env>/hmac-email-key",
    )


def resolve_hmac_key(parameter_name: str, region: str, environ=None, ssm_client=None) -> bytes:
    """Clave HMAC: variable de entorno si existe; si no, SSM (boto3 solo se importa entonces)."""
    environ = os.environ if environ is None else environ
    value = environ.get(HMAC_KEY_ENV)
    if not value:
        if ssm_client is None:
            import boto3  # solo en Glue; en local y en tests basta la variable

            ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        value = response["Parameter"]["Value"]
    if not value:
        raise ValueError("la clave HMAC esta vacia")
    return value.encode("utf-8")


def hmac_column(key: bytes, column: str):
    """HMAC-SHA256 hexadecimal de `lower(trim(column))`; nulo si falta o queda vacio."""

    return F.udf(make_hmac_fn(key), StringType())(F.col(column))


def make_hmac_fn(key: bytes):
    """Funcion email -> HMAC hexadecimal de `lower(trim(email))`; nulo si falta o queda vacio.

    Es una clausura (Spark la serializa por valor: los workers no importan este modulo). Si
    falla, el error no incluye el email ni encadena la excepcion original: las trazas de Spark
    y los logs de Glue no deben contener datos personales.
    """

    def _hmac(email):
        try:
            normalized = email.strip().lower() if email else ""
            if not normalized:
                return None
            return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()
        except Exception:
            raise ValueError("no se pudo calcular el HMAC de un email (valor omitido)") from None

    return _hmac


def typed_events(bronze, run_date: str, key: bytes):
    """Eventos de la particion de D con tipos de Silver y el email sustituido por su HMAC."""
    day = F.to_date(F.lit(run_date))
    typed = bronze.where(F.col("_ingest_date") == day).select(
        "event_id",
        "event_type",
        F.to_timestamp("event_ts", TS_FORMAT).alias("event_ts"),
        "customer_id",
        "session_id",
        "campaign_id",
        "currency",
        amount_decimal().alias("amount"),
        F.to_timestamp("consent_ts", TS_FORMAT).alias("consent_ts"),
        hmac_column(key, "email").alias("email_hmac"),
        "booking_id",
    )
    return typed.distinct()


def published_conflicts(spark: SparkSession, target: str, events, run_date: str) -> int:
    """event_id del lote que ya estan en el destino con alguna columna distinta.

    No compara `email_hmac`: rotar la clave HMAC (Ruling value_wo_version) deja los hashes viejos
    hasta reconstruir events, y relanzar un dia solo escribe filas nuevas (el MERGE solo
    inserta), asi que una clave nueva no debe hacer fallar el relanzamiento.

    El destino se poda por `event_ts` en [D-3 00:00, D+1 00:00) para leer solo esas particiones:
    un tardio llega como mucho 72 h despues. Un evento del lote fuera de ese rango no se
    compararia (el MERGE seguiria sin duplicarlo).
    """
    day = date.fromisoformat(run_date)
    # Literales como texto: Spark los interpreta en spark.sql.session.timeZone (UTC).
    lower = F.to_timestamp(F.lit(f"{day - timedelta(days=3)} 00:00:00"))
    upper = F.to_timestamp(F.lit(f"{day + timedelta(days=1)} 00:00:00"))
    published = (
        spark.table(target)
        .where((F.col("event_ts") >= lower) & (F.col("event_ts") < upper))
        .alias("t")
    )
    batch = events.alias("s")
    others = [c for c in events.columns if c not in ("event_id", "email_hmac")]
    differs = None
    for column in others:
        diff = ~F.col(f"s.{column}").eqNullSafe(F.col(f"t.{column}"))
        differs = diff if differs is None else (differs | diff)
    return batch.join(published, F.col("s.event_id") == F.col("t.event_id")).where(differs).count()


def write_events(spark: SparkSession, target: str, events, run_date: str) -> int:
    rows = events.count()
    if rows:
        conflicts = events.groupBy("event_id").count().where(F.col("count") > 1).count()
        if conflicts:
            message = f"{conflicts} event_id de {run_date} con contenido distinto en Bronze"
            raise WapCheckError(
                branch_name(run_date), [Failure("events_conflicting_ids", message, conflicts)]
            )
        changed = published_conflicts(spark, target, events, run_date)
        if changed:
            message = f"{changed} event_id de {run_date} ya publicados con contenido distinto"
            raise WapCheckError(
                branch_name(run_date), [Failure("events_conflicting_published", message, changed)]
            )
        events.createOrReplaceTempView("_events_batch")
        spark.sql(
            f"""
            MERGE INTO {target} t USING _events_batch s
            ON t.event_id = s.event_id
            WHEN NOT MATCHED THEN INSERT *
            """
        )
    return rows


def run(spark: SparkSession, args, key: bytes) -> dict:
    tz = spark.conf.get("spark.sql.session.timeZone")
    assert tz == "UTC", f"spark.sql.session.timeZone debe ser UTC, es {tz!r}"
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    source = f"{args.catalog_name}.{bronze_db}.clickstream"
    target = f"{args.catalog_name}.{silver_db}.events"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))

    events = typed_events(spark.table(source), args.run_date, key).cache()
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_events(session, target, events, args.run_date)

    try:
        run_wap(spark, target, args.run_date, write, args.checks_dir / "events.yaml")
    finally:
        events.unpersist()
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver events %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    require_rules_file(args.checks_dir / "events.yaml")
    parameter = args.hmac_ssm_parameter or f"/skyroute/{args.env}/hmac-email-key"
    key = resolve_hmac_key(parameter, args.region)
    spark = build_spark(args)
    last_ok = None
    for day in args.dates:
        day_args = copy.copy(args)
        day_args.run_date = day
        try:
            run(spark, day_args, key)
        except Exception:
            resume = f"--from {day}" + (f" --to {args.date_to}" if args.date_to else "")
            LOG.error("fallo en %s; ultima fecha OK: %s; reanuda con %s", day, last_ok, resume)
            raise
        last_ok = day
    return 0


if __name__ == "__main__":
    sys.exit(main())
