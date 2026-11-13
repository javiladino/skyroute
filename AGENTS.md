# AGENTS.md — Skyroute Marketing Lakehouse

Instrucciones para cualquier agente de código que trabaje en este repo. Léelas enteras antes de actuar.

## Qué es este repo

Proyecto de portfolio: un lakehouse de marketing en AWS (S3 + Iceberg + Glue Catalog, Spark, dbt sobre Athena, Airflow 3, Terraform) para una agencia de viajes ficticia. Descripción de producto: `docs/design/platform-blueprint/current/project/README.md`.

## Mapa del repo

Existe hoy:

| Ruta | Contenido |
|------|-----------|
| `docs/design/` | Raíz de diseño: memoria de largo plazo de los agentes (ver abajo) |
| `.claude/skills/` | Skills de método: `design-memory`, `reppit-*`, `adversarial-review`, `grill-me`, etc. |
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore` | Archivos raíz |

Previsto (aún no existe; no lo crees sin un plan aprobado):

| Ruta | Contenido |
|------|-----------|
| `infra/terraform/{bootstrap,modules,envs/{dev,prod}}/` | Infraestructura |
| `generators/` | Simulador OTA y handler Lambda |
| `spark/jobs/{bronze,silver,maintenance}/`, `spark/tests/` | Jobs PySpark y tests |
| `dbt/models/{staging,intermediate,marts}/`, `dbt/tests/`, `dbt/macros/` | Proyecto dbt |
| `airflow/dags/`, `airflow/include/` | Proyecto Astro CLI |
| `contracts/` | Data contracts YAML (ODCS) |
| `observability/` | docker-compose de Marquez y OpenMetadata |
| `docs/{adr,runbooks,postmortems}/` | ADRs, runbooks, post-mortems |
| `.github/workflows/` | CI |

## Reglas del proyecto

Las reglas del proyecto están en `docs/design/CONTEXT.md` § Conventions. Ese es su único hogar: léelas allí y no las copies a otro archivo. Las Conventions en vigor son:

- Table format
- Medallion layers
- Compute split
- Orchestration runtime
- Region
- No hourly-billed resources
- IaC only
- Apply gate
- Idempotency
- Design write ownership
- Subagent roles
- Skills location
- Simple shell commands
- Verification ownership
- AGENTS.md budget
- Git workflow
- Bootstrap identity

Las reglas de un solo topic están en `docs/design/<topic>/context.md` § Rulings.

Si una regla, una cifra o el alcance no coinciden entre dos archivos, para y pregunta al owner. No elijas una versión por tu cuenta.

## Raíz de diseño

La raíz de diseño es `docs/design/`. Se gestiona con la skill `design-memory`; cárgala en toda sesión que lea o escriba ahí.

- Archivos de proyecto: `CONTEXT.md` (estado actual y Conventions), `README.md` (fases, topics, decisiones abiertas), `CHANGELOG.md` (historia, solo se añade), `findings.md` (cuando exista).
- Cada topic es una carpeta `docs/design/<topic>/` con `context.md` y las carpetas `current/`, `working/`, `evidence/`, `archive/`, `assets/`.
- No edites ni borres nada en `evidence/` ni en `archive/`.
- No escribas prompts de traspaso en archivos. El traspaso a la siguiente sesión va en el chat (regla de la skill `design-memory`).

## Protocolo de carga

Lee en este orden y para en cuanto la tarea esté orientada:

1. **L0:** `docs/design/CONTEXT.md`.
2. **L1:** `docs/design/<topic>/context.md` del topic activo (rulings y document map).
3. **L2:** los archivos que el document map marca `always`.
4. **L3:** solo los archivos que nombre la tarea; `findings.md` solo si la tarea toca un tema que cubre.

No abras `CHANGELOG.md`, `evidence/` ni `archive/` salvo que la tarea nombre el archivo. No listes una carpeta de topic entera: lee su document map.

## Ciclo RePPIT

Todo trabajo de diseño o código no trivial sigue las cinco etapas, cada una con su skill. Cada etapa escribe su stage file en el topic:

| Etapa | Skill | Stage file |
|-------|-------|------------|
| Research | `reppit-research` | `docs/design/<topic>/working/research.md` |
| Propose | `reppit-propose` | `docs/design/<topic>/working/proposal.md` |
| Plan | `reppit-plan` | `docs/design/<topic>/working/plan.md` |
| Implement | `reppit-implement` | lee `working/plan.md`; cambia el código que lista. Implementer: `executor` |
| Test | `reppit-test` | `docs/design/<topic>/working/test.md` |

- Las etapas se ejecutan con la skill `session-orchestration`: los stage files los escribe `stage-author`, la implementación y los checks `executor`, y la review `adversarial-reviewer` (agentes en `.claude/agents/`).
- No pases a Plan hasta que el owner elija propuesta y quede en `proposal.md` § Decision.
- No pases de una etapa a la siguiente sin el visto bueno del owner.
- Al cerrar el ciclo, mueve el deliverable a `current/` y los drafts gastados a `archive/` (skill `design-memory`).

## Comandos de build y test

Todavía no hay código. Rellena estos comandos cuando exista cada componente:

```bash
# TODO: lint Python        (ruff …)
# TODO: tests Spark        (pytest spark/tests)
# TODO: dbt                (dbt build …)
terraform fmt -check -recursive infra/terraform
# validate: antes, terraform -chdir=infra/terraform/<root-module> init -backend=false
terraform -chdir=infra/terraform/<root-module> validate
# tflint: antes, tflint --init --config=infra/terraform/.tflint.hcl; nunca con --recursive
tflint --chdir=infra/terraform/<root-module> --config=$PWD/infra/terraform/.tflint.hcl
# checkov -d infra/terraform: corre solo en CI (job static-checks de terraform-plan.yml), no localmente
# TODO: contratos          (datacontract lint / test)
# TODO: entorno local      (make up)
```

## Cierre de sesión (obligatorio)

Toda sesión que haya escrito en `docs/design/` termina así, según la skill `design-memory`:

1. Triage de cada documento producido: keep (`current/`), in flight (`working/`), archive o discard.
2. Findings: si aprendiste un hecho que otro topic necesitará, añádelo a `findings.md` y actualiza su puntero en `CONTEXT.md`.
3. Actualiza el document map, el bloque Active Context y una entrada del `CHANGELOG.md`.
4. Ejecuta el checker y corrige cada `FAIL`:

   ```bash
   python3 .claude/skills/design-memory/scripts/design_check.py docs/design
   ```

5. Cita al owner la línea de resumen del script (`N FAIL, M WARN`). No des una sesión por cerrada sin ella.
