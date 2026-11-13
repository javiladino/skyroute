"""Semilla determinista, ids estables y clave de objeto de landing/.

Solo stdlib. Nunca se usa hash() (varia por proceso) ni el reloj.
"""

import hashlib

SLOTS_PER_DAY = 96
CLICKSTREAM_PREFIX = "landing/clickstream"


def seed_for(run_date: str, slot: int, source: str) -> int:
    """Semilla sha256(f"{run_date}|{slot}|{source}") como entero."""
    digest = hashlib.sha256(f"{run_date}|{slot}|{source}".encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def _short(text: str, length: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def customer_id(n: int) -> str:
    return f"C{n:06d}"


def campaign_id(n: int) -> str:
    return f"CMP-{n:04d}"


def booking_id(run_date: str, j: int) -> str:
    return f"B{run_date.replace('-', '')}{j:04d}"


def session_id(run_date: str, slot: int, n: int) -> str:
    return "S" + _short(f"{run_date}|{slot}|{n}|session", 16)


def event_id(run_date: str, slot: int, n: int) -> str:
    return "E" + _short(f"{run_date}|{slot}|{n}|event", 20)


def email_for(cust_id: str) -> str:
    """Email sintetico u<sha256(customer_id)[:12]>@example.com."""
    return f"u{_short(cust_id, 12)}@example.com"


def landing_key(run_date: str, slot: int) -> str:
    """Clave del objeto de clickstream; la usan el generador y verify_landing."""
    if not 0 <= slot < SLOTS_PER_DAY:
        raise ValueError(f"slot fuera de rango: {slot}")
    return f"{CLICKSTREAM_PREFIX}/ingest_date={run_date}/slot={slot:02d}/part.json.gz"
