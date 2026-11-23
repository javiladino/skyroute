"""Catalogos propios y reglas de coherencia (reservas del dia).

Las reservas de un dia son la fuente comun: el clickstream emite un
`purchase` por reserva en su slot y seed_postgres carga las mismas filas.
"""

import copy
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
# Navegacion de fondo: solo estos tipos. `add_to_cart`, `begin_checkout` y `purchase` salen
# unicamente de sesiones de recorrido, en orden y con abandono determinista.
BACKGROUND_EVENT_TYPES = ["page_view", "search", "product_view", "consent"]
BACKGROUND_EVENT_WEIGHTS = [55, 25, 15, 5]
# Pasos del funnel antes de la compra, en orden; `purchase` cierra la sesion de la reserva.
FUNNEL_STEPS = ["search", "product_view", "add_to_cart", "begin_checkout"]
# Catalogo completo de tipos admitidos (fondo mas recorrido).
EVENT_TYPES = ["page_view", "search", "product_view", "add_to_cart", "begin_checkout",
               "purchase", "consent"]
MAX_TOUCHPOINTS = 4
JOURNEY_WINDOW_DAYS = 7  # el generador del dia X emite sesiones de reservas de X a X+6


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
        travel_rng = random.Random(seed_for(run_date, j, "travel"))
        travel_date = (day + timedelta(days=travel_rng.randint(1, 180))).strftime("%Y-%m-%d")
        base = {
            "booking_id": booking_id(run_date, j),
            "customer_id": customer_id(customer_n),
            "session_id": session_id(run_date, slot, 1000 + j),
            "campaign_id": campaign_id(campaign_n_for(campaign_idx)),
            "origin": origin,
            "destination": dest,
            "travel_date": travel_date,
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


def _funnel_events(rng: random.Random, steps: list, end: datetime, booking: dict,
                   campaign: str, amount: float) -> list:
    """Eventos de `steps` (en orden de funnel) antes de `end`, con saltos de 1 a 20 min."""
    ts = end
    events = []
    for k in range(len(steps) - 1, -1, -1):
        ts -= timedelta(seconds=rng.randint(60, 20 * 60))
        events.append({
            "n": k,
            "event_type": steps[k],
            "event_ts": fmt_ts(ts),
            "customer_id": booking["customer_id"],
            "campaign_id": campaign,
            "currency": booking["currency"],
            "amount": amount if steps[k] == "add_to_cart" else None,
            "consent_ts": consent_ts_for(int(booking["customer_id"][1:])),
        })
    events.sort(key=lambda e: e["n"])
    return events


@lru_cache(maxsize=512)
def _booking_journeys(booking_day: str) -> tuple:
    """Recorridos de las reservas de `booking_day`: de 1 a 4 sesiones (touchpoints) cada uno.

    Las sesiones previas caen en dias distintos de D-6..D-1, con campana propia y abandono
    determinista (un prefijo del funnel, sin compra). La ultima es la sesion de la reserva
    (dia D, campana de la reserva) y completa el funnel hasta el `purchase`. Todo sale de la
    semilla de la fecha de la reserva.
    """
    day = parse_day(booking_day)
    out = []
    for j, booking in enumerate(_bookings(booking_day)):
        rng = random.Random(seed_for(booking_day, j, "journey"))
        n_sessions = rng.randint(1, MAX_TOUCHPOINTS)
        offsets = sorted(rng.sample(range(1, JOURNEY_WINDOW_DAYS), n_sessions - 1), reverse=True)
        offsets.append(0)
        sessions = []
        for seq, offset in enumerate(offsets):
            last = offset == 0
            if last:
                end = datetime.strptime(booking["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC)
                slot = booking["slot"]
                steps = list(FUNNEL_STEPS)
                campaign = booking["campaign_id"]
                amount = booking["amount"]
                sid = booking["session_id"]
            else:
                slot = rng.randrange(8, SLOTS_PER_DAY)
                end = (day - timedelta(days=offset) + timedelta(minutes=15 * slot,
                                                                 seconds=rng.randrange(900)))
                steps = FUNNEL_STEPS[: rng.randint(1, len(FUNNEL_STEPS))]
                campaign = campaign_id(campaign_n_for(rng.randrange(len(CAMPAIGNS))))
                amount = round(rng.uniform(40, 1500), 2)
                sid = session_id(booking_day, slot, 3000 + j * 10 + seq)
            events = _funnel_events(rng, steps, end, booking, campaign, amount)
            for event in events:
                event["session_id"] = sid
            sessions.append({
                "booking_id": booking["booking_id"],
                "booking_day": booking_day,
                "booking_j": j,
                "touch_seq": seq,
                "n_touches": n_sessions,
                "offset": offset,
                "emit_date": (day - timedelta(days=offset)).strftime("%Y-%m-%d"),
                "slot": slot,
                "session_id": sid,
                "campaign_id": campaign,
                "events": events,
            })
        out.append(tuple(sessions))
    return tuple(out)


def booking_journeys(booking_day: str) -> list:
    """Sesiones de cada reserva de `booking_day` (una lista por reserva, en orden temporal)."""
    return copy.deepcopy([list(sessions) for sessions in _booking_journeys(booking_day)])


@lru_cache(maxsize=512)
def _emitted(run_date: str) -> dict:
    """slot -> sesiones que emite el generador de `run_date` (reservas de run_date..run_date+6).

    `j` es unico por (run_date, slot) entre todos los dias de reserva:
    `offset * BOOKINGS_PER_DAY + j de la reserva`.
    """
    day = parse_day(run_date)
    by_slot: dict = {}
    for offset in range(JOURNEY_WINDOW_DAYS):
        booking_day = (day + timedelta(days=offset)).strftime("%Y-%m-%d")
        for sessions in _booking_journeys(booking_day):
            for session in sessions:
                if session["offset"] != offset:
                    continue
                by_slot.setdefault(session["slot"], []).append(
                    {**session, "j": offset * BOOKINGS_PER_DAY + session["booking_j"]})
    for sessions in by_slot.values():
        sessions.sort(key=lambda s: s["j"])
    return by_slot


def customer_journeys(run_date: str) -> list:
    """Sesiones de recorrido que emite `run_date`, de todos sus slots.

    Cada elemento: `j` (unico por dia), `slot`, `booking_id`, `touch_seq`, `events` (de 1 a 4
    eventos de funnel del mismo cliente y sesion, separados por menos de 30 min). Los eventos
    de la sesion de la reserva pueden caer hasta 80 min antes de `created_at`, fuera del slot
    e incluso en D-1: se emiten en su slot con `event_ts` anterior (llegada tardia).
    """
    emitted = _emitted(run_date)
    return copy.deepcopy([s for slot in sorted(emitted) for s in emitted[slot]])


def bookings_for_day(run_date: str) -> list:
    return [dict(b) for b in _bookings(run_date)]


def bookings_for_slot(run_date: str, slot: int) -> list:
    return [dict(b) for b in _bookings(run_date) if b["slot"] == slot]


def journeys_for_slot(run_date: str, slot: int) -> list:
    """Sesiones cuyo dia logico de emision es `run_date`, en `slot`, de reservas de
    `run_date` a `run_date`+6."""
    return copy.deepcopy(_emitted(run_date).get(slot, []))
