"""Imprime count(*) y sum(<columna>) de una tabla Iceberg de un catalogo hadoop local.

Solo lectura y sin AWS: sirve para comparar el resultado local de un job Silver con Athena.

    python spark/tools/count_table.py --warehouse /tmp/wh \
        --table skyroute.skyroute_dev_silver.bookings_eur --sum-column amount_eur
"""

import argparse
import re
import sys

from pyspark.sql import SparkSession

ICEBERG_EXTENSIONS = "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
DEFAULT_PACKAGES = "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.1"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", required=True, help="ruta local del catalogo hadoop")
    parser.add_argument("--table", required=True, help="<catalogo>.<base>.<tabla>")
    parser.add_argument("--sum-column", required=True)
    parser.add_argument("--catalog-name", default="skyroute")
    parser.add_argument("--jars-packages", default=DEFAULT_PACKAGES, help="'none' lo desactiva")
    args = parser.parse_args(argv)
    for value in (args.table, args.sum_column, args.catalog_name):
        if not IDENT.match(value):
            parser.error(f"identificador no valido: {value!r}")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    prefix = f"spark.sql.catalog.{args.catalog_name}"
    builder = (
        SparkSession.builder.appName("skyroute-count-table")
        .config("spark.sql.extensions", ICEBERG_EXTENSIONS)
        .config("spark.sql.session.timeZone", "UTC")
        .config(prefix, "org.apache.iceberg.spark.SparkCatalog")
        .config(f"{prefix}.type", "hadoop")
        .config(f"{prefix}.warehouse", args.warehouse)
    )
    if args.jars_packages.lower() != "none":
        builder = builder.config("spark.jars.packages", args.jars_packages)
    spark = builder.getOrCreate()
    row = spark.sql(
        f"SELECT count(*) AS n, sum({args.sum_column}) AS total FROM {args.table}"
    ).first()
    print(f"count={row['n']} sum_{args.sum_column}={row['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
