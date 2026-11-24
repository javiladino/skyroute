"""Gasto publicitario diario por campana a landing/ad_spend/ingest_date=D/part.json.gz.

Fuente diaria local, como `fx` y `bookings`: una fila por campana de `model.CAMPAIGNS` y dia.
Solo depende de D (semilla de keys.seed_for): dos ejecuciones dan los mismos bytes (JSON lines
gzip, `mtime=0`, `sort_keys`). Va dentro del zip de la Lambda (lambda.tf no lo excluye)
aunque la Lambda no lo importa; solo stdlib. Uso, con `generators/` en PYTHONPATH:

    python3 -m ota.ad_spend --run-date 2026-01-05 --out-dir build

Escribe `<out-dir>/landing/ad_spend/ingest_date=D/part.json.gz`; subirlo a S3 es un paso
aparte del owner.
"""

import argparse
import gzip
import json
import random
import sys
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    try:
        target = write_export(args.run_date, args.out_dir)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(f"{target} ({len(model.CAMPAIGNS)} filas)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
