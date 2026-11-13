# Skyroute Marketing Lakehouse

**Owner:** javiladino
**Tracker:** ninguno
**Status:** Fase 1 hecha (2026-11-13): bootstrap de Terraform, state remoto en S3, roles OIDC de CI y plan/apply en GitHub Actions; Fase 2 sin empezar.

## Resumen

Proyecto de portfolio para un puesto de Data Engineer Senior: una plataforma de datos de marketing para una agencia de viajes online ficticia, Skyroute. Ingiere clickstream, reservas, gasto publicitario, CRM y tipos de cambio; los refina en una arquitectura Medallion sobre Apache Iceberg en S3; y entrega productos de datos con contrato (ROAS, CAC, atribución, funnel, RFM) a los Product Owners de marketing. Se construye con Terraform, Spark, dbt sobre Athena y Airflow 3, y se opera como en producción. Descripción de producto: [`platform-blueprint/current/project/README.md`](platform-blueprint/current/project/README.md).

## Fases

| Fase | Resultado (hecho cuando…) | Estado |
|------|---------------------------|--------|
| **1** — Fundaciones | Cuenta AWS con MFA y usuario no root, presupuesto, repo, bootstrap de Terraform (state, rol OIDC), CI básica. Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica. | Done 2026-11-13 ([`foundations`](foundations/context.md); PR #1) |
| **2** — Generador y landing | Simulador OTA coherente, Lambda + EventBridge, Postgres local, archivos en `landing/`. Hecho cuando hay 6 meses de histórico y llegan micro-lotes nuevos. | Planned - no topic |
| **3** — Bronze y Silver con Spark + Iceberg | Jobs PySpark con tests, MERGE, sesionización, SCD2, conversión de divisas. Hecho cuando relanzar un día da exactamente el mismo resultado. | Planned - no topic |
| **4** — Gold con dbt | Staging, modelo dimensional, atribución en tres modelos, ROAS, funnel, RFM, tests, contratos, exposures, docs. Hecho cuando el glosario de KPIs coincide con el SQL. | Planned - no topic |
| **5** — Orquestación end to end | DAG diario, Cosmos para dbt, sensores, reintentos, backfill de 90 días, DAG semanal de mantenimiento Iceberg. Hecho cuando un backfill completo termina sin intervención. | Planned - no topic |
| **6** — Calidad y observabilidad | WAP con ramas Iceberg, Elementary, tabla `ops.dq_results`, alertas SNS, métricas de coste. Hecho cuando un dato malo nunca llega a `main`. | Planned - no topic |
| **7** — Gobierno | Contratos ODCS en CI, Marquez con lineage de punta a punta, OpenMetadata, Lake Formation con columnas PII ocultas. Hecho cuando el impacto de un fallo se enseña en 2 clics. | Planned - no topic |
| **8** — RUN y presentación | Seis game days, dos o tres post-mortems, runbooks, README con diagrama, vídeo de demo de 5 min. Hecho cuando alguien externo levanta el proyecto con el README. | Planned - no topic |

## Topics

| Topic | Título | Status |
|-------|--------|--------|
| [`platform-blueprint`](platform-blueprint/context.md) | Blueprint de la plataforma y descripción de producto | Done |
| [`agent-workflow`](agent-workflow/context.md) | Archivos raíz, agentes y hooks para trabajar con agentes | Done |
| [`reppit-orchestration`](reppit-orchestration/context.md) | Etapas RePPIT con session-orchestration: roles, agentes y permisos | Done |
| [`foundations`](foundations/context.md) | Fase 1 — Fundaciones: cuenta, presupuesto, bootstrap de Terraform, OIDC y CI | Done |

## Documentos

| Topic | Documento | Ruta |
|-------|-----------|------|
| — | Contexto para agentes | [CONTEXT.md](CONTEXT.md) |
| — | Changelog | [CHANGELOG.md](CHANGELOG.md) |
| platform-blueprint | Descripción de producto (deliverable) | [README.md](platform-blueprint/current/project/README.md) |
| agent-workflow | Instrucciones para agentes | [AGENTS.md](../../AGENTS.md) |
| agent-workflow | Específico de Claude Code | [CLAUDE.md](../../CLAUDE.md) |
| agent-workflow | README raíz | [README.md](../../README.md) |
| agent-workflow, reppit-orchestration | Agentes (9) | [.claude/agents/](../../.claude/agents/) |
| agent-workflow | Permisos y hooks | [settings.json](../../.claude/settings.json) |
| platform-blueprint | Blueprint original (evidencia) | [skyroute-blueprint.html](platform-blueprint/evidence/skyroute-blueprint.html) |

## Open decisions

| Decisión | Opciones | Estado |
|----------|----------|--------|
| Plan de cuenta AWS (créditos Free Tier desde julio 2025) | Plan Free (cierra a los 6 meses o al agotar créditos) / Plan Paid con presupuesto y alertas | Decided 2026-11-12: Free, Paid aplazado (Ruling Foundations design en [`foundations`](foundations/context.md)) |
| Dónde corre Spark en las ejecuciones diarias | Spark local en Docker / AWS Glue 5 para todo / local + Glue solo en demos | Proposed |
| Motor de checks de calidad en la rama WAP de Silver | PySpark checks propios / Soda Core | Proposed |
| Modo de escritura Iceberg por tabla | Copy-on-write / merge-on-read (el blueprint sugiere MoR en Silver bookings y CoW en Gold, a justificar por ratio lecturas/escrituras) | Proposed |
| Herramienta de dashboard de marketing | Streamlit / Evidence | Proposed |

_Estados: **Proposed** (opciones listadas, nada elegido) · **Accepted** (elegida; la razón va al CHANGELOG) · **Deprecated** · **Superseded**._
