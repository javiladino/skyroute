---
type: Test
---

# Foundations: Test Report

> **Date:** 2026-11-13 · **Base:** d264a40 (HEAD 9b70313) · **Plan:** docs/design/foundations/working/plan.md

## Verdict: PENDIENTE

Los 59 checks que dan PASS (57 ejecutados por un agente más B9 y M1, con evidencia del owner; 0 FAIL; la review es GO-WITH-FIXES con los fixes aplicados): fmt, validate y tflint en los tres root modules, y todos los Grep de Region, IaC only, Apply gate, seguridad del state, No hourly-billed y Budget/bucket. Quedan 4 filas PENDIENTE (owner/CI): T4, A10, B6 y F1. A10 se ejecutó en solo lectura y hoy muestra que la configuración de los environments y de la branch protection todavía no está hecha (ver fila).
Ajustes decididos por el owner/orquestador: tflint con `--config=<abs>/infra/terraform/.tflint.hcl` (la fila T3 del plan no lo incluye); `validate` sin repetir `init -backend=false` (ya hecho); sin tests protegidos porque no existen archivos de test. Los Grep se ejecutaron con `rg`/`grep` sin pipes, una orden por llamada. Rutas abreviadas: `TF` = `infra/terraform`, `BS` = `infra/terraform/bootstrap`, `WF` = `.github/workflows`.

## Checks

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| T1 | fmt | plan T1 | `terraform fmt -check -recursive infra/terraform` | sin salida, exit 0 | PASS |
| T2 | validate x3 | plan T2 | `terraform -chdir=infra/terraform/{bootstrap,envs/dev,envs/prod} validate` | "Success! The configuration is valid." en los tres | PASS |
| T3 | tflint x3 | plan T3 | `tflint --chdir=infra/terraform/{bootstrap,envs/dev,envs/prod} --config=<abs>/infra/terraform/.tflint.hcl` | sin salida, exit 0 en los tres (nota: el plan omite `--config`) | PASS |
| T4 | checkov en CI | plan T4 | no ejecutado (no instalado localmente; solo CI) | Necesita: URL del run de Actions con `static-checks` en verde | PENDIENTE (owner/CI) |
| T4b | checkov en terraform-plan.yml | plan T4b | `rg -n 'checkov\|id-token\|environment:\|^  [a-z-]+:$' WF/terraform-plan.yml` | checkov en job `static-checks` (L110-131); `id-token: write` solo en job `plan` (L22); sin `environment:` | PASS |
| R1 | region eu-west-3 | plan R1 | `rg -n 'region\s*=\s*"eu-west-3"' TF --glob '*.tf'` | 5: versions.tf:13, dev/backend.tf:14,20, prod/backend.tf:14,20 (backend + provider en dev y prod; provider en bootstrap) | PASS |
| R2 | ninguna otra región | plan R2 | `rg -nP 'region\s*=\s*"(?!eu-west-3)' TF` | 0 | PASS |
| R3 | sin eu-north-1 en .tf | plan R3 | `rg -n 'eu-north-1' TF --glob '*.tf'` | 0 | PASS |
| R4 | sin bucket manual en .tf | plan R4 | `rg -n 'skyroute-tfstate-demo' TF --glob '*.tf'` | 0 | PASS |
| R5 | runbook nombra el bucket manual | plan R5 | `grep -c skyroute-tfstate-demo-437266392155-eu-north-1-an docs/runbooks/foundations-bootstrap.md` | 3 | PASS |
| I1 | use_lockfile | plan I1 | `rg -n 'use_lockfile\s*=\s*true' TF` | 2 (dev:15, prod:15) | PASS |
| I2 | sin dynamodb_table | plan I2 | `rg -n 'dynamodb_table' TF` | 0 | PASS |
| I3 | budget | plan I3 | `rg -n 'resource "aws_budgets_budget"' BS` | 1 (budget.tf:1) | PASS |
| I4 | imports | plan I4 | `rg -n '^import\s*\{' BS` | 4 (owner_user.tf:5,10,15,20) | PASS |
| A1 | 3 sub | plan A1 | `rg -n 'repo:javiladino@97758532/skyroute@1455233709:(pull_request\|environment:(dev\|prod))' BS` | 3: ci_roles.tf:121 (ci-plan), 246, 247 (ci-apply) | PASS |
| A2 | sin StringLike | plan A2 | `rg -n 'StringLike' TF` | 0 | PASS |
| A3 | sts.amazonaws.com | plan A3 | `rg -n 'sts.amazonaws.com' BS` | ci_roles.tf:120, 244; oidc.tf:3 | PASS |
| A4 | Resource "*" solo en Deny | plan A4 | `grep -n 'Resource *= *"\*"' BS/ci_roles.tf` y `grep -n 'Effect\|Resource *= *"\*"' BS/ci_roles.tf` | 6 líneas (59, 70, 183, 194, 310, 321); cada una va precedida por `Effect = "Deny"` (57, 68, 181, 192, 308, 319) | PASS |
| A4a | sin Allow con Resource "*" | plan A4a | `rg -nU --multiline-dotall 'Effect\s*=\s*"Allow"[^}]*Resource\s*=\s*"\*"' BS/ci_roles.tf` | 0 | PASS |
| A4d | acciones de políticas IAM | plan A4d | `grep -c` de `iam:CreatePolicyVersion`, `iam:SetDefaultPolicyVersion`, `iam:DeletePolicy"`, `iam:DeletePolicyVersion` en BS/ci_roles.tf (4 llamadas) | 3, 3, 3, 3 | PASS |
| A4e | boundary condition | plan A4e | `grep -c 'StringNotEquals'` y `grep -c 'iam:PermissionsBoundary'` en BS/ci_roles.tf | 3; 12 | PASS |
| A4b | claves de state por rol | plan A4b | `rg -c '(envs/(dev\|prod)/terraform\.tfstate)(\.tflock)?' BS/ci_roles.tf` | 12 (>= 8) | PASS |
| A4c | roles sin state de bootstrap | plan A4c | `rg -c 'bootstrap/terraform\.tfstate' BS/ci_roles.tf` | sin coincidencias (0) | PASS |
| A5 | sin pull_request_target | plan A5 | `rg -n 'pull_request_target' WF` | 0 | PASS |
| A5b | workflows sin bootstrap | plan A5b | `rg -n 'bootstrap' WF` | 0 | PASS |
| A6 | actions fijadas por SHA | plan A6 | `rg -nP 'uses:\s*\S+@(?![0-9a-f]{40})' WF` | 0 | PASS |
| A7 | sin upload-artifact | plan A7 | `rg -n 'upload-artifact' WF` | 0 | PASS |
| A7b | permissions {} | plan A7b | `rg -n '^permissions:\s*\{\}' WF` | 2 (apply:7, plan:6) | PASS |
| A7c | persist-credentials | plan A7c | `rg -n 'persist-credentials:\s*false' WF` y `rg -n 'actions/checkout' WF` | 4 y 4 | PASS |
| A7d | concurrency en apply | plan A7d | `rg -n 'concurrency:' WF/terraform-apply.yml` | 1 (L9) | PASS |
| A7f | sin paths: | plan A7f | `grep -r -c 'paths:' WF` | apply 0, plan 0 | PASS |
| A7e | -no-color y TF_LOG | plan A7e | `rg -n -e '-no-color' WF/terraform-plan.yml` y `rg -n 'TF_LOG' WF` | 4 líneas; 0 | PASS |
| A8 | environments | plan A8 | `rg -n 'environment:\s*(dev\|prod)' WF/terraform-apply.yml` y `rg -n 'environment:' WF/terraform-plan.yml` | 2 (L22 dev, L58 prod); 0 | PASS |
| A9 | plan solo plan | plan A9 | `rg -n 'terraform (plan\|apply)' WF/terraform-plan.yml` | 1 línea, solo `terraform plan` (L63) | PASS |
| A10 | environments y branch protection | plan A10 | `gh api repos/javiladino/skyroute/environments/dev`, `.../environments/prod`, `.../branches/main/protection` | dev y prod: `deployment_branch_policy: null`, `protection_rules: []`, `can_admins_bypass: true` (sin revisor ni restricción a `main`); `branches/main/protection`: HTTP 404 "Branch not protected". Los environments existen pero el owner aún no los ha configurado | PENDIENTE (owner) |
| S1 | state bucket protegido | plan S1 | `rg -n 'prevent_destroy\s*=\s*true\|force_destroy\s*=\s*false' BS/state_bucket.tf` | 1 cada uno (L6, L3) | PASS |
| S2 | Deny DeleteBucket | plan S2 | `rg -n 's3:DeleteBucket' BS/state_bucket.tf` | L70 | PASS |
| S3 | Deny de acciones S3 | plan S3 | `rg -n 's3:DeleteObjectVersion\|s3:PutBucketVersioning\|...' BS/ci_roles.tf` | 3 bloques (L87-91 boundary, L211-215 ci-plan, L338-342 ci-apply), cada uno tras un `Effect = "Deny"` (L85, 209, 336) | PASS |
| S4 | Deny sobre owner | plan S4 | `rg -n 'user/skyroute-dev\|group/admins' BS/ci_roles.tf` | 3 cada uno (L41-42, 165-166, 292-293) | PASS |
| S5 | boundary/IAM | plan S5 | `grep -c 'iam:PermissionsBoundary'` (12) y `rg -n 'iam:CreateRole\|iam:PutRolePermissionsBoundary\|iam:DeleteRolePermissionsBoundary'` | 12; 6 líneas (3 bloques x 2) | PASS |
| S6 | trust AssumeRoleWithWebIdentity | plan S6 | `rg -n 'sts:AssumeRoleWithWebIdentity\|sts:AssumeRole"\|Federated...' BS/ci_roles.tf` | AssumeRoleWithWebIdentity 2 (L117, 241); `sts:AssumeRole"` 0 | PASS |
| S7 | Federated | plan S7 | mismo comando que S6 | 2 (L115, 239) | PASS |
| S8 | aud y sub en el mismo StringEquals | plan S8 | `rg -nU 'StringEquals[^}]*:aud[^}]*:sub\|StringEquals[^}]*:sub[^}]*:aud' BS/ci_roles.tf` | 2 (L119, L243) | PASS |
| S9 | sin emails reales | plan S9 | `rg -n '<regex email>' infra .github docs/runbooks` | 2: runbook L13 y terraform.tfvars.example:2, ambos `tu-email@example.com` | PASS |
| S10 | sensitive y gitignore | plan S10 | `rg -n 'sensitive\s*=\s*true' BS/variables.tf`; `grep -n 'tfvars' .gitignore` | variables.tf:4; .gitignore L8 `*.tfvars`, L9 `!*.tfvars.example` | PASS |
| N1 | sin recursos con coste por hora | plan N1 | `rg -n 'aws_kms\|aws_nat_gateway\|...' TF --glob '*.tf'` | 0 | PASS |
| N2 | sin budget action | plan N2 | `rg -n 'aws_budgets_budget_action' TF` | 0 | PASS |
| B1 | umbrales | plan B1 | `rg -n 'threshold\s*=\s*(50\|80\|100)\b' BS/budget.tf` | 3 (L15, 23, 31) | PASS |
| B2 | sin FORECASTED | plan B2 | `rg -n 'FORECASTED' TF` | 0 | PASS |
| B3 | suscriptores | plan B3 | `rg -n 'subscriber_email_addresses' BS/budget.tf` | 3 | PASS |
| B4 | lifecycle | plan B4 | `rg -n 'noncurrent_days\s*=\s*90\|abort_incomplete_multipart_upload\|expired_object_delete_marker' BS/state_bucket.tf` | 3 líneas, 1 cada patrón (L89, 93, 96) | PASS |
| B5 | SecureTransport | plan B5 | `rg -n 'aws:SecureTransport' BS/state_bucket.tf` | L62 | PASS |
| B6 | cifrado, versionado, budget en AWS | plan B6 | no ejecutado (comandos `aws`, solo owner) | Necesita: salida de `aws s3api get-bucket-encryption`, `get-bucket-versioning` y `aws budgets describe-budgets` (AES256; Enabled; 10 USD) | PENDIENTE (owner) |
| B7 | include_credit | plan B7 | `rg -n 'include_credit\s*=\s*false\|include_refund\s*=\s*false' BS/budget.tf` | L9 | PASS |
| B8 | include_refund | plan B8 | mismo comando que B7 | L10 | PASS |
| B9 | plan del paso 1: los 4 imports sin cambios | plan B9 | evidencia del owner: `docs/design/foundations/evidence/bootstrap-plan.txt`; `grep -n 'Plan:'`, `grep -n 'will be imported'`, `grep -n 'will be updated in-place'` | L306 `Plan: 4 to import, 14 to add, 0 to change, 0 to destroy.`; 4 `will be imported` (L53 aws_iam_group.admins, L62 aws_iam_group_policy_attachment.admins_administrator_access, L153 aws_iam_user.owner, L165 aws_iam_user_group_membership.owner_admins); `will be updated in-place`: 0 | PASS (evidencia del owner) |
| F1 | PR muestra plan y merge lo aplica | plan F1 | no ejecutado (CI/owner) | Necesita: URL del comentario de plan en la PR de prueba y URL del run de `terraform-apply.yml` con `apply-dev` en verde | PENDIENTE (owner/CI) |
| P1 | Archivos protegidos | plan (Files Changed) | `git diff d264a40 --stat` | Sin tests protegidos: no existen archivos de test. 22 archivos, 1360 inserciones, 8 borrados: 2 workflows, AGENTS.md, 3 archivos de memoria de diseño (CHANGELOG.md, CONTEXT.md, foundations/context.md), working/plan.md, runbook, `.tflint.hcl`, 10 archivos de bootstrap (con su lock) y `envs/{dev,prod}` (backend.tf y lock) | PASS (con observación, ver Follow-up) |

| T1r | fmt tras los fixes de la review | plan T1 (re-ejecución) | `terraform fmt -check -recursive infra/terraform` | sin salida, exit 0 | PASS (orquestador) |
| T2r | validate x3 tras los fixes | plan T2 (re-ejecución) | `terraform -chdir=infra/terraform/{bootstrap,envs/dev,envs/prod} validate` | "Success! The configuration is valid." x3 | PASS (orquestador) |
| T4c | skips de checkov en el state bucket | review hallazgo 1 | `grep -c 'checkov:skip=' infra/terraform/bootstrap/state_bucket.tf` | 4 | PASS (orquestador) |
| REV | Review adversarial (d264a40..9b70313) | reppit-test | adversarial-reviewer (Opus) | GO-WITH-FIXES; fixes 1, 2 y 6 aplicados, 3 nits como follow-up | PASS |
| M1 | Migración del state del bootstrap a S3 | plan Fase 7 paso 2 | evidencia del owner (salida en chat, 2026-11-13): `aws s3 ls`, `terraform state list`, `terraform plan`, `find` | `aws s3 ls` muestra `bootstrap/terraform.tfstate` en `skyroute-tfstate-437266392155-eu-west-3`; `terraform state list` devuelve 18 recursos (4 importados + 14 añadidos, coincide con B9); `terraform plan` devuelve "No changes"; borrados `terraform.tfstate`, `terraform.tfstate.backup`, el `.tfplan` y la copia de respaldo del owner; `find` no halla ningún `*.tfstate` fuera de `.terraform/` | PASS (evidencia del owner) |

Evidencia aportada por el owner en la Fase 7 (Convention Verification ownership; el Apply gate impide que el agente la ejecute). El account ID que aparece en ella lo acepta el owner, sin anonimizar:

- Apply del paso 1 (aportada por el owner, texto en chat, 2026-11-13): "Apply complete! Resources: 4 imported, 14 added, 0 changed, 0 destroyed." Bucket `skyroute-tfstate-437266392155-eu-west-3` creado en eu-west-3. Coincide con el plan de B9 (4 import, 14 add).
- Paso 2, migración del state (verificación del owner de 2026-11-13, salida citada en chat): `aws s3 ls` muestra `bootstrap/terraform.tfstate` en el bucket `skyroute-tfstate-437266392155-eu-west-3`; `terraform state list` devuelve 18 recursos (4 importados + 14 añadidos, coherente con B9); `terraform plan` devuelve "No changes"; se borraron el `terraform.tfstate` local, el `terraform.tfstate.backup`, el `.tfplan` y la copia de respaldo del owner, y `find` no encuentra ningún `*.tfstate` fuera de `.terraform/`. Corrección: el registro anterior daba el `terraform init -migrate-state` por hecho a partir de una afirmación previa, y era prematuro. En ese momento no se había hecho: Terraform informaba "Backend initialization required" y el bucket estaba vacío. Este registro lo corrige. No sustituye a B6.

Resumen: 59 PASS, 0 FAIL, 4 PENDIENTE (T4, A10, B6, F1). Las 4 filas nuevas (T1r, T2r, T4c, REV) vienen de la review y de la re-ejecución del orquestador tras los fixes; M1 se añade con la evidencia del owner sobre la migración del state. El `git status` final se comprobó al cerrar la sesión (solo `test.md` nuevo).

## Review

Veredicto del adversarial-reviewer (Opus, code review de d264a40..9b70313): GO-WITH-FIXES.

1. should-fix: checkov fallaría en el state bucket (CKV_AWS_18, CKV_AWS_144, CKV_AWS_145, CKV2_AWS_62) sin skips y sin `--soft-fail`. Fixed, con aprobación del owner: 4 `#checkov:skip=ID:motivo` en `infra/terraform/bootstrap/state_bucket.tf` (sin commit).
2. should-fix: el runbook no avisaba de que el Deny de `s3:DeleteBucket` con Principal `"*"` bloquea también al owner. Fixed: nota en `docs/runbooks/foundations-bootstrap.md`.
3. nit: el fmt y el tflint de CI no cubren `bootstrap/`. Follow-up.
4. nit: `tflint --init` dentro del bucle se ejecuta dos veces. Follow-up.
5. nit: las PR desde forks fallan en el paso OIDC y no dejan comentario (CI 16). Follow-up.
6. nit: el runbook no decía que hay que borrar el tfstate local tras `migrate-state`. Fixed en el runbook.

Verificado OK por el reviewer: permisos de ci-plan y ci-apply suficientes para el backend, los Deny no bloquean el backend, trust exacto, permissions/needs/environments de los workflows coinciden, argumentos del budget, IDs de import y orden del runbook.

Fila REV: PASS, porque los fixes 1, 2 y 6 están aplicados y los 3 nits restantes son follow-up menor fuera del alcance del plan.

## Follow-up

- Review nits 3, 4 y 5: incluir `bootstrap/` en fmt/tflint de CI, quitar el `tflint --init` duplicado del bucle y decidir qué hacer con las PR desde forks (fallan en OIDC sin comentario).
- Las 4 filas PENDIENTE (T4, B6, F1, A10) necesitan evidencia del owner o de CI (runbook Fase 7). A10 hoy muestra environments sin `deployment_branch_policy`, sin protection rules, `can_admins_bypass: true` y `main` sin branch protection. El veredicto sigue PENDIENTE.

- T4, B6, F1: aportar la evidencia indicada en cada fila (owner/CI, Convention Verification ownership).
- A10: el owner debe configurar en la UI deployment branches solo `main` en `dev` y `prod`, revisor requerido en `prod` con "Prevent self-review" desactivado, bypass de administradores desactivado (hoy `can_admins_bypass: true`) y branch protection de `main` con PR requerida (hoy 404). Después, repetir los tres `gh api` de A10.
- T3: la fila del plan no incluye `--config`; corregir el plan o `AGENTS.md` si ese es el comando canónico.
- Observación en P1: el plan dice que `docs/design/CONTEXT.md` no se toca y que no cambia nada fuera de Files Changed, pero el commit 9b70313 modifica `CONTEXT.md`, `CHANGELOG.md` y `foundations/context.md` (actualización de memoria de diseño). El orquestador decide si es deriva aceptable.
