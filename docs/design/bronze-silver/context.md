# bronze-silver — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 3 — Bronze y Silver con Spark + Iceberg (README § Fases): "Jobs PySpark con tests, MERGE, sesionización, SCD2, conversión de divisas. Hecho cuando relanzar un día da exactamente el mismo resultado." Entrada: el clickstream en `landing/` y las Reservas en Postgres local de `generator-landing` (Fase 2, pendiente solo del backfill del día D). Restricciones: Conventions Table format, Medallion layers, Compute split, Region, No hourly-billed resources, IaC only, Apply gate e Idempotency. Decisiones abiertas del README que tocan esta fase: dónde corre Spark, modo de escritura Iceberg por tabla, motor de checks WAP y credenciales de AWS para lo que corre en local. Rama: `docs/bronze-silver-research` (sale de `docs/generator-landing-test`). Etapa en curso: Research.

## Rulings

_Sin rulings todavía._

## Journal (newest first)

**2026-11-19 (Research):** stage-author (Opus) escribió `working/research.md`. Revisión en paralelo: adversarial-reviewer (Opus, GO-WITH-FIXES, 14 hallazgos), security-reviewer (Opus, 7) y cost-guard (Sonnet, 7). executor (Sonnet) ejecutó los checks locales: `.env.example` existe y está versionado (el hallazgo contrario de security era erróneo, lo confirmó el orquestador); pytest no está instalado. Un stage-author (Opus) aplicó los hallazgos: 14 tensiones (T1-T14) y una sección "No comprobado" con los checks de AWS, que son del owner. Siguiente: gate del owner y grill-me antes de Propose.

**2026-11-14:** Topic abierto (scaffold) y Research lanzado con `session-orchestration` (Opus para el documento consolidado y los revisores profundos, Sonnet para notas de área, cost-guard y executor).

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | What it holds |
|------|------|------|---------------|
| `working/research.md` | draft | on-demand | Research de la Fase 3: lo que existe hoy para Bronze y Silver (C1–C6, T1–T14, revisado y corregido) |
