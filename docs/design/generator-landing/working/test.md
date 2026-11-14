---
type: Test
---

# generator-landing: Registro de evidencia (en curso)

> **Estado:** En curso — evidencia por fase · **Fecha:** 2026-11-14 · **Plan:** docs/design/generator-landing/working/plan.md

Este archivo todavía no es el veredicto final de `reppit-test`: ese veredicto llega tras la Fase 10. Aquí se acumula la evidencia por fase. Lo que la Convention "Apply gate" impide ejecutar a los agentes se prueba con la salida que aporta el owner (Convention "Verification ownership").

## Evidencia por fase

| Fase | Id | Check | Comando / fuente | Resultado | Estado |
|------|----|-------|------------------|-----------|--------|
| 1 | TS-V1 | Tests del generador | `pytest generators/tests -q` (orquestador, 2026-11-13) | `28 passed` | PASS |
| 2 | (verify de la Fase 2) | Compose de Postgres resuelve | `docker compose -f docker/postgres/compose.yml config` (orquestador, 2026-11-13) | sin error | PASS |
| 3 | TS-A2 | Plan de PR-L (#8) con `-lock=false` | job de CI, run 43494752105 | plan-dev, plan-prod y static-checks pass | PASS |
| 4 | TS-A1 (PR-B1) | Static checks de PR-B1 (#10) | job `static-checks` de CI, run 43572417056 | plan-dev, plan-prod y static-checks pass; checkov sin hallazgos | PASS |
| 4 | TS-V2, TS-V3 (`bootstrap`) | fmt y validate de la Fase 4 | `terraform fmt -check -recursive infra/terraform` y `terraform -chdir=infra/terraform/bootstrap validate` (orquestador) | según el orquestador; salida literal no recogida en este archivo | PASS (sin salida literal) |
| 5 | TS-B1 | Plan del owner solo con create/update de la Fase 5; apply | `terraform -chdir=infra/terraform/bootstrap plan -out=b1.tfplan` y `apply b1.tfplan` (owner) | plan `7 to add, 2 to change, 0 to destroy`; `ci-apply` sin cambios; `Apply complete! Resources: 7 added, 2 changed, 0 destroyed.` | PASS |

Notas de la Fase 4: la PR-B1 es la #10. La fila TS-A1 cubre PR-B1; la de PR-M queda pendiente.

### Fase 5: salida del owner (literal)

Aportada por el owner (javiladino), 2026-11-14, desde `main` con la PR #10 fusionada, sesión `aws login` como `user/skyroute-dev`.

```text
$ terraform -chdir=infra/terraform/bootstrap init
Initializing the backend...
- Reusing version 6.73.0 of hashicorp/aws from the dependency lock file
Terraform has been successfully initialized!

$ terraform -chdir=infra/terraform/bootstrap plan -out=b1.tfplan
(extracto: cabeceras de recurso y resumen; el diff completo de políticas lo revisó el orquestador en la sesión)
  # aws_iam_policy.ci_boundary will be updated in-place
  # aws_iam_policy.workload_boundary_dev will be created
  # aws_iam_policy.workload_boundary_prod will be created
  # aws_iam_role.ci_apply_dev will be created
      sub = "repo:javiladino@97758532/skyroute@1455233709:environment:dev", aud = "sts.amazonaws.com", permissions_boundary = ci-boundary
  # aws_iam_role.ci_apply_prod will be created
      sub = "repo:javiladino@97758532/skyroute@1455233709:environment:prod", aud = "sts.amazonaws.com", permissions_boundary = ci-boundary
  # aws_iam_role_policy.ci_apply_dev will be created
  # aws_iam_role_policy.ci_apply_prod will be created
  # aws_iam_role_policy.ci_plan will be updated in-place
      Sid "StateLock" -> "PlanS3Metadata" (se retiran s3:GetObject/PutObject/DeleteObject sobre envs/{dev,prod}/terraform.tfstate.tflock)
      + PlanLambdaRead (lambda:GetFunction ... sobre function:skyroute-*-generator), + DenyDataObjectRead, + DenyLogRead
  # aws_s3_account_public_access_block.this will be created (4 bloqueos = true)
  aws_iam_role.ci_apply y aws_iam_role_policy.ci_apply: solo "Refreshing state", sin cambios.
Plan: 7 to add, 2 to change, 0 to destroy.

$ terraform -chdir=infra/terraform/bootstrap apply b1.tfplan
aws_iam_policy.workload_boundary_dev: Creating...
aws_iam_policy.workload_boundary_prod: Creating...
aws_s3_account_public_access_block.this: Creating...
aws_iam_policy.ci_boundary: Modifying... [id=arn:aws:iam::437266392155:policy/ci-boundary]
aws_iam_policy.workload_boundary_prod: Creation complete after 1s [id=arn:aws:iam::437266392155:policy/workload-boundary-prod]
aws_iam_policy.workload_boundary_dev: Creation complete after 1s [id=arn:aws:iam::437266392155:policy/workload-boundary-dev]
aws_iam_policy.ci_boundary: Modifications complete after 1s [id=arn:aws:iam::437266392155:policy/ci-boundary]
aws_iam_role.ci_apply_prod: Creating...
aws_iam_role.ci_apply_dev: Creating...
aws_iam_role_policy.ci_plan: Modifying... [id=ci-plan:ci-plan-backend]
aws_s3_account_public_access_block.this: Creation complete after 1s [id=437266392155]
aws_iam_role_policy.ci_plan: Modifications complete after 1s [id=ci-plan:ci-plan-backend]
aws_iam_role.ci_apply_dev: Creation complete after 1s [id=ci-apply-dev]
aws_iam_role_policy.ci_apply_dev: Creating...
aws_iam_role.ci_apply_prod: Creation complete after 1s [id=ci-apply-prod]
aws_iam_role_policy.ci_apply_prod: Creating...
aws_iam_role_policy.ci_apply_dev: Creation complete after 0s [id=ci-apply-dev:ci-apply-dev-backend]
aws_iam_role_policy.ci_apply_prod: Creation complete after 0s [id=ci-apply-prod:ci-apply-prod-backend]

Apply complete! Resources: 7 added, 2 changed, 0 destroyed.
```

Evidencia adicional (owner, `gh api`, 2026-11-13): `dev` y `prod` con `can_admins_bypass:false` y branch policy `main`; `prod` con `required_reviewers` javiladino (relacionado con TS-O5, que se repite al ejecutar `reppit-test`).

## Pendiente

Fase 5 (owner):
- TS-B2: `aws iam get-role --role-name ci-apply-dev` y `simulate-principal-policy` de `ci-apply-dev` con `s3:GetObject` sobre `envs/prod/terraform.tfstate` (esperado: un solo `sub` `...:environment:dev`; `implicitDeny`).
- TS-B3: `simulate-principal-policy` de `ci-apply-dev`, `iam:UpdateAssumeRolePolicy` sobre `ci-apply-prod` (esperado: `explicitDeny`).
- TS-B5: `simulate-principal-policy` de `ci-apply-dev` con `iam:CreateRole` y `iam:PermissionsBoundary` = `workload-boundary-prod`; luego `= workload-boundary-dev` sobre `role/workload/skyroute-dev-x`; `iam:PassRole` fuera de `role/workload/skyroute-dev-*` (esperado: `explicitDeny`; `allowed`; `explicitDeny`).
- TS-B6: `simulate-principal-policy` de `ci-plan`: `lambda:GetFunction`; `s3:GetObject` en `skyroute-prod-data-<id>/landing/x`; `lambda:GetFunctionConfiguration`; `s3:PutObject` del `.tflock` de dev (esperado según OQ10; con la opción por defecto, `allowed` solo sobre `function:skyroute-*-generator`).
- Verify de la Fase 5: `terraform -chdir=infra/terraform/bootstrap plan -detailed-exitcode` tras el apply, con código de salida 0.
- TS-B8 (`simulate-principal-policy` de `ci-apply-dev`, cinco acciones con `explicitDeny`): el plan la lista como owner; no se citó entre las pendientes de la Fase 5 pero sigue sin evidencia.

Fase 2 (executor, Docker local):
- TS-C3: `docker compose -f docker/postgres/compose.yml up -d` (tras `make env`), `make seed-postgres` y `docker compose -f docker/postgres/compose.yml exec postgres psql -U postgres -c "select count(*) from bookings"`; esperado conteo > 0. N/A si `docker info` falla.

Revisión:
- Campo email de los eventos consent: revisión pendiente (relación con TS-U4, PII). No tiene id TS propio en el plan.

Resto de checks según el plan:
- Verify y reglas de archivos: TS-V2 a TS-V6 (fmt, validate de dev, prod y bootstrap, tflint de dev y prod, diff de `docs/design/foundations` contra `b21c2f9`, `git diff --name-only b21c2f9`).
- Unit tests: TS-U1 a TS-U10 (cubiertos en conjunto por los 28 tests de TS-V1; falta la correspondencia fila por fila en el veredicto final).
- Behavior checks: TS-A1 para PR-M; TS-A2 para PR-M; TS-A3 en la PR-T1 (Fase 10).
- Fase 6: TS-W1 (run de `terraform-apply.yml` tras PR-W).
- Fase 8: TS-B7 (plan de destroy solo de `ci-apply` y `aws iam get-role --role-name ci-apply` con `NoSuchEntity`).
- TS-B4 (`grep -c` por Sid y archivo, tras la Fase 7).
- Fases 9 y 10: TS-C2, TS-C2b, TS-C4, TS-O1, TS-O2, TS-O3, TS-O4, TS-O5 (repetir), TS-O6; fecha D (OQ9) que registra el owner.
- Revisión de `adversarial-reviewer` y protected-test diff del veredicto final de `reppit-test`.
