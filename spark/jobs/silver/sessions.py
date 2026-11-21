"""Silver sessions: sesionizacion por inactividad sobre silver.events (plan, Design Decision 5).

Una sesion es la secuencia de eventos de un `customer_id`, ordenados por (event_ts, event_id),
con huecos de como maximo `--session-gap-minutes` (30 por defecto); un hueco estrictamente mayor
abre otra sesion. Tope de duracion: el evento cuyo `event_ts` dista >= 24 h del `session_start`
(primer evento) de su sesion abre una sesion nueva; el corte es a 24 h exactas desde
`session_start`, asi que una sesion dura como mucho 23:59:59 y la siguiente empieza en ese
evento. `session_key` = sha256(customer_id | event_id del primer evento).

El dia D lee silver.events con `event_ts` en [D-5 00:00 - gap, D+2 00:00), sin corte por
`_ingest_date`: por abajo, contexto para decidir donde empiezan las sesiones de D-4 (un tardio
llega como mucho 72 h despues, y una sesion que lo recibe empezo como mucho 24 h antes); por
arriba, una sesion que empieza en D acaba antes de D+2 00:00 gracias al tope de 24 h. Reemplaza
las sesiones cuyo primer evento cae en [D-4, D] con un unico MERGE por `session_key`:
WHEN MATCHED UPDATE, WHEN NOT MATCHED INSERT y
WHEN NOT MATCHED BY SOURCE AND session_start_date BETWEEN D-4 AND D THEN DELETE (no deja
sesiones huerfanas si un tardio cambia el primer evento y, con ello, la clave). Las sesiones
que empiezan antes de D-4 solo son contexto: ni se reescriben ni se borran.

Una sesion pertenece al dia de su primer evento. Requiere que events se haya ejecutado antes
para D: si la particion Bronze clickstream `_ingest_date = D` tiene algun event_id que no esta
en silver.events, el job falla (`events_missing_for_ingest_day`); si la particion esta vacia o
no existe, no bloquea.

`session_key` no es estable hasta D+4: hasta que pasa la ventana de tardios un evento puede
adelantar el primer evento de una sesion y cambiar su clave. Gold debe recalcular esa ventana
entera (D-4..D) en cada ejecucion en vez de tratar las claves como definitivas.

Limite conocido: si una cadena de eventos sin huecos > gap dura mas de ~24 h, el punto de corte
del tope depende del primer evento leido de la cadena. Si ese cae en [lower, lower + gap) y la
cadena llega a sesiones desde D-4, el job falla con `sessions_chain_touches_context` en vez de
dar sesiones distintas en silencio. Checks: spark/checks/sessions.yaml.

    python -m jobs.silver.sessions --run-date 2026-01-01 --warehouse s3://<bucket>/silver
"""

import copy
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from jobs.silver.bookings_scd2 import DEFAULT_CHECKS_DIR
from lib.args import parse_args
from lib.checks import Failure
from lib.session import build_spark
from lib.wap import WapCheckError, branch_name, run_wap
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

LOG = logging.getLogger("silver.sessions")
DEFAULT_GAP_MINUTES = 30
MAX_SESSION_SECONDS = 24 * 3600  # tope de duracion: un evento a >= 24 h del inicio abre sesion
# Un evento tardio llega como mucho 72 h despues (generators/ota/clickstream.py) y la sesion que
# lo recibe empezo como mucho 24 h antes: se reescriben las sesiones que empiezan en [D-4, D].
REWRITE_DAYS = 4
CONTEXT_DAYS = 5  # lectura desde D-5 00:00 - gap: contexto para las sesiones de D-4
LOOKAHEAD_DAYS = 2  # D+2 00:00: con el tope de 24 h, las sesiones de D acaban antes

DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    session_key string,
    customer_id string,
    session_start timestamp,
    session_end timestamp,
    session_start_date date,
    n_events int,
    converted boolean,
    booking_id string
) USING iceberg
TBLPROPERTIES (
    'format-version' = '2',
    'write.wap.enabled' = 'true',
    'write.merge.mode' = 'copy-on-write',
    'write.update.mode' = 'copy-on-write',
    'write.delete.mode' = 'copy-on-write'
)
"""


def _gap_minutes(value: str) -> int:
    minutes = int(value)
    if minutes <= 0:
        raise ValueError("--session-gap-minutes debe ser > 0")
    return minutes


def _extra_args(parser):
    parser.add_argument("--bronze-database", help="por defecto skyroute_<env>_bronze")
    parser.add_argument("--silver-database", help="por defecto skyroute_<env>_silver")
    parser.add_argument("--checks-dir", type=Path, default=DEFAULT_CHECKS_DIR)
    parser.add_argument("--session-gap-minutes", type=_gap_minutes, default=DEFAULT_GAP_MINUTES)


def window_bounds(run_date: str, gap_minutes: int) -> tuple[datetime, datetime, date, date]:
    """(lectura desde, lectura hasta, primer dia reescrito, ultimo dia reescrito), todo UTC."""
    day = date.fromisoformat(run_date)
    first = day - timedelta(days=REWRITE_DAYS)
    context = day - timedelta(days=CONTEXT_DAYS)
    start = datetime(context.year, context.month, context.day) - timedelta(minutes=gap_minutes)
    end_day = day + timedelta(days=LOOKAHEAD_DAYS)
    return start, datetime(end_day.year, end_day.month, end_day.day), first, day


_PAIRS = ArrayType(
    StructType(
        [StructField("event_id", StringType()), StructField("first_event_id", StringType())]
    )
)


@F.udf(_PAIRS)
def _cap_first_ids(items):
    """items: (_ts en segundos, event_id) ordenados; devuelve (event_id, primer evento de sesion).

    Dentro de un tramo sin huecos > gap, un evento a >= 24 h del primer evento de la sesion
    en curso abre sesion nueva.
    """
    pairs = []
    start_ts = start_id = None
    for item in items:
        if start_ts is None or item["_ts"] - start_ts >= MAX_SESSION_SECONDS:
            start_ts, start_id = item["_ts"], item["event_id"]
        pairs.append((item["event_id"], start_id))
    return pairs


def assign_sessions(events, gap_minutes: int, keep_chain: bool = False):
    """Anade `session_key` a cada evento (de event_id, event_ts y customer_id, todos no nulos).

    Un hueco > gap abre sesion; dentro de cada tramo sin huecos, el tope de 24 h parte la
    cadena desde su primer evento (`_cap_first_ids`). `event_id` es unico en `events`.
    Con `keep_chain` conserva `_ordinal` (numero de cadena por cliente).
    """
    ordered = Window.partitionBy("customer_id").orderBy("event_ts", "event_id")
    previous = F.lag("event_ts").over(ordered)
    elapsed = F.col("event_ts").cast("long") - previous.cast("long")
    opens = F.when(previous.isNull() | (elapsed > gap_minutes * 60), 1).otherwise(0)
    numbered = events.withColumn("_opens", opens).withColumn(
        "_ordinal", F.sum("_opens").over(ordered.rowsBetween(Window.unboundedPreceding, 0))
    )
    item = F.struct(F.col("event_ts").cast("long").alias("_ts"), F.col("event_id"))
    chains = numbered.groupBy("customer_id", "_ordinal").agg(
        F.sort_array(F.collect_list(item)).alias("_items")
    )
    firsts = chains.select(
        "customer_id", F.explode(_cap_first_ids("_items")).alias("_pair")
    ).select("customer_id", "_pair.event_id", "_pair.first_event_id")
    keyed = numbered.join(firsts, ["customer_id", "event_id"]).withColumn(
        "session_key", F.sha2(F.concat_ws("|", F.col("customer_id"), F.col("first_event_id")), 256)
    )
    return keyed.drop("_opens", "first_event_id", *([] if keep_chain else ["_ordinal"]))


def aggregate_sessions(labeled):
    """Una fila por sesion a partir de eventos con `session_key`."""
    is_purchase = F.col("event_type") == "purchase"
    purchase = F.when(
        is_purchase & F.col("booking_id").isNotNull(),
        F.struct("event_ts", "event_id", "booking_id"),
    )
    grouped = labeled.groupBy("session_key", "customer_id").agg(
        F.min("event_ts").alias("session_start"),
        F.max("event_ts").alias("session_end"),
        F.count(F.lit(1)).cast("int").alias("n_events"),
        F.max(F.when(is_purchase, 1).otherwise(0)).alias("_purchases"),
        F.array_min(F.collect_list(purchase)).getField("booking_id").alias("booking_id"),
    )
    return grouped.select(
        "session_key",
        "customer_id",
        "session_start",
        "session_end",
        F.to_date("session_start").alias("session_start_date"),
        "n_events",
        (F.col("_purchases") == 1).alias("converted"),
        "booking_id",
    )


def _ts_literal(value: datetime):
    # Literales como texto: Spark los interpreta en spark.sql.session.timeZone (UTC), no en la
    # zona local del proceso Python.
    return F.to_timestamp(F.lit(value.strftime("%Y-%m-%d %H:%M:%S")))


def window_events(events, run_date: str, gap_minutes: int):
    """Eventos de la ventana de lectura de D, con las columnas que usa la sesionizacion."""
    start, end, _, _ = window_bounds(run_date, gap_minutes)
    window = events.where(
        (F.col("event_ts") >= _ts_literal(start)) & (F.col("event_ts") < _ts_literal(end))
    )
    return window.select("event_id", "event_type", "event_ts", "customer_id", "booking_id")


def sessions_for_window(events, run_date: str, gap_minutes: int):
    """Sesiones con primer evento en [D-4, D], calculadas con la ventana de lectura de D."""
    _, _, first_day, last_day = window_bounds(run_date, gap_minutes)
    window = window_events(events, run_date, gap_minutes)
    sessions = aggregate_sessions(assign_sessions(window, gap_minutes))
    return sessions.where(
        F.col("session_start_date").between(F.lit(first_day), F.lit(last_day))
    )


def require_anchor_free_window(events, run_date: str, gap_minutes: int) -> None:
    """Falla si una cadena que toca el borde inferior de la lectura llega a sesiones de [D-4, D].

    Una cadena sin huecos > gap cuyo primer evento leido cae en [lower, lower + gap) puede tener
    eventos anteriores sin leer; si ademas alcanza una sesion que empieza en >= D-4, el punto de
    corte de 24 h depende de un evento que esta ventana no ve. Se detecta en vez de dar sesiones
    distintas segun la ejecucion.
    """
    start, _, first_day, _ = window_bounds(run_date, gap_minutes)
    labeled = assign_sessions(window_events(events, run_date, gap_minutes), gap_minutes, True)
    starts = labeled.groupBy("customer_id", "_ordinal", "session_key").agg(
        F.min("event_ts").alias("_start")
    )
    chains = starts.groupBy("customer_id", "_ordinal").agg(
        F.min("_start").alias("_first"), F.max(F.to_date("_start")).alias("_last_day")
    )
    touching = chains.where(
        (F.col("_first") < _ts_literal(start + timedelta(minutes=gap_minutes)))
        & (F.col("_last_day") >= F.lit(first_day))
    ).count()
    if touching:
        message = (
            f"{touching} cadena(s) de eventos sin huecos > gap empiezan en el borde de la lectura "
            f"de {run_date} y llegan a sesiones desde {first_day}; el corte de 24 h no es fiable"
        )
        raise WapCheckError(
            branch_name(run_date), [Failure("sessions_chain_touches_context", message, touching)]
        )


def write_sessions(spark: SparkSession, target: str, sessions, run_date: str) -> int:
    rows = sessions.count()
    first_day = date.fromisoformat(run_date) - timedelta(days=REWRITE_DAYS)
    sessions.createOrReplaceTempView("_sessions_batch")
    spark.sql(
        f"""
        MERGE INTO {target} t USING _sessions_batch s
        ON t.session_key = s.session_key
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        WHEN NOT MATCHED BY SOURCE
            AND t.session_start_date BETWEEN DATE '{first_day.isoformat()}'
                AND DATE '{run_date}' THEN DELETE
        """
    )
    return rows


def require_events_of_ingest_day(
    spark: SparkSession, bronze: str, source: str, run_date: str
) -> None:
    """Falla antes de escribir si un event_id de la particion Bronze `_ingest_date = D` falta.

    Si la particion esta vacia o no existe no bloquea: las sesiones se calculan con lo que haya.
    """
    if not spark.catalog.tableExists(bronze):
        return
    day = F.to_date(F.lit(run_date))
    ids = spark.table(bronze).where(F.col("_ingest_date") == day).select("event_id").distinct()
    if ids.isEmpty():
        return
    if not spark.catalog.tableExists(source):
        missing = ids.count()
    else:
        missing = ids.join(spark.table(source).select("event_id"), "event_id", "left_anti").count()
    if missing:
        message = f"{missing} event_id de Bronze {run_date} faltan en silver.events; ejecuta events"
        raise WapCheckError(
            branch_name(run_date), [Failure("events_missing_for_ingest_day", message, missing)]
        )


def run(spark: SparkSession, args) -> dict:
    tz = spark.conf.get("spark.sql.session.timeZone")
    assert tz == "UTC", f"spark.sql.session.timeZone debe ser UTC, es {tz!r}"
    silver_db = args.silver_database or f"skyroute_{args.env}_silver"
    bronze_db = args.bronze_database or f"skyroute_{args.env}_bronze"
    bronze = f"{args.catalog_name}.{bronze_db}.clickstream"
    source = f"{args.catalog_name}.{silver_db}.events"
    target = f"{args.catalog_name}.{silver_db}.sessions"
    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{silver_db}")
    spark.sql(DDL.format(table=target))

    require_events_of_ingest_day(spark, bronze, source, args.run_date)
    if not spark.catalog.tableExists(source):
        message = "silver.events no existe; ejecuta events antes"
        raise WapCheckError(
            branch_name(args.run_date), [Failure("events_missing_for_ingest_day", message, 0)]
        )
    require_anchor_free_window(spark.table(source), args.run_date, args.session_gap_minutes)
    sessions = sessions_for_window(
        spark.table(source), args.run_date, args.session_gap_minutes
    ).cache()
    result = {}

    def write(session: SparkSession) -> None:
        result["rows"] = write_sessions(session, target, sessions, args.run_date)

    try:
        run_wap(spark, target, args.run_date, write, args.checks_dir / "sessions.yaml")
    finally:
        sessions.unpersist()
    summary = {"run_date": args.run_date, "rows_in_batch": result["rows"], "table": target}
    LOG.info("silver sessions %s", summary)
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
