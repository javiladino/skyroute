.PHONY: test-generators env seed-postgres

COMPOSE_PG = docker compose -f docker/postgres/compose.yml
SEED_FROM ?= 2026-01-01
SEED_TO ?= 2026-01-01

test-generators:
	pytest generators/tests -q

env:
	test -f .env || cp .env.example .env

seed-postgres: env
	PYTHONPATH=generators python3 -m ota.seed_postgres --from $(SEED_FROM) --to $(SEED_TO) | $(COMPOSE_PG) exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 -q
