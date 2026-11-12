# Skyroute Marketing Lakehouse — Contexto para agentes

> **Propósito:** orientar a cualquier agente que trabaje en este proyecto. Léelo primero y para en cuanto la tarea esté clara.
> **Last updated:** 2026-11-12

_Nota de idioma: la documentación está en español. Las cabeceras y etiquetas que lee `design_check.py` (Active Context, Conventions, Last updated, Current state, Status, Rulings, Journal, Document map, Open decisions) se dejan en inglés a propósito._

## Skills

Se cargan por tarea, no todas a la vez. Están en `.claude/skills/`.

| Skill | Cuándo cargarla |
|-------|-----------------|
| design-memory | Cualquier sesión que lea o escriba en `docs/design/`; cierre de sesión |
| reppit-research | Etapa 1 de RePPIT: documentar lo que existe para un topic |
| reppit-propose | Etapa 2: 2–3 propuestas revisadas; elige el owner |
| reppit-plan | Etapa 3: plan de implementación a partir de la propuesta elegida |
| reppit-implement | Etapa 4: ejecutar plan.md fase a fase |
| reppit-test | Etapa 5: verificar la implementación contra el plan |
| adversarial-review | Cuestionar un diff, un plan o un doc de diseño |
| grill-me | Entrevistas al owner, una pregunta cada vez |

## Active Context

**Orden de carga:** este archivo → `platform-blueprint/context.md` → los archivos que su document map marca `always` → solo los archivos que nombre la tarea. No cargues `CHANGELOG.md`, `evidence/`, `archive/` ni una carpeta entera salvo que la tarea nombre el archivo.
**Topics activos:** `platform-blueprint` (memoria de diseño montada; sin código ni infraestructura).

**Current state (2026-11-12):** Rama `main`. La memoria de diseño está montada: archivos de proyecto, topic `platform-blueprint` con la descripción de producto, y las Conventions del blueprint. No hay código, Terraform ni recursos AWS. Fase 1 sin empezar.

**Siguiente:** sesión 2: `AGENTS.md`, `CLAUDE.md`, README raíz, `.gitignore`, agentes (`adversarial-reviewer`) y hooks.
**Problemas conocidos:** no existe `.claude/agents/adversarial-reviewer.md`, que `reppit-propose` necesita.

## Conventions

Hogar único de las reglas de todo el proyecto. Los demás archivos las citan por nombre.

- **Table format (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** toda tabla del lakehouse es Apache Iceberg en S3, registrada en un único catálogo: AWS Glue Data Catalog.
- **Medallion layers (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** cuatro capas en este orden. `landing/`: archivos crudos tal cual, lifecycle de 30 días. Bronze: append-only, payload completo más `_ingested_at`, `_batch_id`, `_source_file`, `_ingest_date`. Silver: tipado, sin duplicados, claves estables. Gold: `dim_*`, `fct_*`, `mart_*` con definición de negocio acordada. Bases Glue `skyroute_{bronze,silver,gold,ops}`.
- **Compute split (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** Spark escribe Bronze y Silver; dbt sobre Athena construye Gold; ningún motor escribe en la capa del otro.
- **Orchestration runtime (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** Airflow 3 en Docker local (Astro CLI), DAGs con `airflow.sdk`; el código de DAG debe poder desplegarse en MWAA sin cambios, pero MWAA no se aprovisiona.
- **Region (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** todo recurso AWS, incluido el state de Terraform, va en `eu-west-3` (París).
- **No hourly-billed resources (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** prohibido cualquier recurso que cobre por hora estando inactivo (NAT Gateway, MWAA, Redshift, EMR siempre encendido); sin VPC privada. El cómputo Spark en AWS son jobs Glue 5 puntuales (Flex, 2 DPU).
- **IaC only (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** todo recurso AWS existe solo por Terraform (`infra/terraform/`, state remoto en S3 con `use_lockfile`); nada se crea a mano en consola ni por CLI. El primer recurso es un `aws_budgets_budget` de 10 USD con alertas al 50/80/100 %.
- **Apply gate (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** ningún agente ejecuta `terraform plan`, `terraform apply` ni comandos AWS; el owner corre `plan` él mismo; `apply` solo desde CI al fusionar (dev), y prod con aprobación manual.
- **Idempotency (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** cada tarea y job depende solo de la fecha lógica (`{{ ds }}` / `--run-date` / `var("run_date")`), nunca de `now()`, y escribe con MERGE o reemplazo de partición, nunca con append ciego (salvo Bronze, append-only por diseño): relanzar un día da el mismo resultado.
- **Reglas de un solo topic:** viven en `<topic>/context.md` § Rulings.
