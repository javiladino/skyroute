# Skyroute Marketing Lakehouse Changelog

Newest first. One `##` heading per day with activity. Write outcomes, not implementation steps. This file is appended to, never rewritten, and is not loaded by default.

## 2026-11-12

### platform-blueprint — Sesión 1: base de la memoria de diseño
- Scaffold de `docs/design/` (CONTEXT, README, CHANGELOG) y del topic `platform-blueprint`; documentación en español.
- Nueve Conventions de proyecto extraídas del blueprint y aprobadas por el owner (Table format, Medallion layers, Compute split, Orchestration runtime, Region, No hourly-billed resources, IaC only, Apply gate, Idempotency). Apply gate: el owner corre `terraform plan` él mismo.
- README de diseño con las 8 fases del blueprint (sin topics) y 5 decisiones abiertas.
- Deliverable `platform-blueprint/current/project/README.md` (descripción de producto).
- Quitados del índice los `.DS_Store` versionados; `.gitignore` queda para la sesión 2.
- Falta `.claude/agents/adversarial-reviewer.md` (lo necesita reppit-propose); se crea en la sesión 2.

### Files (skyroute, rama main)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md` (new)
- `docs/design/platform-blueprint/context.md`, `current/project/README.md` (new)
- `.DS_Store` ×5 (deleted)

### agent-workflow — Sesión 2: archivos raíz del repo
- Nuevo topic `agent-workflow` (cubre esta sesión y la siguiente).
- Dos Conventions nuevas aprobadas por el owner: Single design writer y Read-only subagents (con excepción para los implementers de `reppit-implement`). Ruling del topic: AGENTS.md budget. Los traspasos en el chat se quedan como regla de la skill `design-memory`, sin ruling.
- Escritos `AGENTS.md` (120 líneas), `CLAUDE.md`, `README.md` raíz y `.gitignore`; `docs/design/` sigue versionado entero.

### Files (skyroute, rama main, sin commit)
- `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore` (new)
- `docs/design/agent-workflow/context.md` (new)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md` (modified)

### agent-workflow — Sesión 3: agentes, permisos y hooks; topic cerrado
- Promoted ruling "AGENTS.md budget" from agent-workflow to Conventions.
- Nueva Convention "Git workflow" (antes solo en `AGENTS.md` § Git, que se quita).
- Agentes en `.claude/agents/`: `infra-lead` (sesión principal), `adversarial-reviewer` (sin Bash) y cinco subagentes de solo lectura (`aws-researcher`, `terraform-researcher`, `security-reviewer`, `cost-guard`, `cicd-researcher`). Sin implementer con nombre: `reppit-implement` no lo espera.
- La doc oficial dice que los subagentes pueden anidar por defecto (hasta 3 niveles): se fija `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` y ningún subagente tiene la herramienta Agent; `CLAUDE.md` corregido.
- `.claude/settings.json`: deny de `terraform plan/apply/destroy/import/state` (también con `-chdir`), `aws` y lectura de `.env*` y `*.tfvars`; ask para commit/push; allow de fmt/validate/tflint/checkov, git de lectura y `design_check.py`. Hooks Stop (`design-check-on-stop.sh`) y PostToolUse (`terraform-fmt.sh`).
- `session-orchestration` no se usa en el proyecto (choca con Single design writer).
- Pruebas: `aws --version` denegado; Stop hook silencioso con 0 FAIL y bloqueante en una copia con un FAIL.

### Files (skyroute, rama main, sin commit)
- `.claude/agents/*.md` ×7, `.claude/settings.json`, `.claude/hooks/terraform-fmt.sh` (new)
- `AGENTS.md`, `CLAUDE.md` (modified)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `agent-workflow/context.md` (modified)

### reppit-orchestration — Adopción de session-orchestration para RePPIT
- Decisión del owner: las etapas RePPIT se ejecutan con `session-orchestration`. Va en el topic nuevo `reppit-orchestration`; `agent-workflow` sigue cerrado.
- Ruling reversal: "Single design writer" (solo el agente principal escribe en `docs/design/`) → "Design write ownership" (el orquestador escribe los archivos de proyecto, los context.md, `## Decision` y los movimientos entre carpetas; cada stage file tiene como autor al subagente de su brief).
- Ruling reversal: "Read-only subagents" (solo lectura salvo implementers) → "Subagent roles" (investigadores y revisores de solo lectura; autores y ejecutores escriben solo en las rutas de su brief; ninguno tiene Agent).
- Nuevas Conventions: "Skills location" y "Simple shell commands". `AGENTS.md` nombra 15 Conventions (120 líneas, dentro de AGENTS.md budget).
- Agentes: nuevos `stage-author` y `executor` (implementer de `reppit-implement`); `infra-lead` pasa al contrato de orquestador; "Reviewer sin Bash" actualizada (lo no comprobado lo ejecuta `executor`); todos los agentes en Sonnet 5.5.
- `settings.json`: allow de `WebSearch`, `WebFetch` por dominio de documentación oficial, `Edit(/docs/design/*/working/**)`, `pytest` y `ruff`. Los deny del Apply gate no cambian y tienen precedencia.
- Abierta: quién ejecuta la verificación (choque de `reppit-implement` y `reppit-test` con "Subagent roles").
- `platform-blueprint` cerrado.

### Files (skyroute, rama main, sin commit)
- `.claude/agents/stage-author.md`, `executor.md`, `docs/design/reppit-orchestration/context.md` (new)
- `.claude/agents/*.md` ×7, `.claude/settings.json`, `AGENTS.md`, `CLAUDE.md` (modified)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `agent-workflow/context.md`, `platform-blueprint/context.md` (modified)

### reppit-orchestration — Verificación y modelos
- Decisión del owner (opción b): nueva Convention "Verification ownership"; fila retirada de Open decisions (Accepted).
- Ruling reversal "Modelo de los agentes": antes todos los agentes con `model: sonnet` (Sonnet 5.5); ahora `model: inherit` y el modelo se fija en cada prompt de sesión (contrato 4 de `session-orchestration`).
- `AGENTS.md` nombra 16 Conventions (121 líneas).
- Prueba de `stage-author` en segundo plano no ejecutada: los agentes de `.claude/agents/` no están cargados en esta sesión (`Agent type 'stage-author' not found`). Pendiente en una sesión nueva; `reppit-orchestration` sigue abierto.

### Files (skyroute, rama main, sin commit)
- `.claude/agents/*.md` ×9, `AGENTS.md` (modified)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `reppit-orchestration/context.md` (modified)

### reppit-orchestration — Smoke test y cierre del topic
- Prueba superada: `stage-author` (Sonnet), lanzado en segundo plano, escribió `working/smoke.md` con Write sin bloqueo de permisos; archivo borrado tras comprobarlo.
- Retirado el problema conocido "agentes no cargados en la sesión que los creó". Topic `reppit-orchestration` cerrado (Done).

### Files (skyroute, rama main, sin commit)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `reppit-orchestration/context.md` (modified)

### foundations — Topic abierto (Fase 1)
- Scaffold de `foundations/context.md`; Fase 1 pasa a In progress en README. Siguiente: Research.

### Files (skyroute, rama main, sin commit)
- `docs/design/foundations/context.md` (new)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md` (modified)

### foundations — Research (sesión infra-lead)
- `working/research.md` consolidado a partir de cuatro notas de área (terraform-layout, cicd-oidc, iam-security, account-cost); una ronda de revisión (adversarial-reviewer GO-WITH-FIXES, security-reviewer, cost-guard) y corrección de 22 hallazgos.
- Siete tensiones con Conventions registradas sin resolver (Region en el alta nueva de AWS, Budgets global, revisores de environments según plan de GitHub, bucket de state frente a IaC only, Apply gate frente al criterio de la Fase 1, cobros horarios de KMS, orden budget/backend). Decisión abierta "Plan de cuenta AWS" documentada, no decidida. Siguiente: Propose.
- Datos del owner añadidos a `research.md`: repo `javiladino/skyroute` creado 2026-11-12 (formato `sub` inmutable) y público; cuenta AWS existente en eu-west-3. Tensiones 1 (Region en el alta) y 3 (revisores de environments) resueltas por dato del owner.
- Conventions Region y Apply gate aclaradas con el owner (grill-me): servicios globales exentos de Region; GitHub Actions publica `plan` en cada PR; excepción única de bootstrap aplicada por el owner en local. Resueltas las tensiones 2, 4, 5 y 7; KMS queda para Propose.

### Files (skyroute, rama infra-foundations, sin commit)
- `docs/design/foundations/working/research.md`, `working/research/{terraform-layout,cicd-oidc,iam-security,account-cost}.md` (new)
- `docs/design/CONTEXT.md`, `CHANGELOG.md`, `foundations/context.md` (modified)

### foundations — Propose (sesión infra-lead)
- `working/proposal.md` con tres propuestas (mínimo coste; postura gestionada con Organizations e Identity Center; intermedia), una ronda de revisión (adversarial-reviewer GO-WITH-FIXES, security-reviewer, cost-guard) y corrección de todos los hallazgos.
- El owner eligió P1 con dos roles de CI: Ruling Foundations design. Decisión abierta "Plan de cuenta AWS" cerrada: Free, Paid aplazado. Siguiente: Plan.

### Files (skyroute, rama infra-foundations, sin commit)
- `docs/design/foundations/working/proposal.md` (new)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `foundations/context.md` (modified)

## 2026-11-13

### foundations — Plan (sesión infra-lead)
- `working/plan.md`: 7 fases, la última solo del owner y la CI; una ronda de revisión (adversarial-reviewer GO-WITH-FIXES, security-reviewer, cost-guard) y corrección.
- Conventions IaC only y Apply gate aclaradas con el owner: excepción para los recursos previos al bootstrap (usuario, grupo y pertenencia importados; budget y bucket manuales que borra el owner); "los roles de CI". El bucket manual está en eu-north-1 y no se adopta.

### Files (skyroute, rama infra-foundations, sin commit)
- `docs/design/foundations/working/plan.md` (new)
- `docs/design/CONTEXT.md`, `CHANGELOG.md`, `foundations/context.md` (modified)

### foundations — Implement, fases 1-6 (sesión infra-lead)
- Bootstrap de Terraform (budget, bucket de state, OIDC, roles `ci-plan`/`ci-apply` con boundary, imports del usuario del owner), backends de dev y prod, workflows de plan y apply, `.tflint.hcl`, runbook y comandos de `AGENTS.md`. fmt, validate y tflint pasan; checkov y la Fase 7 quedan para la CI y el owner.

### Files (skyroute, rama infra-foundations, sin commit)
- `infra/terraform/**`, `.github/workflows/terraform-{plan,apply}.yml`, `docs/runbooks/foundations-bootstrap.md` (new)
- `AGENTS.md`, `docs/design/foundations/working/plan.md` (modified)

### foundations — Test (sesión infra-lead)
- `working/test.md`: 57 PASS, 0 FAIL, 5 PENDIENTE de evidencia del owner o la CI (checkov, budget, plan del bootstrap, criterio de Fase 1, environments). Revisión GO-WITH-FIXES; aplicados 4 skips de checkov justificados y dos notas del runbook. Veredicto PENDIENTE hasta la Fase 7.

### Files (skyroute, rama infra-foundations, sin commit)
- `docs/design/foundations/working/test.md` (new)
- `infra/terraform/bootstrap/state_bucket.tf`, `docs/runbooks/foundations-bootstrap.md`, `docs/design/CONTEXT.md`, `CHANGELOG.md`, `foundations/context.md` (modified)

### foundations — Fase 7, pasos 1-2 (owner)
- Bootstrap aplicado por el owner: los primeros recursos AWS gestionados por Terraform existen (bucket de state en eu-west-3, OIDC, roles de CI, budget) y el state del bootstrap está migrado a S3 (verificado por el owner: `state list` con 18 recursos, `plan` sin cambios; state local borrado). Evidencia del plan en `evidence/bootstrap-plan.txt`; B9 PASS. Se había registrado la migración antes de estar hecha; corregido con esta verificación.

### Files (skyroute, rama infra-foundations, sin commit)
- `docs/design/foundations/evidence/bootstrap-plan.txt`, `infra/terraform/bootstrap/backend.tf` (new)
- `docs/design/foundations/working/test.md`, `CONTEXT.md`, `CHANGELOG.md`, `foundations/context.md` (modified)

### foundations — checkov en la PR
- Nueva Convention Bootstrap identity: el usuario de arranque con `AdministratorAccess` es un riesgo aceptado; CKV_AWS_273 y CKV_AWS_274 se omiten solo en sus dos recursos. checkov local con el comando de la CI: 35 passed, 0 failed, 6 skipped. Corregido en `test.md` el PASS engañoso (greps estáticos, no ejecuciones de checkov).

### Files (skyroute, rama infra-foundations)
- `infra/terraform/bootstrap/owner_user.tf`, `AGENTS.md`, `docs/design/CONTEXT.md`, `CHANGELOG.md`, `foundations/context.md`, `foundations/working/test.md` (modified)
