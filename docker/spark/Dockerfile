# Runtime local de Spark: mismas versiones que Glue 5.0 (Python 3.11, Java 17, PySpark 3.5.4).
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY spark/requirements.txt /app/spark/requirements.txt
RUN pip install --no-cache-dir -r /app/spark/requirements.txt

# El codigo se monta como volumen (compose.yml); PYTHONPATH permite `python -m jobs.bronze.ingest`.
ENV PYTHONPATH=/app/spark \
    AWS_REGION=eu-west-3 \
    AWS_DEFAULT_REGION=eu-west-3
