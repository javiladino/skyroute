"""Esquemas explicitos de landing por fuente, derivados de lo que escriben los generadores.

El payload se conserva tal cual lo escribe el generador: marcas de tiempo como texto ISO
(`YYYY-MM-DDTHH:MM:SSZ`) e importes como DoubleType (el JSON lleva `float`; un entero como 10
tambien se lee bien). Todos los campos son anulables: un dia puede traer un campo ausente o
nulo y el siguiente con valor sin que cambie la tabla. Un campo nuevo en landing que no este
aqui se ignora al leer; ampliar el esquema es un cambio deliberado de este archivo.

Fuentes (generators/):
- clickstream: ota/clickstream.py (+ ota/model.py customer_journeys). `email` solo en eventos
  `consent`; `booking_id` solo en `purchase`; `amount` es null salvo add_to_cart y purchase.
- bookings: ota/export_bookings.py FIELDS (bookings_history; history_id entero).
- fx: fx/ecb.py build_payload (una fila por divisa y dia calendario).
- ad_spend: ota/ad_spend.py build_rows (una fila por campana y dia; spend en EUR).
"""

from pyspark.sql.types import DoubleType, LongType, StringType, StructField, StructType


def _struct(*fields: tuple) -> StructType:
    return StructType([StructField(name, dtype, True) for name, dtype in fields])


CLICKSTREAM_SCHEMA = _struct(
    ("event_id", StringType()),
    ("event_type", StringType()),
    ("event_ts", StringType()),
    ("customer_id", StringType()),
    ("session_id", StringType()),
    ("campaign_id", StringType()),
    ("currency", StringType()),
    ("amount", DoubleType()),
    ("consent_ts", StringType()),
    ("email", StringType()),
    ("booking_id", StringType()),
)

BOOKINGS_SCHEMA = _struct(
    ("history_id", LongType()),
    ("booking_id", StringType()),
    ("customer_id", StringType()),
    ("session_id", StringType()),
    ("campaign_id", StringType()),
    ("origin", StringType()),
    ("destination", StringType()),
    ("travel_date", StringType()),
    ("status", StringType()),
    ("currency", StringType()),
    ("amount", DoubleType()),
    ("created_at", StringType()),
    ("updated_at", StringType()),
    ("changed_at", StringType()),
)

FX_SCHEMA = _struct(
    ("base", StringType()),
    ("currency", StringType()),
    ("rate", DoubleType()),
    ("rate_date", StringType()),
    ("fx_date", StringType()),
)

AD_SPEND_SCHEMA = _struct(
    ("spend_date", StringType()),
    ("campaign_id", StringType()),
    ("spend", DoubleType()),
    ("currency", StringType()),
    ("impressions", LongType()),
    ("clicks", LongType()),
)

SCHEMAS = {
    "clickstream": CLICKSTREAM_SCHEMA,
    "bookings": BOOKINGS_SCHEMA,
    "fx": FX_SCHEMA,
    "ad_spend": AD_SPEND_SCHEMA,
}
