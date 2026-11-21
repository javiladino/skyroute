"""Export diario de `bookings_history` a landing/bookings/ingest_date=D/part.json.gz.

Lee las filas con `changed_at` en [D 00:00, D+1 00:00) UTC ordenadas por
`history_id` y escribe JSON lines gzip deterministas (mtime=0, sort_keys), como
clickstream.py. Solo depende de D: dos ejecuciones dan los mismos bytes. No entra
en el zip de Lambda; necesita `psycopg` solo al leer de Postgres. Uso:

    PYTHONPATH=generators python3 -m ota.export_bookings --run-date 2026-01-01 \
        --out-dir build [--dsn postgresql://...]

Escribe `<out-dir>/landing/bookings/ingest_date=D/part.json.gz`; subirlo a S3 es un
paso aparte del owner. Un dia sin filas escribe igualmente un gzip vacio (archivo
valido, cero lineas), para que relanzar el dia deje siempre el mismo objeto.
"""

import argparse
import gzip
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ota import model
from ota.keys import BOOKINGS_PREFIX, daily_key

FIELDS = (
    "history_id", "booking_id", "customer_id", "session_id", "campaign_id",
    "status", "currency", "amount", "created_at", "updated_at", "changed_at",
)
DEFAULT_DSN = "postgresql://postgres@127.0.0.1:5433/postgres"


def day_bounds(run_date: str) -> tuple:
    start = model.parse_day(run_date)
    return start, start + timedelta(days=1)


def _jsonable(value):
    if isinstance(value, datetime):
        return model.fmt_ts(value.astimezone(UTC))
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dsn", default=os.environ.get("BOOKINGS_DSN", DEFAULT_DSN))
    args = parser.parse_args(argv)
    try:
        rows = fetch_rows(args.dsn, args.run_date)
        target = write_export(args.run_date, rows, args.out_dir)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(f"{target} ({len(rows)} filas)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
