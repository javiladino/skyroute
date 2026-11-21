"""Columnas tecnicas de Bronze, derivadas solo de run_date y _source_file (nunca del reloj).

- _ingested_at = run_date 00:00 UTC + slot * 15 min (slot 0 en fuentes diarias).
- _batch_id = sha256(run_date|_source_file).
- _source_file = ruta del archivo desde `landing/`, sin esquema ni bucket.
- _ingest_date = run_date.
"""

from datetime import UTC, date, datetime

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

SLOT_MINUTES = 15
TECHNICAL_COLUMNS = ("_ingested_at", "_batch_id", "_source_file", "_ingest_date")


def day_start_epoch(run_date: str) -> int:
    day = date.fromisoformat(run_date)
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def add_technical_columns(df: DataFrame, run_date: str) -> DataFrame:
    source_file = F.regexp_extract(F.input_file_name(), r"(landing/.+)$", 1)
    slot = F.regexp_extract(F.col("_source_file"), r"slot=(\d+)", 1)
    slot = F.when(slot == "", F.lit(0)).otherwise(slot.cast("int"))
    base = F.lit(day_start_epoch(run_date))
    batch = F.sha2(F.concat_ws("|", F.lit(run_date), F.col("_source_file")), 256)
    return (
        df.withColumn("_source_file", source_file)
        .withColumn("_ingested_at", F.timestamp_seconds(base + slot * F.lit(SLOT_MINUTES * 60)))
        .withColumn("_batch_id", batch)
        .withColumn("_ingest_date", F.to_date(F.lit(run_date)))
    )
