# Skyroute Marketing Lakehouse — Contexto para agentes

> **Propósito:** orientar a cualquier agente que trabaje en este proyecto. Léelo primero y para en cuanto la tarea esté clara.
> **Last updated:** 2026-11-14

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
**Topics activos:** `generator-landing` (Fase 2, Implement en curso: Fases 1-8 hechas; rama `infra/generator-landing-lambda-quota`).

**Current state (2026-11-14):** Fase 1 hecha: `foundations` cerrado (Done) y fusionado en `main` (PRs #2 y #3, con la aprobación manual de prod verificada en el run 43462639280). Fase 2 abierta: topic `generator-landing` con Research, Propose y Plan hechos e Implement en curso. Las Fases 1-8 del plan están hechas (PRs #7-#13 y los re-applies de bootstrap del owner). El owner eligió la Propuesta 1 y aprobó el plan (Rulings Research decisions, Propose decisions y Plan decisions). El Ruling Implement decisions deja en suspenso la concurrencia reservada, porque la cuota de Lambda es 10. Apply gate aclarada: el owner re-aplica `bootstrap/` en cada cambio. En AWS existen, creados por Terraform, el budget de 10 USD, el bucket de state en eu-west-3, el proveedor OIDC, los roles `ci-plan`, `ci-apply-dev` y `ci-apply-prod`, las boundaries `ci-boundary` y `workload-boundary-{dev,prod}`, y el bloqueo de acceso público de S3 de la cuenta. `ci-apply` se destruyó en la Fase 8. La PR publica el plan y el merge aplica en dev y prod, con aprobación manual en `prod`. El código está en `main` (PR #1). Las etapas RePPIT se ejecutan con `session-orchestration` (Conventions Design write ownership, Subagent roles y Verification ownership). `platform-blueprint`, `agent-workflow`, `reppit-orchestration` y `foundations` están cerrados.

**Siguiente:** subida de cuota de Lambda en `bootstrap/` (re-apply del owner). Después la Fase 9 (módulo y entornos, PR-M) sin concurrencia reservada, la Fase 10 (backfill, del owner) y la PR-Q cuando AWS apruebe la cuota. El plan Free vence el 2027-01-22: el paso a Paid queda como decisión abierta en el README.
**Problemas conocidos:** Design write ownership se hace cumplir solo por prompt y por herramientas: el allow de `Edit` sobre `working/` no distingue agentes. T17 (`ci-apply` con trust en dev podía escribir el state de prod) quedó cerrada el 2026-11-14 al destruir `ci-apply` (Fase 8).
**Findings:** `findings.md`, 3 entradas, la última del 2026-11-13.

## Conventions

Hogar único de las reglas de todo el proyecto. Los demás archivos las citan por nombre.

- **Table format (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** toda tabla del lakehouse es Apache Iceberg en S3, registrada en un único catálogo: AWS Glue Data Catalog.
- **Medallion layers (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** cuatro capas en este orden. `landing/`: archivos crudos tal cual, lifecycle de 30 días. Bronze: append-only, payload completo más `_ingested_at`, `_batch_id`, `_source_file`, `_ingest_date`. Silver: tipado, sin duplicados, claves estables. Gold: `dim_*`, `fct_*`, `mart_*` con definición de negocio acordada. Bases Glue `skyroute_{bronze,silver,gold,ops}`.
- **Compute split (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** Spark escribe Bronze y Silver; dbt sobre Athena construye Gold; ningún motor escribe en la capa del otro.
- **Orchestration runtime (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** Airflow 3 en Docker local (Astro CLI), DAGs con `airflow.sdk`; el código de DAG debe poder desplegarse en MWAA sin cambios, pero MWAA no se aprovisiona.
- **Region (en vigor 2026-11-12; owner javiladino; source platform-blueprint, aclarada en foundations):** todo recurso AWS regional, incluido el state de Terraform, va en `eu-west-3` (París); los servicios globales sin región (IAM, Budgets, Organizations) quedan exentos. El provider de Terraform se configura siempre con `region = "eu-west-3"`.
- **No hourly-billed resources (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** prohibido cualquier recurso que cobre por hora estando inactivo (NAT Gateway, MWAA, Redshift, EMR siempre encendido); sin VPC privada. El cómputo Spark en AWS son jobs Glue 5 puntuales (Flex, 2 DPU).
- **IaC only (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** todo recurso AWS existe solo por Terraform (`infra/terraform/`, state remoto en S3 con `use_lockfile`); nada se crea a mano en consola ni por CLI, salvo los recursos previos al bootstrap que fija Apply gate. El primer recurso es un `aws_budgets_budget` de 10 USD con alertas al 50/80/100 %.
- **Apply gate (en vigor 2026-11-12; owner javiladino; source platform-blueprint, aclarada en foundations y en generator-landing 2026-11-13):** ningún agente de código (Claude y sus subagentes) ejecuta `terraform plan`, `terraform apply` ni comandos AWS. GitHub Actions no es un agente: corre `plan` en cada PR y lo publica como comentario; el owner puede correr `plan` en local. `apply` solo desde CI al fusionar (dev), y prod con aprobación manual en un environment con revisor obligatorio. Excepción única: el owner aplica `infra/terraform/bootstrap/` desde su máquina: la primera vez con state local migrado después al bucket de state, y cada cambio posterior (permisos de CI, boundaries) con el state remoto y su plan como evidencia; la CI nunca aplica bootstrap. Ese bootstrap crea el budget, el bucket de state, el proveedor OIDC y los roles de CI. Única excepción a IaC only, los recursos creados a mano antes del bootstrap: el usuario IAM del owner (con MFA, creado en consola con root y MFA), su grupo y su pertenencia al grupo, que el bootstrap importa a Terraform; el budget manual, que queda como red de seguridad hasta que exista el de Terraform; y el bucket manual `skyroute-tfstate-demo-437266392155-eu-north-1-an` (en eu-north-1, fuera de Region, vacío), que no se adopta. El owner borra los dos últimos después del bootstrap (paso del runbook).
- **Idempotency (en vigor 2026-11-12; owner javiladino; source platform-blueprint):** cada tarea y job depende solo de la fecha lógica (`{{ ds }}` / `--run-date` / `var("run_date")`), nunca de `now()`, y escribe con MERGE o reemplazo de partición, nunca con append ciego (salvo Bronze, append-only por diseño): relanzar un día da el mismo resultado.
- **Design write ownership (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** La sesión principal (orquestador) es la única que escribe CONTEXT.md, README.md, CHANGELOG.md y findings.md, el context.md de cada topic, y la sección `## Decision` de proposal.md con la elección del owner; también es la única que mueve archivos entre working/, current/ y archive/. Cada stage file de working/ tiene un único autor: el subagente al que se le encargó en su brief.
- **Subagent roles (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** Investigadores y revisores (aws-researcher, terraform-researcher, cicd-researcher, security-reviewer, cost-guard, adversarial-reviewer) son de solo lectura y devuelven hallazgos como texto. Autores de stage files y ejecutores (implementación y tests) tienen escritura y solo pueden escribir en las rutas que fija su brief. Ningún subagente escribe en archivos del orquestador (Design write ownership) ni tiene la herramienta Agent.
- **AGENTS.md budget (en vigor 2026-11-12; owner javiladino; source agent-workflow):** `AGENTS.md` cabe en 150 líneas como máximo, en imperativo, y nombra cada Convention sin su veredicto; `CLAUDE.md` importa `@AGENTS.md` y añade solo lo específico de Claude Code.
- **Git workflow (en vigor 2026-11-12; owner javiladino; source agent-workflow):** ningún agente hace commit ni push sin que el owner lo pida; antes de cambiar código estando en `main`, crea una rama.
- **Skills location (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** Las skills viven en `.claude/skills/<name>/SKILL.md`. Todo brief usa esa ruta desde la raíz del repo, aunque una skill indique otra (p. ej. `skills/<name>/SKILL.md`).
- **Simple shell commands (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** Un comando simple por llamada de shell: sin `;`, `&&`, `|`, heredocs, `cd … &&` ni `git -C`. Para leer y buscar se usan Read, Grep y Glob. Si un comando es denegado, se pasa a la forma simple; nunca se reintenta igual.
- **Verification ownership (en vigor 2026-11-12; owner javiladino; source reppit-orchestration):** `executor` implementa y ejecuta las pruebas completas; el orquestador vuelve a ejecutar él mismo el verify command final de cada fase, y solo esa salida cuenta como evidencia en `test.md`. Lo que el Apply gate impide ejecutar se prueba con la salida que aporte el owner.
- **Bootstrap identity (en vigor 2026-11-13; owner javiladino; source foundations):** el usuario IAM `skyroute-dev` (grupo `admins` con `AdministratorAccess`, consola con MFA, sin access keys) es la identidad humana de arranque. No se usa Identity Center porque la cuenta sigue en plan Free (Ruling Foundations design). Es un riesgo aceptado: checkov CKV_AWS_273 y CKV_AWS_274 se omiten solo en esos dos recursos de `bootstrap/owner_user.tf`, nunca en todo el repo. El mínimo privilegio se exige a los roles de CI y a toda identidad no humana.
- **Reglas de un solo topic:** viven en `<topic>/context.md` § Rulings.
