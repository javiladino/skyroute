"""Fixtures de Spark: catalogo Iceberg `hadoop` en tmp_path, sin AWS.

La sesion es una por ejecucion de pytest (arrancar la JVM es lo caro); cada test usa un
catalogo con nombre unico y su propio warehouse, asi que no comparten tablas.
Descarga iceberg-spark-runtime de Maven Central la primera vez (spark.jars.packages).
"""

import gzip
import itertools
import json
import os
import sys
import time
from pathlib import Path

import pytest

# Los workers de Python deben ser el mismo interprete que el driver, y el collect() de
# timestamps convierte con la zona local del proceso: se fija UTC para que los tests no
# dependan de la maquina.
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ["TZ"] = "UTC"
if hasattr(time, "tzset"):
    time.tzset()

SPARK_DIR = Path(__file__).resolve().parents[1]
if str(SPARK_DIR) not in sys.path:
    sys.path.insert(0, str(SPARK_DIR))

from lib.session import ICEBERG_EXTENSIONS, catalog_conf  # noqa: E402

ICEBERG_RUNTIME = "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.1"
_counter = itertools.count()


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[2]")
        .appName("skyroute-tests")
        .config("spark.jars.packages", ICEBERG_RUNTIME)
        .config("spark.sql.extensions", ICEBERG_EXTENSIONS)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.warehouse.dir", str(tmp_path_factory.mktemp("spark-warehouse")))
        .getOrCreate()
    )
    yield session
    session.stop()


class Lake:
    """Un catalogo hadoop y una raiz de landing aislados en tmp_path."""

    def __init__(self, spark, root: Path):
        self.spark = spark
        self.root = root
        self.catalog = f"cat{next(_counter)}"
        self.warehouse = str(root / "warehouse")
        for key, value in catalog_conf(self.catalog, "hadoop", self.warehouse, "eu-west-3").items():
            spark.conf.set(key, value)

    def table(self, source: str, database: str = "skyroute_dev_bronze") -> str:
        return f"{self.catalog}.{database}.{source}"

    def write_landing(self, key: str, rows: list[dict]) -> Path:
        """Escribe un part.json.gz en <root>/<key>; rows vacio da un gzip vacio."""
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
        target.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
        return target

    def argv(self, source: str, run_date: str) -> list[str]:
        return [
            "--source", source,
            "--run-date", run_date,
            "--catalog-name", self.catalog,
            "--catalog-impl", "hadoop",
            "--warehouse", self.warehouse,
            "--landing-root", str(self.root),
            "--jars-packages", "none",
        ]  # fmt: skip

    def rows(self, source: str, order_by: str) -> list[dict]:
        table = self.spark.table(self.table(source))
        frame = table.orderBy(order_by, "_ingest_date", "_source_file")
        return [r.asDict() for r in frame.collect()]


@pytest.fixture
def lake(spark, tmp_path):
    return Lake(spark, tmp_path)
