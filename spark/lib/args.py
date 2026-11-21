"""Argumentos comunes de los jobs: iguales en local y en Glue (Ruling "Dónde corre Spark")."""

import argparse
from datetime import date, timedelta

DEFAULT_REGION = "eu-west-3"
DEFAULT_PACKAGES = ",".join(
    [
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.1",
        "org.apache.iceberg:iceberg-aws-bundle:1.7.1",
        "org.apache.hadoop:hadoop-aws:3.3.4",
    ]
)


def run_date_type(value: str) -> str:
    """Valida YYYY-MM-DD y devuelve el mismo texto; la fecha lógica nunca sale del reloj."""
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--run-date debe ser YYYY-MM-DD: {value!r}") from exc
    if len(value) != 10:
        raise argparse.ArgumentTypeError(f"--run-date debe ser YYYY-MM-DD: {value!r}")
    return value


def date_range(date_from: str, date_to: str) -> list[str]:
    """Fechas logicas YYYY-MM-DD de date_from a date_to, ambas incluidas."""
    start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    return [(start + timedelta(days=n)).isoformat() for n in range((end - start).days + 1)]


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--run-date", type=run_date_type, help="YYYY-MM-DD (un dia)")
    parser.add_argument("--from", dest="date_from", type=run_date_type, help="YYYY-MM-DD inclusive")
    parser.add_argument("--to", dest="date_to", type=run_date_type, help="YYYY-MM-DD inclusive")
    parser.add_argument("--env", choices=("dev", "prod"), default="dev")
    parser.add_argument("--catalog-name", default="skyroute")
    parser.add_argument("--catalog-impl", choices=("glue", "hadoop"), default="glue")
    parser.add_argument(
        "--warehouse",
        required=True,
        help="s3://bucket/<capa> con catalogo glue; ruta local con hadoop",
    )
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument(
        "--jars-packages",
        default=DEFAULT_PACKAGES,
        help="spark.jars.packages; 'none' lo desactiva (Glue ya trae los jars)",
    )
    return parser


def parse_args(argv=None, description: str = "", extra=None) -> argparse.Namespace:
    """`extra(parser)` añade los argumentos propios del job."""
    parser = argparse.ArgumentParser(description=description)
    add_common_args(parser)
    if extra is not None:
        extra(parser)
    args = parser.parse_args(argv)
    if args.run_date and (args.date_from or args.date_to):
        parser.error("usa --run-date o --from/--to, no ambos")
    if args.run_date:
        args.dates = [args.run_date]
    elif args.date_from and args.date_to:
        if args.date_to < args.date_from:
            parser.error("--to debe ser >= --from")
        args.dates = date_range(args.date_from, args.date_to)
    else:
        parser.error("falta --run-date o --from y --to")
    if args.catalog_impl == "glue" and not args.warehouse.startswith("s3://"):
        parser.error(f"con catalogo glue --warehouse debe empezar por s3://: {args.warehouse!r}")
    return args
