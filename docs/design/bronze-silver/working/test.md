---
type: Test
---

# bronze-silver: Test Report

> **Fecha:** 2026-11-20 · **Base:** main (rama `infra/bronze-silver-bootstrap`) · **Plan:** docs/design/bronze-silver/working/plan.md

## Verdict: IN PROGRESS (fases 1, 1b, 2 y 3 en PASS; siguiente: fase 4)

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
| 2.x | CI plan de la PR #26 | plan.md Fase 2 (CI) | run 44809403791 (terraform-plan) | dev: "Plan: 9 to add, 2 to change, 0 to destroy". prod: "Plan: 7 to add, 2 to change, 0 to destroy", sin `skyroute-prod-local-data`. El refresh de `aws_ssm_parameter` no dio AccessDenied (enmienda de la PR #25 verificada). Los 2 change: el lifecycle del bucket (reglas athena-results 7 d y glue-temp 1 d, abort-multipart reordenada) y `aws_lambda_function.generator`, que añade la variable de entorno `BUCKET_NAME` (no estaba en el checklist; update in-place, sin impacto) | PASS |
| 2.y | Apply en main | plan.md Fase 2 (CI) | run 44809535857 (terraform-apply, merge de la PR #26) | success en dev y prod | PASS |
| 2.z | Gate de MFA con `aws login` | plan.md Fase 2 (owner) | `aws sts get-caller-identity --profile skyroute-dev-local-data` (source_profile `skyroute-dev-login` de `aws login`, mfa_serial `arn:aws:iam::437266392155:mfa/skyroute`) | Pidió el código MFA y devolvió Arn `arn:aws:sts::437266392155:assumed-role/skyroute-dev-local-data/botocore-session-1795254817` (owner, 2026-11-21). Confirma que el trust con MFA funciona con `aws login`, sin fallback | PASS |

## Fase 3: generador (bookings_history, export, FX del BCE)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 3.1 | Tests del generador | plan.md Fase 3 (executor) | `.venv/bin/python -m pytest generators/tests -q` | "52 passed" (re-ejecutado por el orquestador) | PASS |
| 3.2 | Lint | plan.md Fase 3 (executor) | `ruff check generators` con el `ruff.toml` del repo | "All checks passed!" | PASS |
| 3.3 | Tests preexistentes | plan.md Fase 3 (executor) | `git diff --stat generators/tests` | Solo `test_handler.py` cambia (wrap de línea por lint) | PASS |
| 3.4 | Fuente BCE | plan.md Fase 3 (executor) | URLs 90d e hist; parseo de `fx` | URL 90d e hist válidas, namespace `eurofxref`; FX 2025-07-01..2025-12-31 produce 184 archivos | PASS |
| 3.5 | G3 contra Postgres (reproducibilidad del historial) | plan.md Fase 3 (executor, 2026-11-21) | `make seed-postgres SEED_FROM=2026-05-01 SEED_TO=2026-05-03 REBUILD=1` dos veces (volumen recreado con `down -v`, init 002 aplicado), luego `SELECT count(*), max(history_id), md5(...) FROM bookings_history` y `len(replay_history("2026-05-01","2026-05-03"))` | Ejecución 1: count 578, max 578, md5 `ef80bc720701d6fa312f8f83b470aba7`. Ejecución 2: count 578, max 578, md5 `ef80bc720701d6fa312f8f83b470aba7`. `len(replay_history)` = 578 | PASS |
| 3.6 | Export real byte a byte (a vs b, y vs simulación) | plan.md Fase 3 (executor, 2026-11-21) | `make export-bookings RUN_DATE=2026-05-02 OUT_DIR=build/a` (y `build/b`), `cmp`; `build/sim_export.py` y `cmp` con `build/a` | Ejecutado por el owner con `PGPASSWORD` desde su `.env` (Verification ownership: salida aportada por el owner, 2026-11-21). `make export-bookings RUN_DATE=2026-05-02` con OUT_DIR=build/a y build/b: "part.json.gz (188 filas)" en ambas. `cmp` a vs b: IGUALES. `build/sim_export.py` (simulación con `replay_history`): 188 filas. `cmp` a vs `build/sim/part.json.gz`: IGUALES_SIM | PASS |

Nota de revisión: adversarial-reviewer dio GO-WITH-FIXES. Los hallazgos 2 a 6 están aplicados: FX exige publicación de D o publicación posterior; `ruff.toml`; docs de recorridos fuera de slot y de REBUILD; Makefile con `$(PY)`; test de `normalize`.

## Review

Pendiente: la review final de `adversarial-reviewer` sobre el diff completo corre al cerrar la última fase.

## Follow-up

- N1 y N2 (Low) de la ronda 2 de security-reviewer: aceptados, sin acción en la Fase 1.
