"""Export diario de `bookings_history` a landing/bookings/ingest_date=D/part.json.gz.

Lee las filas con `changed_at` en [D 00:00, D+1 00:00) UTC ordenadas por
`history_id` y escribe JSON lines gzip deterministas (mtime=0, sort_keys), como
clickstream.py. Solo depende de D: dos ejecuciones dan los mismos bytes. Va dentro
del zip de la Lambda (lambda.tf no lo excluye) aunque la Lambda no lo importa; necesita
`psycopg` solo al leer de Postgres. Uso:

    PYTHONPATH=generators python3 -m ota.export_bookings --run-date 2026-01-01 \
        --out-dir build [--dsn postgresql://...]
    PYTHONPATH=generators python3 -m ota.export_bookings --from 2026-01-01 --to 2026-01-31 \
        --out-dir build

Con `--from`/`--to` (excluyente con `--run-date`) recorre los dias en orden ascendente y
exporta cada uno con la misma funcion diaria: mismos bytes que un `--run-date` por dia.

Escribe `<out-dir>/landing/bookings/ingest_date=D/part.json.gz`; subirlo a S3 es un
paso aparte del owner. Un dia sin filas escribe igualmente un gzip vacio (archivo
valido, cero lineas), para que relanzar el dia deje siempre el mismo objeto.
"""

import argparse
import gzip
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ota import model
from ota.keys import BOOKINGS_PREFIX, daily_key

FIELDS = (
    "history_id", "booking_id", "customer_id", "session_id", "campaign_id",
    "origin", "destination", "travel_date", "status", "currency", "amount",
    "created_at", "updated_at", "changed_at",
)
DEFAULT_DSN = "postgresql://postgres@127.0.0.1:5433/postgres"


def day_bounds(run_date: str) -> tuple:
    start = model.parse_day(run_date)
    return start, start + timedelta(days=1)


def _jsonable(value):
    if isinstance(value, datetime):
        return model.fmt_ts(value.astimezone(UTC))
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize(row: dict) -> dict:
    return {field: _jsonable(row[field]) for field in FIELDS}


def rows_in_day(history: list, run_date: str) -> list:
    """Filtro puro sobre filas de historial (strings 'Z'): lo que devuelve la consulta SQL."""
    start, end = day_bounds(run_date)
    low, high = model.fmt_ts(start), model.fmt_ts(end)
    picked = [r for r in history if low <= r["changed_at"] < high]
    return sorted(picked, key=lambda r: r["history_id"])


def build_payload(rows: list) -> bytes:
    ordered = sorted((normalize(r) for r in rows), key=lambda r: r["history_id"])
    text = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in ordered)
    return gzip.compress(text.encode("utf-8"), compresslevel=6, mtime=0)


def fetch_rows(dsn: str, run_date: str) -> list:
    import psycopg  # solo hace falta al leer de Postgres
    from psycopg.rows import dict_row

    start, end = day_bounds(run_date)
    query = (
        f"SELECT {', '.join(FIELDS)} FROM bookings_history "
        "WHERE changed_at >= %s AND changed_at < %s ORDER BY history_id"
    )
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(query, (start, end)).fetchall()


def write_export(run_date: str, rows: list, out_dir: str) -> Path:
    model.parse_day(run_date)
    target = Path(out_dir) / daily_key(BOOKINGS_PREFIX, run_date)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_payload(rows))
    return target


def days(start: str, end: str) -> list:
    """Dias YYYY-MM-DD de start a end, ambos incluidos, ascendentes."""
    first, last = model.parse_day(start), model.parse_day(end)
    if first > last:
        raise ValueError("--from debe ser <= --to")
    span = (last - first).days + 1
    return [(first + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(span)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-date", help="YYYY-MM-DD")
    group.add_argument("--from", dest="start", help="YYYY-MM-DD, con --to")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD, con --from")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dsn", default=os.environ.get("BOOKINGS_DSN", DEFAULT_DSN))
    args = parser.parse_args(argv)
    if (args.start is None) != (args.end is None):
        parser.error("--from y --to van juntos")
    try:
        run_dates = [args.run_date] if args.run_date else days(args.start, args.end)
        for run_date in run_dates:
            rows = fetch_rows(args.dsn, run_date)
            target = write_export(run_date, rows, args.out_dir)
            sys.stdout.write(f"{target} ({len(rows)} filas)\n")
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
