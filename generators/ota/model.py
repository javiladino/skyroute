"""Catalogos propios y reglas de coherencia (reservas del dia).

Las reservas de un dia son la fuente comun: el clickstream emite un
`purchase` por reserva en su slot y seed_postgres carga las mismas filas.
"""

import random
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from ota.keys import (
    SLOTS_PER_DAY,
    booking_id,
    campaign_id,
    customer_id,
    seed_for,
    session_id,
)

CUSTOMER_POOL = 20000
BOOKINGS_PER_DAY = 120

AIRPORTS = ["CDG", "ORY", "LHR", "MAD", "BCN", "FCO", "AMS", "FRA", "LIS", "ZRH", "JFK", "DXB"]
ROUTES = [
    ("CDG", "LHR"), ("CDG", "MAD"), ("CDG", "BCN"), ("ORY", "FCO"),
    ("CDG", "LIS"), ("LHR", "JFK"), ("AMS", "CDG"), ("FRA", "CDG"),
    ("ZRH", "CDG"), ("CDG", "DXB"), ("MAD", "JFK"), ("BCN", "AMS"),
]
CAMPAIGNS = [
    "summer-sale", "city-breaks", "last-minute", "loyalty-boost",
    "newsletter-weekly", "brand-search", "retargeting", "family-offer",
]
CURRENCIES = ["EUR", "EUR", "EUR", "GBP", "USD", "CHF"]
STATUSES = ["confirmed", "confirmed", "confirmed", "pending", "cancelled"]
EVENT_TYPES = ["page_view", "search", "add_to_cart", "consent"]
EVENT_WEIGHTS = [60, 25, 10, 5]


def parse_day(run_date: str) -> datetime:
    return datetime.strptime(run_date, "%Y-%m-%d").replace(tzinfo=UTC)


def fmt_ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def currency_for(customer_n: int) -> str:
    return CURRENCIES[customer_n % len(CURRENCIES)]


def campaign_n_for(index: int) -> int:
    return index % len(CAMPAIGNS) + 1


def consent_ts_for(customer_n: int) -> str:
    return fmt_ts(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=customer_n % 365))


def _status_chain(final_status: str, rng: random.Random) -> list:
    """Cadena de estados que acaba en `final_status` (1 a 3 versiones)."""
    if final_status == "confirmed":
        return ["pending", "confirmed"] if rng.random() < 0.5 else ["confirmed"]
    if final_status == "cancelled":
        if rng.random() < 0.5:
            return ["pending", "cancelled"]
        return ["pending", "confirmed", "cancelled"]
    return [final_status]


@lru_cache(maxsize=512)
def _build(run_date: str) -> tuple:
    """(reservas en su estado final, versiones de estado de todas las reservas)."""
    day = parse_day(run_date)
    out = []
    versions = []
    for j in range(BOOKINGS_PER_DAY):
        rng = random.Random(seed_for(run_date, j, "booking"))
        slot = rng.randrange(SLOTS_PER_DAY)
        customer_n = rng.randint(1, CUSTOMER_POOL)
        campaign_idx = rng.randrange(len(CAMPAIGNS))
        origin, dest = ROUTES[rng.randrange(len(ROUTES))]
        amount = round(rng.uniform(40, 1500), 2)
        status = STATUSES[rng.randrange(len(STATUSES))]
        offset = rng.randrange(900)
        created = day + timedelta(minutes=15 * slot, seconds=offset)

        hist_rng = random.Random(seed_for(run_date, j, "booking-history"))
        chain = _status_chain(status, hist_rng)
        updated = created
        base = {
            "booking_id": booking_id(run_date, j),
            "customer_id": customer_id(customer_n),
            "session_id": session_id(run_date, slot, 1000 + j),
            "campaign_id": campaign_id(campaign_n_for(campaign_idx)),
            "currency": currency_for(customer_n),
            "amount": amount,
            "created_at": fmt_ts(created),
        }
        for version, step_status in enumerate(chain):
            if version > 0:
                updated += timedelta(minutes=hist_rng.randint(1, 600))
            versions.append({**base, "status": step_status, "updated_at": fmt_ts(updated),
                             "version": version})
        out.append({
            **base,
            "status": status,
            "route": f"{origin}-{dest}",
            "slot": slot,
            "updated_at": fmt_ts(updated),
        })
    return tuple(out), tuple(versions)


def _bookings(run_date: str) -> tuple:
    return _build(run_date)[0]


def booking_versions_for_day(run_date: str) -> list:
    """Todas las versiones de estado de las reservas creadas en `run_date`.

    Cada version lleva `version` (0 = alta) y `updated_at` estrictamente creciente por reserva.
    """
    return [dict(v) for v in _build(run_date)[1]]


def customer_journeys(run_date: str) -> list:
    """Recorridos por cliente: eventos previos a cada compra, en la sesion de la reserva.

    Devuelve una lista de recorridos (uno por reserva): `slot` (el del purchase) y `events`
    con 1 a 4 eventos de navegacion del mismo cliente y sesion, separados por menos de
    30 min, que acaban justo antes del `purchase` en `created_at`.

    Los eventos pueden caer hasta 80 min antes de `created_at` (4 saltos de hasta 20 min),
    es decir, fuera del slot de la reserva e incluso en D-1 si la reserva es de las primeras
    del dia. Se emiten en el slot del purchase; su `event_ts` real es anterior (llegada tardia).
    """
    journeys = []
    for j, booking in enumerate(_bookings(run_date)):
        rng = random.Random(seed_for(run_date, j, "journey"))
        n_events = rng.randint(1, 4)
        end = datetime.strptime(booking["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        customer_n = int(booking["customer_id"][1:])
        ts = end
        events = []
        for k in range(n_events - 1, -1, -1):
            ts -= timedelta(seconds=rng.randint(60, 20 * 60))
            etype = "add_to_cart" if k == n_events - 1 else rng.choice(["page_view", "search"])
            events.append({
                "n": k,
                "event_type": etype,
                "event_ts": fmt_ts(ts),
                "customer_id": booking["customer_id"],
                "session_id": booking["session_id"],
                "campaign_id": booking["campaign_id"],
                "currency": booking["currency"],
                "amount": booking["amount"] if etype == "add_to_cart" else None,
                "consent_ts": consent_ts_for(customer_n),
            })
        events.sort(key=lambda e: e["n"])
        journeys.append({"booking_id": booking["booking_id"], "j": j,
                         "slot": booking["slot"], "events": events})
    return journeys


def bookings_for_day(run_date: str) -> list:
    return [dict(b) for b in _bookings(run_date)]


def bookings_for_slot(run_date: str, slot: int) -> list:
    return [dict(b) for b in _bookings(run_date) if b["slot"] == slot]


def journeys_for_slot(run_date: str, slot: int) -> list:
    return [jr for jr in customer_journeys(run_date) if jr["slot"] == slot]
