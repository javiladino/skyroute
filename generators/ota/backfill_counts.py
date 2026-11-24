"""Recuento esperado de eventos de clickstream de un rango (Validation 4b del backfill).

Sale del generador, sin leer S3: por dia, eventos de fondo (el `total` de cada slot), sesiones
de recorrido emitidas ese dia y un `purchase` por reserva. Cuenta eventos distintos
(`event_id`); los duplicados intencionados (3 %) no entran. Solo stdlib. Uso, con
`generators/` en PYTHONPATH:

    python3 -m ota.backfill_counts --from 2026-05-01 --to 2026-05-07
"""

import argparse
import random
import sys
from datetime import timedelta

from ota import model
from ota.keys import SLOTS_PER_DAY, seed_for


def days(date_from: str, date_to: str) -> list:
    start, end = model.parse_day(date_from), model.parse_day(date_to)
    if end < start:
        raise ValueError("--to debe ser >= --from")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((end - start).days + 1)]


def day_count(run_date: str) -> int:
    background = sum(
        random.Random(seed_for(run_date, slot, "clickstream")).randint(25, 45)
        for slot in range(SLOTS_PER_DAY)
    )
    journey = sum(len(j["events"]) for j in model.customer_journeys(run_date))
    return background + journey + len(model.bookings_for_day(run_date))


def expected_unique_events(date_from: str, date_to: str) -> int:
    return sum(day_count(d) for d in days(date_from, date_to))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    args = parser.parse_args(argv)
    try:
        total = expected_unique_events(args.date_from, args.date_to)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(f"{total}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
