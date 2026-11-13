"""Filas de `bookings` coherentes con los `purchase` del clickstream.

No entra en el zip de Lambda. Emite SQL `INSERT` (solo stdlib) que se carga con
`psql` dentro del contenedor (OQ7). Uso, con `generators/` en PYTHONPATH:

    python3 -m ota.seed_postgres --from 2026-01-01 --to 2026-01-03 [--out f.sql]
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


def sql_for_day(run_date: str) -> str:
    cols = ", ".join(COLUMNS)
    lines = []
    for row in rows_for_day(run_date):
        values = ", ".join(_literal(row[c]) for c in COLUMNS)
        lines.append(f"INSERT INTO bookings ({cols}) VALUES ({values}) ON CONFLICT (booking_id) DO NOTHING;")
    return "\n".join(lines) + "\n"


def sql_for_range(date_from: str, date_to: str) -> str:
    start = model.parse_day(date_from)
    end = model.parse_day(date_to)
    if end < start:
        raise ValueError("--to debe ser >= --from")
    parts = ["BEGIN;\n"]
    day = start
    while day <= end:
        parts.append(sql_for_day(day.strftime("%Y-%m-%d")))
        day += timedelta(days=1)
    parts.append("COMMIT;\n")
    return "".join(parts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", help="archivo de salida; por defecto stdout")
    args = parser.parse_args(argv)
    try:
        sql = sql_for_range(args.date_from, args.date_to)
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
