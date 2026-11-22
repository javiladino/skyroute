"""Mantenimiento: compacta los archivos de datos de una tabla Iceberg (binpack).

No cambia el contenido: solo agrupa archivos pequenos en `main`. `--run-date` es obligatorio
por la interfaz comun de los jobs y solo se registra; la compactacion no lee el reloj para
decidir nada. Con `--min-input-files` mas bajo se compactan grupos de menos archivos.

    python -m jobs.maintenance.rewrite_data_files --run-date 2026-01-01 --table events \
        --warehouse s3://<bucket>/silver
"""

import copy
import logging
import sys

from lib.args import parse_args
from lib.entrypoint import exit_on_error
from lib.session import build_spark
from pyspark.sql import SparkSession

LOG = logging.getLogger("maintenance.rewrite_data_files")


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ValueError("debe ser >= 1")
    return number


def _extra_args(parser):
    parser.add_argument("--table", required=True, help="nombre de la tabla, sin base ni catalogo")
    parser.add_argument("--database", help="por defecto skyroute_<env>_silver")
    parser.add_argument(
        "--min-input-files",
        type=_positive,
        default=5,
        help="minimo de archivos de un grupo para compactarlo (defecto de Iceberg)",
    )


def run(spark: SparkSession, args) -> dict:
    database = args.database or f"skyroute_{args.env}_silver"
    identifier = f"{database}.{args.table}"
    row = spark.sql(
        f"CALL {args.catalog_name}.system.rewrite_data_files("
        f"table => '{identifier}', "
        f"options => map('min-input-files', '{args.min_input_files}'))"
    ).first()
    summary = {
        "run_date": args.run_date,
        "table": f"{args.catalog_name}.{identifier}",
        "rewritten_data_files": row["rewritten_data_files_count"],
        "added_data_files": row["added_data_files_count"],
    }
    LOG.info("rewrite_data_files %s", summary)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args(argv, description=__doc__.splitlines()[0], extra=_extra_args)
    if args.date_from or args.date_to:
        # Compactar N veces la misma tabla no aporta nada: un run, una compactacion.
        sys.exit("rewrite_data_files solo admite --run-date, no --from/--to")
    spark = build_spark(args)
    for day in args.dates:
        day_args = copy.copy(args)
        day_args.run_date = day
        run(spark, day_args)
    return 0


if __name__ == "__main__":
    exit_on_error(main())
