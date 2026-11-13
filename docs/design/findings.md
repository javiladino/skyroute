# Skyroute Marketing Lakehouse — Findings

Hechos duraderos que necesitan los topics posteriores. Un bloque por finding, solo se añade. Se carga solo cuando la tarea toca un tema de esta lista. Se divide en `findings/{tema}.md` al pasar de ~150 líneas.

## Credenciales: nada que corra en local puede escribir en AWS

- **Date:** 2026-11-13 · **Source topic:** `generator-landing`
- **Finding:** el único usuario humano (`skyroute-dev`) no tiene access keys (Convention Bootstrap identity), y la CI usa OIDC. Lo que corra en la máquina del owner (Airflow, Spark, export de Postgres) no tiene hoy credenciales de AWS. Es una decisión abierta en README § Open decisions.
- **Provenance:** `generator-landing/working/research.md` (T6) y Ruling Research decisions

## `landing/`: los datos se regeneran, no se conservan

- **Date:** 2026-11-13 · **Source topic:** `generator-landing`
- **Finding:** S3 cuenta los 30 días del lifecycle desde la creación del objeto, no desde la fecha de la clave. El histórico de `landing/` es regenerable: el generador es determinista por `(run_date, slot)`. Bronze tiene que ingerirlo antes de que caduque. El bucket de datos no tiene versioning.
- **Provenance:** `generator-landing/working/research/landing-s3.md` (H4) y Ruling Research decisions

## CI: `ci-apply` con trust en dev puede escribir el state de prod

- **Date:** 2026-11-13 · **Source topic:** `generator-landing`
- **Finding:** `ci_roles.tf:246-247` y `:270-285` (verificado). `dev` tiene `can_admins_bypass: true` (`gh api`). Se corrige en la Fase 2 separando `ci-apply-dev` y `ci-apply-prod`.
- **Provenance:** `generator-landing/working/research.md` (T17, Hecho (c))
