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
| session-orchestration | Etapas RePPIT: el orquestador delega cada stage file a un subagente (topic `reppit-orchestration`) |

## Active Context

**Orden de carga:** este archivo → `<topic>/context.md` del topic activo → los archivos que su document map marca `always` → solo los archivos que nombre la tarea. No cargues `CHANGELOG.md`, `evidence/`, `archive/` ni una carpeta entera salvo que la tarea nombre el archivo.
**Topics activos:** `reppit-orchestration` (session-orchestration adoptada para RePPIT; falta la prueba de permisos de `stage-author` en segundo plano).

**Current state (2026-11-12):** Rama `main`, sin commit desde la sesión 3. Adoptada `session-orchestration` para las etapas RePPIT (topic `reppit-orchestration`): Conventions de escritura, roles de subagentes y verificación escritas; agentes `stage-author` y `executor` creados; todos los agentes con `model: inherit` (el modelo se fija en cada prompt de sesión); permisos de settings para subagentes en segundo plano. `platform-blueprint` y `agent-workflow` cerrados. No hay código, Terraform ni recursos AWS. Fase 1 sin empezar.

**Siguiente:** en una sesión nueva, prueba de `stage-author` en segundo plano escribiendo `reppit-orchestration/working/smoke.md`; commit; abrir el topic de la Fase 1 (Fundaciones).
**Problemas conocidos:** los agentes de `.claude/agents/` no están cargados en la sesión que los creó (`Agent type 'stage-author' not found`); hay que probarlos en una sesión nueva. Design write ownership se hace cumplir solo por prompt y por herramientas: el allow de `Edit` sobre `working/` no distingue agentes.

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
- **Design write ownership (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** La sesión principal (orquestador) es la única que escribe CONTEXT.md, README.md, CHANGELOG.md y findings.md, el context.md de cada topic, y la sección `## Decision` de proposal.md con la elección del owner; también es la única que mueve archivos entre working/, current/ y archive/. Cada stage file de working/ tiene un único autor: el subagente al que se le encargó en su brief.
- **Subagent roles (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** Investigadores y revisores (aws-researcher, terraform-researcher, cicd-researcher, security-reviewer, cost-guard, adversarial-reviewer) son de solo lectura y devuelven hallazgos como texto. Autores de stage files y ejecutores (implementación y tests) tienen escritura y solo pueden escribir en las rutas que fija su brief. Ningún subagente escribe en archivos del orquestador (Design write ownership) ni tiene la herramienta Agent.
- **AGENTS.md budget (en vigor 2026-11-12; owner javiladino; source agent-workflow):** `AGENTS.md` cabe en 150 líneas como máximo, en imperativo, y nombra cada Convention sin su veredicto; `CLAUDE.md` importa `@AGENTS.md` y añade solo lo específico de Claude Code.
- **Git workflow (en vigor 2026-11-12; owner javiladino; source agent-workflow):** ningún agente hace commit ni push sin que el owner lo pida; antes de cambiar código estando en `main`, crea una rama.
- **Skills location (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** Las skills viven en `.claude/skills/<name>/SKILL.md`. Todo brief usa esa ruta desde la raíz del repo, aunque una skill indique otra (p. ej. `skills/<name>/SKILL.md`).
- **Simple shell commands (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** Un comando simple por llamada de shell: sin `;`, `&&`, `|`, heredocs, `cd … &&` ni `git -C`. Para leer y buscar se usan Read, Grep y Glob. Si un comando es denegado, se pasa a la forma simple; nunca se reintenta igual.
- **Verification ownership (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** `executor` implementa y ejecuta las pruebas completas; el orquestador vuelve a ejecutar él mismo el verify command final de cada fase, y solo esa salida cuenta como evidencia en `test.md`. Lo que el Apply gate impide ejecutar se prueba con la salida que aporte el owner.
- **Reglas de un solo topic:** viven en `<topic>/context.md` § Rulings.
