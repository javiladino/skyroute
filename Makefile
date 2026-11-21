.PHONY: test-generators test-spark env seed-postgres export-bookings fx

COMPOSE_PG = docker compose -f docker/postgres/compose.yml
PY = .venv/bin/python
SEED_FROM ?= 2026-01-01
SEED_TO ?= 2026-01-01
RUN_DATE ?= 2026-01-01
OUT_DIR ?= build
# REBUILD=1 vacia las tablas antes de cargar; history_id (serial) solo es reproducible asi.
REBUILD ?=
REBUILD_FLAG = $(if $(REBUILD),--rebuild,)

test-generators:
	$(PY) -m pytest generators/tests -q

test-spark:
	$(PY) -m pytest spark/tests -q

env:
	test -f .env || cp .env.example .env

seed-postgres: env
	PYTHONPATH=generators $(PY) -m ota.seed_postgres --from $(SEED_FROM) --to $(SEED_TO) $(REBUILD_FLAG) | $(COMPOSE_PG) exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 -q

export-bookings:
	PYTHONPATH=generators $(PY) -m ota.export_bookings --run-date $(RUN_DATE) --out-dir $(OUT_DIR)

fx:
	PYTHONPATH=generators $(PY) -m fx.ecb --run-date $(RUN_DATE) --out-dir $(OUT_DIR)
