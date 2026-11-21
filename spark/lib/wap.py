"""Ciclo WAP por ejecucion (Design Decision 9): rama run_<D>, escritura, checks, fast_forward.

1. Si existe `run_<D>`, se borra. 2. Se crea desde el snapshot actual de `main`.
3. Se escribe en la rama (`spark.wap.branch`). 4. Checks. 5. `fast_forward` de `main`.
6. Se borra la rama. Si un check falla, la rama se conserva para inspeccion y no se publica.
La tabla necesita `write.wap.enabled=true`. No hace falta snapshot semilla: verificado con
Iceberg 1.7.1 que CREATE BRANCH sobre una tabla vacia funciona (crea un snapshot vacio) y
que fast_forward de `main` sobre esa rama tambien.
"""

from collections.abc import Callable

from pyspark.sql import SparkSession

from lib.checks import Failure, run_checks


class WapCheckError(RuntimeError):
    def __init__(self, branch: str, failures: list[Failure]):
        self.branch = branch
        self.failures = failures
        detail = "; ".join(f"{f.rule}: {f.message}" for f in failures)
        super().__init__(f"checks fallidos en la rama {branch}, no se publica: {detail}")


def branch_name(run_date: str) -> str:
    return f"run_{run_date}"


def list_branches(spark: SparkSession, table: str) -> list[str]:
    rows = spark.sql(f"SELECT name FROM {table}.refs WHERE type = 'BRANCH'").collect()
    return sorted(row["name"] for row in rows)


def run_wap(
    spark: SparkSession,
    table: str,
    run_date: str,
    write: Callable[[SparkSession], None],
    rules_yaml,
) -> str:
    """`table` es catalogo.base.tabla. Devuelve el nombre de la rama publicada."""
    catalog = table.split(".")[0]
    identifier = table.split(".", 1)[1]
    branch = branch_name(run_date)
    spark.sql(f"ALTER TABLE {table} DROP BRANCH IF EXISTS `{branch}`")
    spark.sql(f"ALTER TABLE {table} CREATE BRANCH `{branch}`")
    spark.conf.set("spark.wap.branch", branch)
    try:
        write(spark)
    finally:
        spark.conf.unset("spark.wap.branch")
    failures = run_checks(spark.read.option("branch", branch).table(table), rules_yaml)
    if failures:
        raise WapCheckError(branch, failures)
    spark.sql(f"CALL {catalog}.system.fast_forward('{identifier}', 'main', '{branch}')")
    spark.sql(f"ALTER TABLE {table} DROP BRANCH `{branch}`")
    return branch
