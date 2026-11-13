"""Handler Lambda del generador OTA.

Entrada de Lambda: `lambda_handler.handler`. Imports absolutos desde la raiz
del zip. boto3 solo se importa dentro del writer real.

Unica lectura de reloj: validar `to <= hoy-1` en backfill. Ningun byte
escrito depende del reloj.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

from ota.clickstream import generate
from ota.keys import SLOTS_PER_DAY, landing_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def slot_from_scheduled_time(scheduled_time: str) -> tuple:
    """Redondea hacia abajo a 15 min en UTC: devuelve (run_date, slot)."""
    if not isinstance(scheduled_time, str):
        raise ValueError("scheduled_time debe ser una cadena ISO 8601")
    text = scheduled_time.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        when = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"scheduled_time invalido: {scheduled_time!r}") from exc
    if when.tzinfo is None:
        raise ValueError("scheduled_time sin zona horaria")
    when = when.astimezone(timezone.utc)
    return when.strftime("%Y-%m-%d"), (when.hour * 60 + when.minute) // 15


def _parse_date(value, name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{name} debe ser YYYY-MM-DD")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{name} invalido: {value!r}") from exc


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


class S3Writer:
    """Writer real: boto3 se importa aqui, nunca al cargar el modulo."""

    def __init__(self, bucket: str):
        import boto3

        self._bucket = bucket
        self._client = boto3.client("s3")

    def __call__(self, key: str, body: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=body, ContentType="application/gzip"
        )


def _write_slot(run_date: str, slot: int, writer) -> dict:
    body = generate(run_date, slot)
    key = landing_key(run_date, slot)
    writer(key, body)
    logger.info(json.dumps({"run_date": run_date, "slot": slot, "key": key, "bytes": len(body)}))
    return {"key": key}


def _backfill(event: dict, writer, today_fn) -> dict:
    start = _parse_date(event.get("from"), "from")
    end = _parse_date(event.get("to"), "to")
    if start > end:
        raise ValueError("from debe ser <= to")
    if end > today_fn() - timedelta(days=1):
        raise ValueError("to debe ser <= hoy-1 (UTC)")
    logger.info(json.dumps({"backfill": "start", "from": str(start), "to": str(end)}))
    count = 0
    day = start
    while day <= end:
        for slot in range(SLOTS_PER_DAY):
            _write_slot(day.isoformat(), slot, writer)
            count += 1
        day += timedelta(days=1)
    logger.info(json.dumps({"backfill": "end", "from": str(start), "to": str(end), "objects": count}))
    return {"objects": count, "from": str(start), "to": str(end)}


def handler(event, context=None, *, writer=None, today_fn=None):
    if not isinstance(event, dict):
        raise ValueError("evento invalido")
    if writer is None:
        writer = S3Writer(os.environ["BUCKET_NAME"])
    if "scheduled_time" in event:
        run_date, slot = slot_from_scheduled_time(event["scheduled_time"])
        result = _write_slot(run_date, slot, writer)
        return {"objects": 1, **result}
    if "from" in event and "to" in event:
        return _backfill(event, writer, today_fn or _utc_today)
    raise ValueError("el evento debe traer scheduled_time o from/to")
