# foundations — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 1 — Fundaciones (README § Fases): cuenta AWS con MFA y usuario no root, presupuesto, repo, bootstrap de Terraform (state remoto, rol OIDC para GitHub Actions) y CI básica. Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica. Restricciones: Conventions Region, IaC only, Apply gate y No hourly-billed resources. Decisión abierta que toca a esta fase: plan de cuenta AWS (README § Open decisions). Siguiente: Fase 7 del owner y la CI (`docs/runbooks/foundations-bootstrap.md`); con su evidencia (URL del comentario de plan, run de apply y checkov, salidas de `aws`) se cierra Test (`working/test.md`, hoy PENDIENTE) y el ciclo; propuesta elegida en `working/proposal.md` § Decision.

## Rulings

- **Foundations design (javiladino, 2026-11-12 18:00):** Proposal 1 con dos roles de CI: state con SSE-S3 (sin KMS), cuenta AWS en plan Free (Paid aplazado), owner con IAM user y MFA (sin Organizations ni Identity Center), roles `ci-plan` (`sub` `pull_request`) y `ci-apply` (`sub` `environment:dev`/`environment:prod`, environments solo desde `main`). Discusión: `working/proposal.md` § Decision.

## Journal (newest first)

**2026-11-13 (checkov en la PR):** El checkov de la CI falló en la PR (35 passed, 2 failed, 4 skipped) con CKV_AWS_273 y CKV_AWS_274 en `bootstrap/owner_user.tf`. El owner los acepta como riesgo. Nueva Convention Bootstrap identity en CONTEXT.md, con su nombre añadido a la lista de `AGENTS.md`, y dos skips inline que la citan (executor). Causa del PASS engañoso: ninguna fila de `test.md` ejecutó checkov. T4 estaba PENDIENTE, y T4b y T4c eran greps estáticos. Local y CI usan la misma versión (3.4.5) y el mismo comando, así que no hace falta cambiar el pin. Ejecución local en un venv del scratchpad con el comando de la CI, repetida por el orquestador: 35 passed, 0 failed, 6 skipped. `test.md` corregido (executor). Pendiente: que el owner confirme el nuevo run de la CI tras el push.

**2026-11-13 (Fase 7, pasos 1-2):** El owner aplicó el bootstrap en local (4 importados, 14 añadidos) y aportó `evidence/bootstrap-plan.txt`, en el que los 4 imports no muestran cambios. B9 pasa a PASS en `test.md` (executor). `bootstrap/backend.tf` escrito por executor (con `encrypt = true`, que no figura en el runbook ni en envs/*). Se registró el `init -migrate-state` antes de que estuviera hecho y el owner lo corrigió. Lo ejecutó después y lo verificó: `bootstrap/terraform.tfstate` en el bucket, 18 recursos en `state list`, `plan` sin cambios. Borró el state local, el `.tfplan` y su copia. `test.md` corregido (executor) con esa verificación. Test: 4 PENDIENTE (T4, A10, B6, F1).

**2026-11-13 (Test):** Commit `9b70313` (Plan e Implement). `working/test.md` (executor, Sonnet) con base `d264a40`: 57 PASS, 0 FAIL, 5 PENDIENTE (T4 checkov, B6, B9, F1, A10), todos a la espera de evidencia del owner o la CI. Revisión del diff (adversarial-reviewer, Opus): GO-WITH-FIXES. Con el visto bueno del owner, executor añadió 4 `#checkov:skip` justificados en `state_bucket.tf` y dos notas al runbook; quedan 3 nits como follow-up. El orquestador repitió fmt, validate ×3 y el conteo de skips. Veredicto PENDIENTE. Siguiente: Fase 7 del owner según el runbook y, con su evidencia, cerrar Test.

**2026-11-13 (Implement):** Visto bueno del owner al plan. Respuestas incorporadas al plan: environments ya creados en GitHub, grupo `admins` con AdministratorAccess, bucket `skyroute-tfstate-437266392155-eu-west-3`, checkov solo en CI. Fases 1-6 ejecutadas por un executor cada una (Opus en las 2 y 3, Sonnet en el resto); el orquestador volvió a ejecutar cada validación. Decisiones del owner sobre la deriva, ya registradas en el plan: `*` solo en Deny; Deny que protege `ci-boundary`; sin filtros `paths`, con `concurrency`; el runbook nombra el bucket manual. Verificación final: `terraform fmt -check` limpio, `validate` correcto en los 3 root modules, tflint sin hallazgos. Sin comprobar: sintaxis YAML (no hay actionlint ni PyYAML) y checkov (solo en CI). Fase 7 pendiente del owner. Siguiente: Test (`reppit-test`).

**2026-11-13 (Plan):** Commit `d264a40` (Research y Propose). Intake con el owner: modelos como en Propose; primer apply con usuario IAM puente (`skyroute-dev`, grupo `admins`, `aws login`), importado con grupo y pertenencia; versiones no actuales 90 días; IDs `sub` vía `gh api` (executor). El bucket manual está en eu-north-1 (salida del owner): no se adopta, el bootstrap crea uno en eu-west-3. Conventions IaC only y Apply gate aclaradas (recursos previos al bootstrap; "los roles de CI"). `working/plan.md` (stage-author, Opus); revisión (adversarial-reviewer GO-WITH-FIXES, security-reviewer, cost-guard) y corrección (stage-author, Sonnet). Versiones locales: tflint 0.65.0, terraform 1.17.1, checkov sin instalar. Pendiente: visto bueno del owner para Implement y 4 preguntas del plan.

**2026-11-12 (Propose):** Sesión `infra-lead`. Intake con grill-me: cuenta en Free y abierta a Paid; Identity Center con Organizations como una opción. `working/proposal.md` (stage-author, Opus) con tres propuestas; revisión en paralelo (adversarial-reviewer GO-WITH-FIXES y security-reviewer, Opus; cost-guard, Sonnet) y corrección de todos los hallazgos (stage-author, Sonnet). El principal: environments solo desde `main` para que una PR no asuma el rol de apply. Recomendada P3; el owner eligió P1 con dos roles (Ruling Foundations design). Pendiente para Plan: credenciales del primer apply del bootstrap, días de lifecycle de versiones no actuales, IDs numéricos para el `sub`, permisos de Budgets y `envs/*`. Siguiente: Plan (`reppit-plan`).

**2026-11-12 (Research):** Sesión `infra-lead` en rama `infra-foundations`. Cuatro notas de área (stage-author, Sonnet) consolidadas en `working/research.md` (stage-author, Opus); una ronda de revisión (adversarial-reviewer GO-WITH-FIXES, security-reviewer, cost-guard) y corrección (stage-author, Sonnet) de 22 hallazgos. Siete tensiones con Conventions en § 4.1 y 17 ítems no verificados en § 3.5, ambos sin resolver. Gate-check de estructura: siete secciones presentes. Siguiente: Propose (`reppit-propose`), tras el visto bueno del owner. Después, datos del owner (repo creado 2026-11-12 y público; cuenta AWS existente en eu-west-3) registrados en `research.md` por stage-author (Sonnet): tensiones 1 y 3 resueltas por dato del owner; § 3.5 baja a 15 ítems. Ronda `grill-me` con el owner: Region → servicios globales (IAM, Budgets, Organizations) exentos, provider siempre en eu-west-3; Bootstrap del state → excepción única a Apply gate (el owner aplica `infra/terraform/bootstrap/` una vez en local y migra el state; crea budget, bucket, OIDC y rol de CI); Plan en PR → GitHub Actions no es un agente y publica `plan` en cada PR. Escritas en CONTEXT.md § Conventions (Region, Apply gate). Con ello quedan resueltas las tensiones 2, 4, 5 y 7 de `research.md` § 4.1; la 6 (KMS) va a Propose. Reparto de roles plan/apply: diseño, a Propose.

**2026-11-12:** Topic abierto (scaffold). Sin stage files.

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `working/research.md` | draft | on-demand | Stage file Research: estado del repo, hechos externos de las cuatro áreas, tensiones con Conventions, no verificado |
| `working/proposal.md` | draft | on-demand | Stage file Propose: tres propuestas revisadas, tabla de recomendación y § Decision (P1 con dos roles) |
| `working/plan.md` | draft | on-demand | Stage file Plan: 7 fases (6 de executor, 1 del owner y la CI), Files Changed, Testing Strategy para reppit-test |
| `working/test.md` | draft | on-demand | Stage file Test: 62 checks (57 PASS, 5 PENDIENTE del owner o la CI), Review GO-WITH-FIXES, follow-ups |
| `evidence/bootstrap-plan.txt` | reference | on-demand | Salida del plan local del bootstrap (Fase 7, paso 1), aportada por el owner el 2026-11-13; sin email, con el account ID aceptado |
| `working/research/terraform-layout.md` | draft | on-demand | Nota de área: layout bootstrap/modules/envs, backend S3 `use_lockfile`, bootstrap del bucket, versiones |
| `working/research/cicd-oidc.md` | draft | on-demand | Nota de área: OIDC GitHub→AWS, formatos `sub`, plan en PR y apply al fusionar, environments |
| `working/research/iam-security.md` | draft | on-demand | Nota de área: acceso del owner (IAM user / Identity Center), rol de CI, protección del bucket de state |
| `working/research/account-cost.md` | draft | on-demand | Nota de área: plan Free/Paid, servicios por región y plan, Budgets, precios eu-west-3 |
