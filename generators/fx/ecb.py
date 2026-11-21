"""Tipos de referencia del BCE (base EUR) a landing/fx/ingest_date=D/part.json.gz.

Un archivo por dia logico D con los tipos de la ultima publicacion del BCE <= D
(sabados, domingos y festivos llevan el ultimo dia habil, con su `rate_date`
real). Solo depende de D y de la serie: nunca del reloj. Si la serie esta vacia
o no hay publicacion <= D, falla sin escribir nada: nunca se inventa un tipo.
No entra en el zip de Lambda; solo stdlib. Uso, con `generators/` en PYTHONPATH:

    python3 -m fx.ecb --run-date 2026-01-05 --out-dir build
    python3 -m fx.ecb --from 2025-07-01 --to 2025-12-31 --out-dir build

Escribe `<out-dir>/landing/fx/ingest_date=D/part.json.gz`; subirlo a S3 es un paso
aparte del owner.
"""

import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path

from ota import model
from ota.keys import FX_PREFIX, daily_key

URL_90D = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
URL_FULL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
RETRIES = 3
BACKOFF_SECONDS = 2


class FxError(Exception):
    """El BCE no publico lo necesario; no se escribe ningun archivo."""


def parse_series(xml_bytes: bytes) -> dict:
    """XML del BCE -> {fecha: {divisa: tipo}} (1 EUR = tipo divisa)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise FxError(f"respuesta del BCE no valida: {exc}") from exc
    series = {}
    for day in root.iter(f"{NS}Cube"):
        date = day.get("time")
        if not date:
            continue
        rates = {c.get("currency"): float(c.get("rate")) for c in day if c.get("currency")}
        if rates:
            series[date] = rates
    if not series:
        raise FxError("el BCE no devolvio ningun tipo")
    return series


def rates_for(series: dict, run_date: str) -> tuple:
    """(rate_date, tipos) de la ultima publicacion <= run_date; FxError si no hay.

    Determinista respecto a la serie, no al momento de la ejecucion: si D tiene
    publicacion propia se usa esa; si no (fin de semana o festivo) solo se acepta
    cuando la serie ya contiene una publicacion posterior a D, que prueba que el
    hueco esta cerrado. Un dia habil aun sin publicar, o un hueco sin publicacion
    posterior, es FxError: se reintenta mas tarde; nunca se usa el tipo de D-1.
    """
    model.parse_day(run_date)
    dates = [d for d in series if d <= run_date]
    if not dates:
        raise FxError(f"sin publicacion del BCE <= {run_date}")
    if run_date not in series and not any(d > run_date for d in series):
        raise FxError(
            f"el BCE aun no publica {run_date} ni una fecha posterior; reintentar mas tarde"
        )
    rate_date = max(dates)
    return rate_date, series[rate_date]


def build_payload(run_date: str, rate_date: str, rates: dict) -> bytes:
    rows = [
        {
            "base": "EUR", "currency": ccy, "rate": rates[ccy],
            "rate_date": rate_date, "fx_date": run_date,
        }
        for ccy in sorted(rates)
    ]
    text = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows)
    return gzip.compress(text.encode("utf-8"), compresslevel=6, mtime=0)


def fetch(url: str, retries: int = RETRIES, sleep=time.sleep) -> bytes:
    """Descarga con reintentos; si todos fallan, FxError."""
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                sleep(BACKOFF_SECONDS * (attempt + 1))
    raise FxError(f"no se pudo descargar {url}: {last}")


def needs_full_series(series_90d: dict, date_from: str) -> bool:
    """True si date_from queda a mas de 85 dias de la fecha mas reciente de la serie de 90 dias."""
    newest = model.parse_day(max(series_90d))
    return model.parse_day(date_from) < newest - timedelta(days=85)


def _range(date_from: str, date_to: str) -> list:
    start, end = model.parse_day(date_from), model.parse_day(date_to)
    if end < start:
        raise ValueError("--to debe ser >= --from")
    return [(start + timedelta(days=n)).strftime("%Y-%m-%d") for n in range((end - start).days + 1)]


def export_range(xml_bytes: bytes, date_from: str, date_to: str, out_dir: str) -> list:
    """Valida todos los dias antes de escribir; si falta alguno no se escribe ninguno."""
    series = parse_series(xml_bytes)
    payloads = {}
    for day in _range(date_from, date_to):
        rate_date, rates = rates_for(series, day)
        payloads[day] = build_payload(day, rate_date, rates)
    written = []
    for day, payload in payloads.items():
        target = Path(out_dir) / daily_key(FX_PREFIX, day)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written.append(target)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", help="YYYY-MM-DD (un dia)")
    parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--url",
        help="serie del BCE; por defecto 90 dias, o el historico completo si la fecha es antigua",
    )
    args = parser.parse_args(argv)
    if args.run_date and (args.date_from or args.date_to):
        parser.error("usa --run-date o --from/--to, no ambos")
    if args.run_date:
        date_from = date_to = args.run_date
    elif args.date_from and args.date_to:
        date_from, date_to = args.date_from, args.date_to
    else:
        parser.error("falta --run-date o --from y --to")
    try:
        xml_bytes = fetch(args.url or URL_90D)
        if not args.url and needs_full_series(parse_series(xml_bytes), date_from):
            xml_bytes = fetch(URL_FULL)
        written = export_range(xml_bytes, date_from, date_to, args.out_dir)
    except (FxError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(f"{len(written)} archivos en {args.out_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
