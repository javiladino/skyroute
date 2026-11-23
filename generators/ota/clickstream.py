"""Generador de clickstream: (run_date, slot) -> bytes JSON lines gzip.

Determinista: solo la semilla de keys.seed_for decide; nunca el reloj.
Duplicados y eventos tardios (hasta 72 h) tambien salen de la semilla.
"""

import gzip
import json
import random
from datetime import timedelta

from ota import model
from ota.keys import (
    SLOTS_PER_DAY,
    customer_id,
    email_for,
    event_id,
    seed_for,
    session_id,
)

MAX_LATE_SECONDS = 72 * 3600
LATE_PROBABILITY = 0.05
DUPLICATE_PROBABILITY = 0.03
JOURNEY_ID_BASE = 2000
JOURNEY_ID_STRIDE = 100  # pasos por sesion de recorrido: n < 100
FUNNEL_RANK = {step: i for i, step in enumerate(model.FUNNEL_STEPS)}


def journey_event_n(j: int, k: int) -> int:
    """Rango `n` de `event_id` del paso `k` del recorrido `j`: 2000 + j*100 + k, con k < 100.

    `j` efectivo: `offset * BOOKINGS_PER_DAY + j_reserva` (offset 0..6 = dias entre el run_date
    y la reserva). Una reserva solo tiene `j` unico dentro de su dia, pero el generador del
    dia X emite sesiones de reservas de X a X+6 en el mismo slot; sin `offset` dos reservas
    con el mismo indice colisionarian en `event_id`.
    """
    if not 0 <= k < JOURNEY_ID_STRIDE:
        raise ValueError(f"paso de recorrido fuera de rango: {k!r} (max {JOURNEY_ID_STRIDE - 1})")
    return JOURNEY_ID_BASE + j * JOURNEY_ID_STRIDE + k


def journey_events(run_date: str, slot: int, journey: dict) -> list:
    """Eventos de una sesion de recorrido, con su `event_id` en el rango reservado."""
    if len(journey["events"]) > JOURNEY_ID_STRIDE:
        raise ValueError(f"recorrido de {len(journey['events'])} pasos: maximo {JOURNEY_ID_STRIDE}")
    return [
        {
            "event_id": event_id(run_date, slot, journey_event_n(journey["j"], step["n"])),
            **{k: v for k, v in step.items() if k != "n"},
        }
        for step in journey["events"]
    ]


def _validate(run_date: str, slot: int) -> None:
    model.parse_day(run_date)
    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < SLOTS_PER_DAY:
        raise ValueError(f"slot fuera de rango: {slot!r}")


def _order_funnel_types(group: list) -> None:
    """Reasigna los tipos `search`/`product_view` de una sesion de fondo para que, por
    (`event_ts`, `event_id`), `search` no vaya despues de `product_view`: el fondo no invierte
    el funnel."""
    funnel = [e for e in group if e["event_type"] in FUNNEL_RANK]
    types = sorted((e["event_type"] for e in funnel), key=FUNNEL_RANK.get)
    in_order = sorted(funnel, key=lambda e: (e["event_ts"], e["event_id"]))
    for event, etype in zip(in_order, types, strict=True):
        event["event_type"] = etype


def build_events(run_date: str, slot: int) -> list:
    _validate(run_date, slot)
    rng = random.Random(seed_for(run_date, slot, "clickstream"))
    base = model.parse_day(run_date) + timedelta(minutes=15 * slot)
    events = []
    total = rng.randint(25, 45)
    i = 0
    while i < total:
        # Sesion de navegacion: 2 a 5 eventos del mismo cliente en el slot (< 15 min). Los
        # eventos de recorrido de una reserva (model.customer_journeys) pueden caer hasta
        # 80 min antes de created_at, fuera del slot y en D-1.
        group = min(rng.randint(2, 5), total - i)
        customer_n = rng.randint(1, model.CUSTOMER_POOL)
        campaign_idx = rng.randrange(len(model.CAMPAIGNS))
        cust = customer_id(customer_n)
        sess = session_id(run_date, slot, i)
        first = len(events)
        for _ in range(group):
            etype = rng.choices(model.BACKGROUND_EVENT_TYPES,
                                weights=model.BACKGROUND_EVENT_WEIGHTS)[0]
            offset = rng.randrange(900)
            late = rng.random() < LATE_PROBABILITY
            late_shift = rng.randint(1, MAX_LATE_SECONDS)
            price = round(rng.uniform(40, 1500), 2)
            ts = base + timedelta(seconds=offset)
            if late:
                ts -= timedelta(seconds=late_shift)
            event = {
                "event_id": event_id(run_date, slot, i),
                "event_type": etype,
                "event_ts": model.fmt_ts(ts),
                "customer_id": cust,
                "session_id": sess,
                "campaign_id": f"CMP-{model.campaign_n_for(campaign_idx):04d}",
                "currency": model.currency_for(customer_n),
                "amount": price if etype == "add_to_cart" else None,
                "consent_ts": model.consent_ts_for(customer_n),
            }
            if etype == "consent":
                event["email"] = email_for(cust)
            events.append(event)
            i += 1
        _order_funnel_types(events[first:])

    # Recorridos: eventos previos de la sesion de cada reserva, y despues su purchase.
    for journey in model.journeys_for_slot(run_date, slot):
        events.extend(journey_events(run_date, slot, journey))

    for j, booking in enumerate(model.bookings_for_slot(run_date, slot)):
        events.append({
            "event_id": event_id(run_date, slot, 1000 + j),
            "event_type": "purchase",
            "event_ts": booking["created_at"],
            "customer_id": booking["customer_id"],
            "session_id": booking["session_id"],
            "campaign_id": booking["campaign_id"],
            "booking_id": booking["booking_id"],
            "currency": booking["currency"],
            "amount": booking["amount"],
            "consent_ts": model.consent_ts_for(int(booking["customer_id"][1:])),
        })

    dup_rng = random.Random(seed_for(run_date, slot, "duplicates"))
    duplicates = [dict(e) for e in events if dup_rng.random() < DUPLICATE_PROBABILITY]
    return events + duplicates


def generate(run_date: str, slot: int) -> bytes:
    events = build_events(run_date, slot)
    text = "".join(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n" for e in events)
    return gzip.compress(text.encode("utf-8"), compresslevel=6, mtime=0)
