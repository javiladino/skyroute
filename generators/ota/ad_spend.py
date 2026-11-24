"""Gasto publicitario diario por campana a landing/ad_spend/ingest_date=D/part.json.gz.

Fuente diaria local, como `fx` y `bookings`: una fila por campana de `model.CAMPAIGNS` y dia.
Solo depende de D (semilla de keys.seed_for): dos ejecuciones dan los mismos bytes (JSON lines
gzip, `mtime=0`, `sort_keys`). Va dentro del zip de la Lambda (lambda.tf no lo excluye)
aunque la Lambda no lo importa; solo stdlib. Uso, con `generators/` en PYTHONPATH:

    python3 -m ota.ad_spend --run-date 2026-01-05 --out-dir build
    python3 -m ota.ad_spend --from 2026-01-01 --to 2026-01-31 --out-dir build

Con `--from`/`--to` (excluyente con `--run-date`) recorre los dias en orden ascendente y
escribe cada uno con la misma funcion diaria: mismos bytes que un `--run-date` por dia.

Escribe `<out-dir>/landing/ad_spend/ingest_date=D/part.json.gz`; subirlo a S3 es un paso
aparte del owner.
"""

import argparse
import gzip
import json
import random
import sys
from datetime import timedelta
from pathlib import Path

from ota import model
from ota.keys import AD_SPEND_PREFIX, campaign_id, daily_key, seed_for

CURRENCY = "EUR"


def build_rows(run_date: str) -> list:
    model.parse_day(run_date)
    rows = []
    for n in range(1, len(model.CAMPAIGNS) + 1):
        rng = random.Random(seed_for(run_date, n, "ad_spend"))
        spend = round(rng.uniform(50, 800), 2)
        impressions = int(spend * rng.uniform(80, 200))
        clicks = int(impressions * rng.uniform(0.01, 0.05))
        rows.append({
            "spend_date": run_date,
            "campaign_id": campaign_id(n),
            "spend": spend,
            "currency": CURRENCY,
            "impressions": impressions,
            "clicks": clicks,
        })
    return rows


def generate(run_date: str) -> bytes:
    text = "".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in build_rows(run_date)
    )
    return gzip.compress(text.encode("utf-8"), compresslevel=6, mtime=0)


def write_export(run_date: str, out_dir: str) -> Path:
    payload = generate(run_date)
    target = Path(out_dir) / daily_key(AD_SPEND_PREFIX, run_date)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
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
    args = parser.parse_args(argv)
    if (args.start is None) != (args.end is None):
        parser.error("--from y --to van juntos")
    try:
        run_dates = [args.run_date] if args.run_date else days(args.start, args.end)
        for run_date in run_dates:
            target = write_export(run_date, args.out_dir)
            sys.stdout.write(f"{target} ({len(model.CAMPAIGNS)} filas)\n")
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
