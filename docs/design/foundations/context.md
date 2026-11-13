# foundations — Contexto

**Tracker:** ninguno
**Status:** Done · **Owner:** javiladino

## Orientación

Fase 1 — Fundaciones (README § Fases): cuenta AWS con MFA y usuario no root, presupuesto, repo, bootstrap de Terraform (state remoto, rol OIDC para GitHub Actions) y CI básica. Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica. Restricciones: Conventions Region, IaC only, Apply gate y No hourly-billed resources. Decisión abierta que toca a esta fase: plan de cuenta AWS (README § Open decisions). Cerrado el 2026-11-13: Test PASS (`current/test.md`) y lo construido descrito en `current/plan.md`; la propuesta elegida está en `archive/proposal.md` § Decision. Operación: `docs/runbooks/foundations-bootstrap.md`.

## Rulings

- **Foundations design (javiladino, 2026-11-12 18:00):** Proposal 1 con dos roles de CI: state con SSE-S3 (sin KMS), cuenta AWS en plan Free (Paid aplazado), owner con IAM user y MFA (sin Organizations ni Identity Center), roles `ci-plan` (`sub` `pull_request`) y `ci-apply` (`sub` `environment:dev`/`environment:prod`, environments solo desde `main`). Discusión: `archive/proposal.md` § Decision.

## Journal (newest first)

**2026-11-13 (cierre):** Ciclo cerrado en la rama `docs/foundations-close` (desde `origin/main`, con el merge `ec5cfdd`). `plan.md` y `test.md` pasan a `current/`; `research.md`, sus cuatro notas y `proposal.md`, a `archive/`. Status Done. Las rutas internas de los stage files citan su ubicación de entonces (`working/…`). Follow-up abierto: comprobar en el próximo merge que apply-prod espera la aprobación, los 3 nits de CI y alinear `encrypt = true` en envs/* y el runbook.

**2026-11-13 (Test PASS):** El owner añadió `required_reviewers` (`javiladino`, Prevent self-review desactivado) y desactivó el bypass de admins en `prod`. Lo verificó el orquestador con `gh api …/environments/prod`. A10 pasa a PASS; `test.md`: 65 PASS, 0 FAIL, 0 PENDIENTE, veredicto PASS. Follow-up: comprobar en el próximo merge que apply-prod espera la aprobación, más los 3 nits de CI de la revisión. Siguiente: cierre del ciclo, si el owner lo aprueba.

**2026-11-13 (A10 y F1):** PR #1 fusionada. Verificado con `gh` de solo lectura (executor), y el orquestador repitió `environments/prod` y el run de apply. F1 PASS: comentarios de plan de dev y prod con "No changes", run de plan 43446309534 en success con checkov, y run de apply 43449637195 en `main` (merge `ec5cfdd`) en success con apply-dev y apply-prod. A10 FAIL: `prod` solo tiene `branch_policy`, sin `required_reviewers`, y `can_admins_bypass: true`, así que apply-prod se aplicó sin aprobación manual, contra la Convention Apply gate. Sí cumplen la política de rama `main` en dev y prod y el ruleset de `main` (PR obligatoria). `test.md`: 64 PASS, 1 FAIL; veredicto FAIL.

**2026-11-13 (B6):** El owner aportó `evidence/describe-budgets.json`, regenerada filtrada a `skyroute-monthly-10usd` porque la primera captura incluía un budget ajeno al proyecto. La evidencia no tiene email: 10 USD al mes, tipo COST, sin créditos ni reembolsos. Salidas del owner: el budget manual y el bucket de eu-north-1 están borrados (B6b y B6c PASS). El executor había puesto B6 en PASS sin la evidencia del bucket de state y se corrigió a parcial. Después el owner aportó `get-bucket-encryption` (AES256, SSE-C bloqueado) y `get-bucket-versioning` (Enabled), y B6 pasó a PASS. Test: 63 PASS, 2 PENDIENTE (A10, F1).

**2026-11-13 (checkov en la PR):** El checkov de la CI falló en la PR (35 passed, 2 failed, 4 skipped) con CKV_AWS_273 y CKV_AWS_274 en `bootstrap/owner_user.tf`. El owner los acepta como riesgo. Nueva Convention Bootstrap identity en CONTEXT.md, con su nombre añadido a la lista de `AGENTS.md`, y dos skips inline que la citan (executor). Causa del PASS engañoso: ninguna fila de `test.md` ejecutó checkov. T4 estaba PENDIENTE, y T4b y T4c eran greps estáticos. Local y CI usan la misma versión (3.4.5) y el mismo comando, así que no hace falta cambiar el pin. Ejecución local en un venv del scratchpad con el comando de la CI, repetida por el orquestador: 35 passed, 0 failed, 6 skipped. `test.md` corregido (executor). Pendiente: que el owner confirme el nuevo run de la CI tras el push.

**2026-11-13 (Fase 7, pasos 1-2):** El owner aplicó el bootstrap en local (4 importados, 14 añadidos) y aportó `evidence/bootstrap-plan.txt`, en el que los 4 imports no muestran cambios. B9 pasa a PASS en `test.md` (executor). `bootstrap/backend.tf` escrito por executor (con `encrypt = true`, que no figura en el runbook ni en envs/*). Se registró el `init -migrate-state` antes de que estuviera hecho y el owner lo corrigió. Lo ejecutó después y lo verificó: `bootstrap/terraform.tfstate` en el bucket, 18 recursos en `state list`, `plan` sin cambios. Borró el state local, el `.tfplan` y su copia. `test.md` corregido (executor) con esa verificación. Test: 4 PENDIENTE (T4, A10, B6, F1).

**2026-11-13 (Test):** Commit `9b70313` (Plan e Implement). `working/test.md` (executor, Sonnet) con base `d264a40`: 57 PASS, 0 FAIL, 5 PENDIENTE (T4 checkov, B6, B9, F1, A10), todos a la espera de evidencia del owner o la CI. Revisión del diff (adversarial-reviewer, Opus): GO-WITH-FIXES. Con el visto bueno del owner, executor añadió 4 `#checkov:skip` justificados en `state_bucket.tf` y dos notas al runbook; quedan 3 nits como follow-up. El orquestador repitió fmt, validate ×3 y el conteo de skips. Veredicto PENDIENTE. Siguiente: Fase 7 del owner según el runbook y, con su evidencia, cerrar Test.

**2026-11-13 (Implement):** Visto bueno del owner al plan. Respuestas incorporadas al plan: environments ya creados en GitHub, grupo `admins` con AdministratorAccess, bucket `skyroute-tfstate-437266392155-eu-west-3`, checkov solo en CI. Fases 1-6 ejecutadas por un executor cada una (Opus en las 2 y 3, Sonnet en el resto); el orquestador volvió a ejecutar cada validación. Decisiones del owner sobre la deriva, ya registradas en el plan: `*` solo en Deny; Deny que protege `ci-boundary`; sin filtros `paths`, con `concurrency`; el runbook nombra el bucket manual. Verificación final: `terraform fmt -check` limpio, `validate` correcto en los 3 root modules, tflint sin hallazgos. Sin comprobar: sintaxis YAML (no hay actionlint ni PyYAML) y checkov (solo en CI). Fase 7 pendiente del owner. Siguiente: Test (`reppit-test`).

- 2026-11-13: Plan hecho (7 fases, una ronda de revisión); bucket manual en eu-north-1 no adoptado; Conventions IaC only y Apply gate aclaradas.

- 2026-11-12: Propose hecho (tres propuestas revisadas); el owner eligió P1 con dos roles de CI (Ruling Foundations design).

- 2026-11-12: Research hecho (`working/research.md`, cuatro notas de área, una ronda de revisión); Conventions Region y Apply gate aclaradas con el owner; tensión de KMS a Propose.
- 2026-11-12: topic abierto (scaffold).

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `current/plan.md` | deliverable | on-demand | Diseño de lo construido en la Fase 1: decisiones, componentes, Files Changed, Testing Strategy |
| `current/test.md` | deliverable | on-demand | Informe de Test: 65 checks PASS con evidencia, Review y follow-ups |
| `archive/research.md` | reference | on-demand | Research gastado: estado del repo, hechos de las cuatro áreas, tensiones con Conventions |
| `archive/proposal.md` | reference | on-demand | Propose gastado: tres propuestas y § Decision (P1 con dos roles), discusión del Ruling Foundations design |
| `evidence/bootstrap-plan.txt` | reference | on-demand | Salida del plan local del bootstrap (Fase 7, paso 1), aportada por el owner el 2026-11-13; sin email, con el account ID aceptado |
| `evidence/describe-budgets.json` | reference | on-demand | Salida de `aws budgets describe-budget` de `skyroute-monthly-10usd` (check B6), aportada por el owner el 2026-11-13; sin email |
| `archive/research/terraform-layout.md` | reference | on-demand | Nota de área: layout bootstrap/modules/envs, backend S3 `use_lockfile`, bootstrap del bucket, versiones |
| `archive/research/cicd-oidc.md` | reference | on-demand | Nota de área: OIDC GitHub→AWS, formatos `sub`, plan en PR y apply al fusionar, environments |
| `archive/research/iam-security.md` | reference | on-demand | Nota de área: acceso del owner (IAM user / Identity Center), rol de CI, protección del bucket de state |
| `archive/research/account-cost.md` | reference | on-demand | Nota de área: plan Free/Paid, servicios por región y plan, Budgets, precios eu-west-3 |
