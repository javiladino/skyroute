---
type: Test
---

# bronze-silver: Test Report

> **Fecha:** 2026-11-20 · **Base:** main (rama `infra/bronze-silver-bootstrap`) · **Plan:** docs/design/bronze-silver/working/plan.md

## Verdict: IN PROGRESS (fase 1 y enmienda 1b en PASS; fase 2 en curso)

Fase 1 (PR #24, permisos de `bootstrap/`): PASS. Los checks estáticos, la review de seguridad, el plan del owner, el tamaño de `ci-boundary` y el apply del owner están en PASS. El veredicto no es PASS hasta cerrar las fases 2 a 8.

Las secciones de las fases siguientes se añaden debajo de esta, una por fase.

## Fase 1: PR de `bootstrap/` (permisos) — PASS

Éxito según plan: el plan solo cambia `ci-boundary`, `ci-plan`, `ci-apply-{dev,prod}` y `workload-boundary-{dev,prod}`; ningún `destroy`; `pass_role_services` incluye `glue.amazonaws.com`.

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 1.1 | Formato Terraform | plan.md Fase 1 (executor) | `terraform fmt -check -recursive infra/terraform` | exit 0 (executor; re-ejecutado por el orquestador 2026-11-20) | PASS |
| 1.2 | Validate de bootstrap | plan.md Fase 1 (executor) | `terraform -chdir=infra/terraform/bootstrap validate` | "Success! The configuration is valid." (re-ejecutado por el orquestador 2026-11-20) | PASS |
| 1.3 | tflint de bootstrap | plan.md Fase 1 (executor) | `tflint --chdir=infra/terraform/bootstrap --config=$PWD/infra/terraform/.tflint.hcl` | exit 0, sin hallazgos (executor) | PASS |
| 1.4 | Review de seguridad | plan.md Fase 1 (security-reviewer) | security-reviewer, 2 rondas | Ronda 1: H1 High (bases Glue compartidas) y H2 a H6, todos aplicados. Ronda 2: OK para re-aplicar; N1 y N2 (Low) aceptados | PASS |
| 1.5 | Plan del owner | plan.md Fase 1 (owner) | `terraform -chdir=infra/terraform/bootstrap plan -out=bootstrap.tfplan` | "Plan: 0 to add, 6 to change, 0 to destroy." (owner, 2026-11-20) | PASS |
| 1.6 | Tamaño de `ci-boundary` | plan.md Fase 1 (owner); gate "Tamaño de `ci-boundary`" | `python3 scripts/policy_size.py infra/terraform/bootstrap/bootstrap.tfplan` | "ci-boundary: 5890 caracteres minificados (limite 6144)" (owner, 2026-11-20; objetivo <= 6000) | PASS |
| 1.7 | Apply del owner | plan.md Fase 1 (owner); gate "Re-aplicar bootstrap" | `terraform -chdir=infra/terraform/bootstrap apply bootstrap.tfplan` | "Apply complete! Resources: 0 added, 6 changed, 0 destroyed." (owner, 2026-11-20); modificados: workload-boundary-dev, workload-boundary-prod, ci-boundary, ci-plan, ci-apply-dev, ci-apply-prod | PASS |

### Notas de la Fase 1

- La primera ejecución de `scripts/policy_size.py` falló porque `terraform show` corría fuera del directorio de bootstrap. Se corrigió en la misma PR: el script usa `-chdir` y sale con código 3 ante errores. El orquestador verificó la ruta de error.
- Un `terraform plan` sin guardar, ejecutado antes del apply, mostró el mismo "0 to add, 6 to change, 0 to destroy", y el diff coincidió con los cambios revisados: ARNs de Glue por entorno, PassRole solo a glue-job, DenyKmsDecrypt y DenyDataObjectRead con NotResource `scripts/*` + 2 tfstate.

## Fase 1b: enmienda de bootstrap (kms:Decrypt de CI acotado al parámetro HMAC, PR #25) — PASS

Motivo: terraform-provider-aws refresca `aws_ssm_parameter` con GetParameter `WithDecryption=true` incluso con `value_wo` (security-reviewer, a partir de `internal/service/ssm/parameter.go` en main).

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 1b.1 | Review de seguridad | security-reviewer | security-reviewer | OK para commit y re-apply; N4 (Deny explícito de kms:Decrypt en `ci-apply-<env>`) aplicado; N8 riesgo aceptado (el CI del repo puede leer la clave; las PR de forks no reciben token OIDC) | PASS |
| 1b.2 | Validate de bootstrap | orquestador | `terraform -chdir=infra/terraform/bootstrap validate` | Success (re-ejecutado por el orquestador) | PASS |
| 1b.3 | Plan del owner | owner, 2026-11-20 | `terraform -chdir=infra/terraform/bootstrap plan -out=bootstrap.tfplan` | "Plan: 0 to add, 4 to change, 0 to destroy." (ci-boundary, ci-apply-dev, ci-apply-prod, ci-plan; el diff coincidió con los Sids revisados) | PASS |
| 1b.4 | Tamaño de `ci-boundary` | owner, 2026-11-20 | `python3 scripts/policy_size.py infra/terraform/bootstrap/bootstrap.tfplan` (versión corregida del commit 3e3d984) | "ci-boundary: 5904 caracteres minificados (limite 6144)" | PASS |
| 1b.5 | Apply del owner | owner, 2026-11-20 | `terraform -chdir=infra/terraform/bootstrap apply bootstrap.tfplan` | "Apply complete! Resources: 0 added, 4 changed, 0 destroyed." | PASS |

Nota: la PR #24 se fusionó antes de que se subiera el commit 3e3d984 (corrección de `policy_size.py` y este `test.md`). El commit 3e3d984 se pasó con cherry-pick a `infra/bronze-silver-lakehouse` (como 2db63f6), así que llega a main con la PR 2.

## Fase 2: gate de MFA del owner

Gate: `aws sts get-caller-identity --profile skyroute-dev-local-data` con `skyroute-dev-local-data` ya creado. Éxito: devuelve `assumed-role/skyroute-dev-local-data/...`. Alternativa: `aws sts get-session-token` con MFA; si las dos fallan, enmienda del Ruling. Ninguna fase que use AWS desde local (4 en adelante) empieza sin este gate.

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 2.1 | MFA con `aws login` | plan.md Fase 2 (owner) | `aws sts get-caller-identity --profile skyroute-dev-local-data` | (sin ejecutar) | PENDING |

## Review

Pendiente: la review final de `adversarial-reviewer` sobre el diff completo corre al cerrar la última fase.

## Follow-up

- N1 y N2 (Low) de la ronda 2 de security-reviewer: aceptados, sin acción en la Fase 1.
