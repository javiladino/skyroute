"""Generador de clickstream: (run_date, slot) -> bytes JSON lines gzip.

Determinista: solo la semilla de keys.seed_for decide; nunca el reloj.
Duplicados y eventos tardios (hasta 72 h) tambien salen de la semilla.
"""

import gzip
import json
import random
from datetime import timedelta

from ota import model
from ota.keys import SLOTS_PER_DAY, customer_id, email_for, event_id, seed_for, session_id

MAX_LATE_SECONDS = 72 * 3600
LATE_PROBABILITY = 0.05
DUPLICATE_PROBABILITY = 0.03


def _validate(run_date: str, slot: int) -> None:
    model.parse_day(run_date)
    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < SLOTS_PER_DAY:
        raise ValueError(f"slot fuera de rango: {slot!r}")


def build_events(run_date: str, slot: int) -> list:
    _validate(run_date, slot)
    rng = random.Random(seed_for(run_date, slot, "clickstream"))
    base = model.parse_day(run_date) + timedelta(minutes=15 * slot)
    events = []
    for i in range(rng.randint(25, 45)):
        etype = rng.choices(model.EVENT_TYPES, weights=model.EVENT_WEIGHTS)[0]
        customer_n = rng.randint(1, model.CUSTOMER_POOL)
        campaign_idx = rng.randrange(len(model.CAMPAIGNS))
        offset = rng.randrange(900)
        late = rng.random() < LATE_PROBABILITY
        late_shift = rng.randint(1, MAX_LATE_SECONDS)
        price = round(rng.uniform(40, 1500), 2)
        ts = base + timedelta(seconds=offset)
        if late:
            ts -= timedelta(seconds=late_shift)
        cust = customer_id(customer_n)
        event = {
            "event_id": event_id(run_date, slot, i),
            "event_type": etype,
            "event_ts": model.fmt_ts(ts),
            "customer_id": cust,
            "session_id": session_id(run_date, slot, i),
            "campaign_id": f"CMP-{model.campaign_n_for(campaign_idx):04d}",
            "currency": model.currency_for(customer_n),
            "amount": price if etype == "add_to_cart" else None,
            "consent_ts": model.consent_ts_for(customer_n),
        }
        if etype == "consent":
            event["email"] = email_for(cust)
        events.append(event)

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
