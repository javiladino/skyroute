"""Compara un listado de landing/clickstream/ con las claves esperadas.

Rango: D-182 a D-1 (D fija, la decide el owner). Solo stdlib; no entra en el
zip. Uso:
    python3 generators/verify_landing.py --listing listado.json --d YYYY-MM-DD
El listado es la salida JSON de `aws s3api list-objects-v2` guardada a archivo.
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

from ota.keys import SLOTS_PER_DAY, landing_key

DAYS = 182
_INGEST = re.compile(r"/ingest_date=(\d{4}-\d{2}-\d{2})/")


def _days(d: str) -> list:
    end = datetime.strptime(d, "%Y-%m-%d").date()
    return [(end - timedelta(days=n)).isoformat() for n in range(DAYS, 0, -1)]


def expected_keys(d: str) -> set:
    return {landing_key(day, slot) for day in _days(d) for slot in range(SLOTS_PER_DAY)}


def compare(listed_keys, d: str) -> dict:
    """Solo mira claves con ingest_date en [D-182, D-1]; el resto se ignora."""
    in_range = set(_days(d))
    seen = set()
    for key in listed_keys:
        match = _INGEST.search(key)
        if match and match.group(1) in in_range:
            seen.add(key)
    expected = expected_keys(d)
    per_day = Counter(_INGEST.search(k).group(1) for k in seen)
    return {
        "missing": sorted(expected - seen),
        "extra": sorted(seen - expected),
        "per_day": {day: per_day.get(day, 0) for day in sorted(in_range)},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listing", required=True)
    parser.add_argument("--d", required=True, help="fecha D fija (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    with open(args.listing, encoding="utf-8") as handle:
        data = json.load(handle)
    keys = [item["Key"] for item in data.get("Contents", [])]
    report = compare(keys, args.d)
    short_days = {day: n for day, n in report["per_day"].items() if n != SLOTS_PER_DAY}
    print(json.dumps({
        "d": args.d,
        "days": len(report["per_day"]),
        "objects_in_range": sum(report["per_day"].values()),
        "days_not_96": short_days,
        "missing": report["missing"],
        "extra": report["extra"],
    }, indent=2))
    return 0 if not report["missing"] and not report["extra"] else 1


if __name__ == "__main__":
    sys.exit(main())
