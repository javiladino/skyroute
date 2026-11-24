"""Ingesta Bronze generica: landing/<source>/ingest_date=D/ a skyroute_<env>_bronze.<source>.

Payload integro (esquema explicito por fuente, FAILFAST) mas _ingested_at, _batch_id,
_source_file, _ingest_date, todos derivados de la fecha logica y del archivo (nunca del
reloj). Escribe con overwritePartitions por _ingest_date (reemplazo de particion) y falla
si no hay archivos de entrada para D. Con --from/--to (inclusivos) itera los dias en una
sola sesion, un commit atomico por dia; si uno falla se detiene e indica como reanudar.
El landing va con s3a:// (Hadoop) y el warehouse de Glue con s3:// (Iceberg).

    python -m jobs.bronze.ingest --source clickstream --run-date 2026-01-01 \
        --landing-root s3a://<bucket> --warehouse s3://<bucket>/bronze
    python -m jobs.bronze.ingest --source fx --from 2026-01-01 --to 2026-06-30 \
        --landing-root s3a://<bucket> --warehouse s3://<bucket>/bronze
"""

import copy
import logging

from lib.args import parse_args
from lib.entrypoint import exit_on_error
from lib.schemas import SCHEMAS
from lib.session import build_spark
from lib.technical_columns import add_technical_columns
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

SOURCES = ("clickstream", "bookings", "fx", "ad_spend")
LOG = logging.getLogger("bronze.ingest")


class NoInputFiles(RuntimeError):
    """No hay archivos de landing para la fecha logica; la particion previa no se toca."""


def _extra_args(parser):
    parser.add_argument("--source", required=True, choices=SOURCES)
    parser.add_argument(
        "--landing-root",
        required=True,
        help="raiz que contiene landing/: s3a://bucket (o s3://bucket en Glue) o ruta local",
    )
    parser.add_argument("--database", help="por defecto skyroute_<env>_bronze")


def input_prefix(landing_root: str, source: str, run_date: str) -> str:
    return f"{landing_root.rstrip('/')}/landing/{source}/ingest_date={run_date}"


def list_input_files(spark: SparkSession, prefix: str) -> list[str]:
    path = spark._jvm.org.apache.hadoop.fs.Path(prefix)
    fs = path.getFileSystem(spark._jsc.hadoopConfiguration())
    if not fs.exists(path):
        return []
    files = []
    it = fs.listFiles(path, True)
    while it.hasNext():
        name = it.next().getPath().toString()
        if name.endswith((".json.gz", ".json")):
            files.append(name)
    return sorted(files)


def align_to_table(df: DataFrame, table_schema) -> DataFrame:
    """Proyecta df al esquema de la tabla: columnas ausentes en el dia quedan nulas."""
    names = [field.name for field in table_schema.fields]
    extra = [c for c in df.columns if c not in names]
    if extra:
        raise ValueError(f"columnas nuevas en landing, Bronze no evoluciona solo: {extra}")
    cols = [
        F.col(f.name) if f.name in df.columns else F.lit(None).cast(f.dataType).alias(f.name)
        for f in table_schema.fields
    ]
    return df.select(*cols)


def run(spark: SparkSession, args) -> dict:
    database = args.database or f"skyroute_{args.env}_bronze"
    table = f"{args.catalog_name}.{database}.{args.source}"
    prefix = input_prefix(args.landing_root, args.source, args.run_date)
    files = list_input_files(spark, prefix)
    if not files:
        raise NoInputFiles(f"sin archivos de entrada en {prefix}")

    # Esquema explicito + FAILFAST: una linea corrupta o de tipo incompatible falla la
    # ejecucion en vez de colarse como _corrupt_record; sin inferencia, los dias no se
    # contradicen entre si.
    raw = spark.read.json(files, schema=SCHEMAS[args.source], mode="FAILFAST")
    df = add_technical_columns(raw, args.run_date)
    rows = df.count()

    if args.catalog_impl == "hadoop":
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {args.catalog_name}.{database}")

    if not spark.catalog.tableExists(table):
        if rows == 0:
            raise NoInputFiles(f"archivos vacios en {prefix} y la tabla {table} no existe")
        (
            df.writeTo(table)
            .using("iceberg")
            .partitionedBy(F.col("_ingest_date"))
            .tableProperty("format-version", "2")
            .create()
        )
    elif rows == 0:
        # Dia sin filas (archivo valido y vacio): la particion queda vacia, no con datos viejos.
        spark.sql(f"DELETE FROM {table} WHERE _ingest_date = DATE '{args.run_date}'")
    else:
        aligned = align_to_table(df, spark.table(table).schema)
        aligned.writeTo(table).overwritePartitions()

    written = (
        spark.table(table).where(F.col("_ingest_date") == F.to_date(F.lit(args.run_date))).count()
    )
    summary = {
        "run_date": args.run_date,
        "source": args.source,
        "files": len(files),
        "rows_read": rows,
        "rows_written": written,
        "table": table,
    }
    LOG.info("bronze ingest %s", summary)
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
            done = last_ok or "ninguna"
            LOG.error("fallo en %s; ultima fecha OK: %s; reanuda con %s", day, done, resume)
            raise
        last_ok = day
    return 0


if __name__ == "__main__":
    exit_on_error(main())
