"""Checks WAP propios en PySpark con las reglas en YAML (Ruling "Checks WAP").

Formato de las reglas:

    checks:
      - {type: min_rows, value: 1}
      - {type: not_null, column: booking_id}
      - {type: unique, columns: [booking_id, history_id]}
      - {type: unique, columns: [booking_id], where: "is_current"}   # `where` es opcional
      - {type: accepted_values, column: status, values: [confirmed, cancelled]}
      - {type: expression, name: valid_range, sql: "valid_to IS NULL OR valid_to >= valid_from"}

`expression` es un predicado que debe cumplir cada fila.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


@dataclass(frozen=True)
class Failure:
    rule: str
    message: str
    count: int


def load_rules(rules_yaml) -> list[dict]:
    """`rules_yaml` es un Path a un archivo YAML o el texto YAML."""
    text = rules_yaml.read_text() if isinstance(rules_yaml, Path) else rules_yaml
    document = yaml.safe_load(text) or {}
    return list(document.get("checks", []))


def _check(df: DataFrame, rule: dict) -> Failure | None:
    kind = rule["type"]
    if kind == "min_rows":
        rows = df.count()
        if rows < rule["value"]:
            return Failure("min_rows", f"{rows} filas, minimo {rule['value']}", rows)
    elif kind == "not_null":
        column = rule["column"]
        bad = df.filter(F.col(column).isNull()).count()
        if bad:
            return Failure(f"not_null:{column}", f"{bad} filas con {column} nulo", bad)
    elif kind == "unique":
        columns = rule["columns"]
        where = rule.get("where")
        scope = df.filter(F.expr(where)) if where else df
        bad = scope.groupBy(*columns).count().filter(F.col("count") > 1).count()
        if bad:
            label = f"unique:{','.join(columns)}" + (f"[{where}]" if where else "")
            return Failure(label, f"{bad} claves repetidas", bad)
    elif kind == "accepted_values":
        column = rule["column"]
        bad = df.filter(~F.col(column).isin(*rule["values"]) | F.col(column).isNull()).count()
        if bad:
            return Failure(f"accepted_values:{column}", f"{bad} valores fuera de lista", bad)
    elif kind == "expression":
        name = rule.get("name", rule["sql"])
        bad = df.filter(~F.coalesce(F.expr(rule["sql"]), F.lit(False))).count()
        if bad:
            return Failure(f"expression:{name}", f"{bad} filas incumplen {rule['sql']}", bad)
    else:
        raise ValueError(f"tipo de check desconocido: {kind}")
    return None


def run_checks(df: DataFrame, rules_yaml) -> list[Failure]:
    """Devuelve los fallos; lista vacia = todo bien. No lanza por un check fallido."""
    failures = []
    for rule in load_rules(rules_yaml):
        failure = _check(df, rule)
        if failure is not None:
            failures.append(failure)
    return failures
