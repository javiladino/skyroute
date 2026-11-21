"""Filas de `bookings` coherentes con los `purchase` del clickstream.

No entra en el zip de Lambda. Emite SQL `INSERT` (solo stdlib) que se carga con
`psql` dentro del contenedor (OQ7). Uso, con `generators/` en PYTHONPATH:

    python3 -m ota.seed_postgres --from 2026-01-01 --to 2026-01-03 [--rebuild] [--out f.sql]

`history_id` es un serial de Postgres: solo es reproducible si se parte de tablas
vacias, es decir, con --rebuild (REBUILD=1 en make). Sin --rebuild los ids dependen de
las cargas previas.
"""

import argparse
import sys
from datetime import timedelta

from ota import model

COLUMNS = (
    "booking_id", "customer_id", "session_id", "campaign_id",
    "status", "currency", "amount", "created_at", "updated_at",
)


def rows_for_day(run_date: str) -> list:
    return [{c: b[c] for c in COLUMNS} for b in model.bookings_for_day(run_date)]


def _literal(value) -> str:
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _days(date_from: str, date_to: str) -> list:
    start = model.parse_day(date_from)
    end = model.parse_day(date_to)
    if end < start:
        raise ValueError("--to debe ser >= --from")
    days = []
    day = start
    while day <= end:
        days.append(day.strftime("%Y-%m-%d"))
        day += timedelta(days=1)
    return days


def versions_for_range(date_from: str, date_to: str) -> list:
    """Versiones de estado del rango en orden determinista (updated_at, booking_id, version)."""
    versions = []
    for day in _days(date_from, date_to):
        versions.extend(model.booking_versions_for_day(day))
    versions.sort(key=lambda v: (v["updated_at"], v["booking_id"], v["version"]))
    return versions


def sql_for_versions(versions: list) -> str:
    """Una sentencia por version; el UPDATE solo avanza (`updated_at` mayor), asi que
    recargar el mismo rango sin --rebuild no duplica filas en `bookings_history`."""
    cols = ", ".join(COLUMNS)
    lines = []
    for row in versions:
        values = ", ".join(_literal(row[c]) for c in COLUMNS)
        lines.append(
            f"INSERT INTO bookings ({cols}) VALUES ({values}) "
            "ON CONFLICT (booking_id) DO UPDATE "
            "SET status = EXCLUDED.status, updated_at = EXCLUDED.updated_at "
            "WHERE bookings.updated_at < EXCLUDED.updated_at;"
        )
    return "\n".join(lines) + "\n"


def sql_for_day(run_date: str) -> str:
    return sql_for_versions(sorted(
        model.booking_versions_for_day(run_date),
        key=lambda v: (v["updated_at"], v["booking_id"], v["version"]),
    ))


def sql_for_range(date_from: str, date_to: str, rebuild: bool = False) -> str:
    parts = ["BEGIN;\n"]
    if rebuild:
        parts.append("TRUNCATE bookings, bookings_history RESTART IDENTITY;\n")
    parts.append(sql_for_versions(versions_for_range(date_from, date_to)))
    parts.append("COMMIT;\n")
    return "".join(parts)


def replay_history(date_from: str, date_to: str) -> list:
    """Simula en Python lo que escribiria el trigger tras `sql_for_range(..., rebuild=True)`:
    `history_id` 1..N en orden de aplicacion, con la misma regla de avance del UPDATE."""
    current = {}
    history = []
    for row in versions_for_range(date_from, date_to):
        prev = current.get(row["booking_id"])
        if prev is not None and not prev["updated_at"] < row["updated_at"]:
            continue
        current[row["booking_id"]] = row
        history.append({
            "history_id": len(history) + 1,
            **{c: row[c] for c in COLUMNS},
            "changed_at": row["updated_at"],
        })
    return history


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", help="archivo de salida; por defecto stdout")
    parser.add_argument(
        "--rebuild", action="store_true",
        help="antepone TRUNCATE bookings, bookings_history RESTART IDENTITY "
        "(history_id reproducible)",
    )
    args = parser.parse_args(argv)
    try:
        sql = sql_for_range(args.date_from, args.date_to, rebuild=args.rebuild)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(sql)
    else:
        sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
