"""Guard `schema_mismatch`: la tabla Silver existente debe tener todas las columnas del DDL.

`CREATE TABLE IF NOT EXISTS` no toca una tabla que ya existe: si el DDL gana columnas (p. ej.
`origin`, `destination`, `travel_date` en las reservas) y la tabla se creo con el DDL viejo, el
MERGE o el INSERT fallarian a medias o perderian columnas. Cada job Silver llama a
`require_columns` tras su CREATE y antes de escribir; si faltan columnas lanza `SchemaMismatch`
y no se escribe nada. La salida es reconstruir la tabla (Ruling "Bronze rebuild exception"),
nunca evolucionarla sola.
"""

import re

from pyspark.sql import SparkSession

_COLUMN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+[A-Za-z]")


class SchemaMismatch(RuntimeError):
    """La tabla existente no tiene todas las columnas del DDL del job."""


def ddl_columns(ddl: str) -> list[str]:
    """Nombres de columna del bloque `CREATE TABLE ... ( ... ) USING` de un DDL de Silver."""
    body = ddl.split("(", 1)[1].split(") USING", 1)[0]
    names = []
    for line in body.splitlines():
        match = _COLUMN.match(line)
        if match:
            names.append(match.group(1))
    if not names:
        raise ValueError("DDL sin columnas reconocibles")
    return names


def require_columns(spark: SparkSession, table: str, columns) -> None:
    """Falla con `schema_mismatch` si a `table` le falta alguna de `columns`."""
    existing = {field.name.lower() for field in spark.table(table).schema.fields}
    missing = [c for c in columns if c.lower() not in existing]
    if missing:
        raise SchemaMismatch(
            f"schema_mismatch: a {table} le faltan las columnas {missing}; "
            "reconstruye la tabla (rebuild_tables), no se escribe nada"
        )
