"""Argumentos comunes de los jobs: iguales en local y en Glue (Ruling "Dónde corre Spark")."""

import argparse
import logging
import re
import sys
from datetime import date, timedelta

LOG = logging.getLogger("lib.args")
GLUE_MARKER = "--JOB_NAME"  # Glue siempre lo añade; solo entonces se toleran argumentos ajenos
DEFAULT_REGION = "eu-west-3"
DEFAULT_PACKAGES = ",".join(
    [
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.1",
        "org.apache.iceberg:iceberg-aws-bundle:1.7.1",
        "org.apache.hadoop:hadoop-aws:3.3.4",
    ]
)


# Argumentos que Glue pasa al script y que los jobs no usan. Fuente: "Using job parameters in
# AWS Glue jobs" (docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-arguments.html,
# comprobada el 2026-11-21) y "Logging behavior changes in AWS Glue 5.0"
# (.../migrating-version-50.html). --JOB_ID y --JOB_RUN_ID los anade Glue al lanzar el run
# (no figuran en esa pagina). Cualquier otro "--nombre" ignorado es un error, p. ej. un typo
# como --session-gap-minute que correria con el valor por defecto.
GLUE_RESERVED = frozenset(
    {
        "--JOB_NAME",
        "--JOB_ID",
        "--JOB_RUN_ID",
        "--TempDir",
        "--scriptLocation",
        "--job-bookmark-option",
        "--job-bookmark-from",
        "--job-bookmark-to",
        "--job-language",
        "--class",
        "--conf",
        "--datalake-formats",
        "--extra-files",
        "--extra-jars",
        "--extra-py-files",
        "--additional-python-modules",
        "--python-modules-installer-option",
        "--python-virtual-env",
        "--user-jars-first",
        "--executor-cores",
        "--disable-proxy-v2",
        "--spark-event-logs-path",
        "--system-logs-kms-key-arn",
        "--customer-driver-env-vars",
        "--customer-executor-env-vars",
        "--encryption-type",
        "--debug",
        "--mode",
        "--endpoint",
        "--execution_class",
        "--redshiftTmpDir",
        "--python-virtual-env-storage-prefix",
        "--python-virtual-env-version",
        "--use-postgres-driver",
        "--auto-scale-within-microbatch",
        "--internal-lib-urls",
        "--glue-di-packages-correlation-ids",
        "--tenant-internal",
    }
)
# Familias de Glue (documentadas o inyectadas por el servicio segun version del runtime).
GLUE_RESERVED_PREFIXES = (
    "--enable-",
    "--continuous-log-",
    "--custom-log",
    "--spark-",
    "--job-",
    "--extra-",
    "--additional-",
    "--python-",
    "--system-",
    "--customer-",
    "--disable-",
    "--internal-",
    "--glue-",
    "--tenant-",
    "--conf",
)
# Parametros internos en MAYUSCULAS (--JOB_ID, --JOB_RUN_ID, --SECURITY_CONFIGURATION, ...).
GLUE_UPPERCASE = re.compile(r"--[A-Z][A-Z0-9_]*")


def _unexpected_glue_args(ignored: list[str]) -> list[str]:
    """Opciones `--x` ignoradas que Glue no reserva (los valores sueltos no se comprueban)."""
    return [
        token
        for token in ignored
        if token.startswith("--")
        and token.split("=", 1)[0] not in GLUE_RESERVED
        and not token.startswith(GLUE_RESERVED_PREFIXES)
        and not GLUE_UPPERCASE.fullmatch(token.split("=", 1)[0])
    ]


def _option_names(tokens: list[str]) -> list[str]:
    """Solo los nombres `--x` (sin `=valor`); los valores sueltos nunca se imprimen."""
    return [token.split("=", 1)[0] for token in tokens if token.startswith("--")]


def _report_rejected(unexpected: list[str], ignored: list[str]) -> None:
    """Deja los nombres rechazados en stdout, stderr y logging: CloudWatch no muestra el
    mensaje de parser.error (solo el traceback). Nunca imprime valores."""
    message = (
        f"argumentos desconocidos que Glue no reserva: {_option_names(unexpected)}; "
        f"nombres ignorados en total: {_option_names(ignored)}"
    )
    print(message, flush=True)
    print(message, file=sys.stderr, flush=True)
    LOG.error(message)


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
    # allow_abbrev=False: un prefijo (--session-gap) no puede asignar otra opcion en silencio.
    parser = argparse.ArgumentParser(description=description, allow_abbrev=False)
    add_common_args(parser)
    if extra is not None:
        extra(parser)
    argv = sys.argv[1:] if argv is None else list(argv)
    if GLUE_MARKER in argv:
        # Glue pasa sus propios argumentos (--TempDir, --extra-py-files, ...) al script.
        args, ignored = parser.parse_known_args(argv)
        unexpected = _unexpected_glue_args(ignored)
        if unexpected:
            _report_rejected(unexpected, ignored)
            names = _option_names(unexpected)
            parser.error(f"argumentos desconocidos que Glue no reserva: {names}")
        LOG.info("argumentos de Glue ignorados: %s", ignored)
    else:
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
