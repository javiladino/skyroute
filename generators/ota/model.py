"""Catalogos propios y reglas de coherencia (reservas del dia).

Las reservas de un dia son la fuente comun: el clickstream emite un
`purchase` por reserva en su slot y seed_postgres carga las mismas filas.
"""

import random
from datetime import datetime, timedelta, timezone
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
    return datetime.strptime(run_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def fmt_ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def currency_for(customer_n: int) -> str:
    return CURRENCIES[customer_n % len(CURRENCIES)]


def campaign_n_for(index: int) -> int:
    return index % len(CAMPAIGNS) + 1


def consent_ts_for(customer_n: int) -> str:
    return fmt_ts(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=customer_n % 365))


@lru_cache(maxsize=512)
def _bookings(run_date: str) -> tuple:
    day = parse_day(run_date)
    out = []
    for j in range(BOOKINGS_PER_DAY):
        rng = random.Random(seed_for(run_date, j, "booking"))
        slot = rng.randrange(SLOTS_PER_DAY)
        customer_n = rng.randint(1, CUSTOMER_POOL)
        campaign_idx = rng.randrange(len(CAMPAIGNS))
        origin, dest = ROUTES[rng.randrange(len(ROUTES))]
        amount = round(rng.uniform(40, 1500), 2)
        status = STATUSES[rng.randrange(len(STATUSES))]
        offset = rng.randrange(900)
        update_minutes = rng.randint(1, 600)
        created = day + timedelta(minutes=15 * slot, seconds=offset)
        updated = created if status == "confirmed" else created + timedelta(minutes=update_minutes)
        out.append({
            "booking_id": booking_id(run_date, j),
            "customer_id": customer_id(customer_n),
            "session_id": session_id(run_date, slot, 1000 + j),
            "campaign_id": campaign_id(campaign_n_for(campaign_idx)),
            "status": status,
            "currency": currency_for(customer_n),
            "amount": amount,
            "route": f"{origin}-{dest}",
            "slot": slot,
            "created_at": fmt_ts(created),
            "updated_at": fmt_ts(updated),
        })
    return tuple(out)


def bookings_for_day(run_date: str) -> list:
    return [dict(b) for b in _bookings(run_date)]


def bookings_for_slot(run_date: str, slot: int) -> list:
    return [dict(b) for b in _bookings(run_date) if b["slot"] == slot]
