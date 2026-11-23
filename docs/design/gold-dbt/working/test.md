---
type: Test
---

# gold-dbt: Test Report

> **Date:** 2026-11-23 · **Base:** main · **Plan:** docs/design/gold-dbt/working/plan.md

## Verdict: PENDING

Fase de implementación en curso; filas por fase; veredicto global pendiente hasta la fase 7.

Fase 0a: PASS (gate de 0b cumplido)

Fase 0b: PASS (O17 completo; deriva de la Lambda BUCKET_NAME resuelta en la PR #47)

Fase 0c: PASS (spike sobre bookings_eur; ventana de sessions en la fase 5)

## Checks

### Fase 0a (PR `bootstrap/`: `gold/*` en las boundaries y workgroup `skyroute-<env>-dbt`)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 0a.1 | Formato Terraform (V4) | plan.md Testing Strategy; ejecutó el orquestador, 2026-11-23 | `terraform fmt -check -recursive infra/terraform` | sin salida, código 0 | PASS |
| 0a.2 | Validate de bootstrap (V5) | plan.md Testing Strategy; orquestador, 2026-11-23 | `terraform -chdir=infra/terraform/bootstrap validate` | `Success! The configuration is valid.` | PASS |
| 0a.3 | tflint de bootstrap (V6) | plan.md Testing Strategy; orquestador, 2026-11-23 | `tflint --chdir=infra/terraform/bootstrap --config=$PWD/infra/terraform/.tflint.hcl` | sin salida, código 0 | PASS |
| 0a.4 | Revisión de seguridad del diff 0a | security-reviewer | revisión del diff de 0a | OK, sin hallazgos high ni medium; un low informativo: `gold/*` en `AllowLakehouseDelete` de prod, intencionado (S13) | PASS |
| 0a.5 | O1, plan del owner | plan.md O1; owner, 2026-11-23 | `terraform -chdir=infra/terraform/bootstrap plan -out=gold-0a.tfplan` | `Plan: 0 to add, 5 to change, 0 to destroy.` Solo `~ update in-place`: `aws_iam_policy.workload_boundary_dev` y `_prod` (`+ .../gold/*` en 3 statements S3 cada una; el Resource de Athena pasa de string a lista con `workgroup/skyroute-<env>` y `workgroup/skyroute-<env>-dbt`), `aws_iam_role_policy.ci_apply_dev` y `_prod` (Resource de Athena pasa a lista con `-dbt`) y `aws_iam_role_policy.ci_plan` (`PlanAthenaRead` con 4 workgroups). Ningún destroy ni replace | PASS |
| 0a.6 | O1, apply del owner | plan.md O1; owner, 2026-11-23, cuenta 437266392155 | `terraform -chdir=infra/terraform/bootstrap apply gold-0a.tfplan` | `Apply complete! Resources: 0 added, 5 changed, 0 destroyed.` | PASS |

Veredicto de fase 0a: PASS (gate de 0b cumplido).

Nota: las filas 0a.1 a 0a.3 las ejecutó el orquestador y las 0a.5 y 0a.6 el owner (Apply gate); este documento registra su evidencia tal como se aportó, no la reejecuta el ejecutor.

### Fase 0b (PR #45, módulo `lakehouse`: base gold, workgroup `skyroute-<env>-dbt` y rol `skyroute-<env>-local-dbt`)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 0b.1 | Formato Terraform (V) | plan.md Testing Strategy; orquestador, 2026-11-23 | `terraform fmt -check -recursive infra/terraform` | sin salida | PASS |
| 0b.2 | Validate de dev y prod (V) | plan.md Testing Strategy; orquestador, 2026-11-23 | `terraform -chdir=infra/terraform/envs/dev validate` y `terraform -chdir=infra/terraform/envs/prod validate` | `Success! The configuration is valid.` en los dos | PASS |
| 0b.3 | tflint del módulo lakehouse (V) | plan.md Testing Strategy; orquestador, 2026-11-23 | `tflint --chdir=infra/terraform/modules/lakehouse --config=$PWD/infra/terraform/.tflint.hcl` | sin salida | PASS |
| 0b.4 | Revisión de seguridad del módulo | security-reviewer | revisión del diff de 0b | Sin hallazgos sobre el módulo. Sus H1-H3 (boundary sin `gold/`) eran falsos positivos: leyó bootstrap desde `main` antes de fusionar la #43; el orquestador comprobó con `git grep` que la rama de la #43 tiene `gold/*` y `athena_workgroup_dbt` en las dos boundaries | PASS |
| 0b.5 | O2, apply de CI | plan.md O2; run 45165899617 de `terraform-apply` (merge de la #45, 2026-11-23) | apply de CI en dev y en prod | En dev y en prod: `Plan: 4 to add, 1 to change, 0 to destroy.` y `Apply complete! Resources: 4 added, 1 changed, 0 destroyed.` Los 4 adds son los esperados: `module.lakehouse.aws_athena_workgroup.dbt`, `aws_glue_catalog_database.layer["gold"]`, `aws_iam_role.local_dbt[0]` y `aws_iam_role_policy.local_dbt[0]`. El change es `module.generator_landing.aws_lambda_function.generator`, que vuelve a añadir `environment.variables.BUCKET_NAME`; no viene de 0b: ya aparecía igual en los applies de la #42 (run 45036663569) y de la #43 (run 45165802461), en dev y en prod. Deriva perpetua previa, registrada como deuda abierta | PASS (con nota) |
| 0b.6 | O17, parte S3 sobre silver | plan.md O17; owner, 2026-11-23 | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::437266392155:role/workload/skyroute-dev-local-dbt --action-names s3:PutObject s3:DeleteObject --resource-arns arn:aws:s3:::skyroute-dev-data-437266392155/silver/__o17_probe__/x` | `s3:PutObject` y `s3:DeleteObject`: `EvalDecision: explicitDeny`, MatchedStatements `role_skyroute-dev-local-dbt_local-dbt`, `AllowedByPermissionsBoundary: true` (deniega la inline aunque la boundary lo permita, como se quería) | PASS |
| 0b.7 | O17, resto (Glue sobre silver y S3 sobre landing y bronze) | plan.md O17; owner, 2026-11-23 | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::437266392155:role/workload/skyroute-dev-local-dbt --action-names glue:CreateTable glue:UpdateTable glue:DeleteTable --resource-arns arn:aws:glue:eu-west-3:437266392155:table/skyroute_dev_silver/__o17_probe__`; y `aws iam simulate-principal-policy ... --action-names s3:PutObject s3:DeleteObject --resource-arns .../landing/__o17_probe__/x .../bronze/__o17_probe__/x --query EvaluationResults[].ResourceSpecificResults[]` | Glue: `explicitDeny` en las 3 acciones (`glue:CreateTable`, `glue:UpdateTable`, `glue:DeleteTable`). S3: `explicitDeny` en las 4 combinaciones de acción y recurso (landing y bronze). Nota: la vista agregada por acción no basta con varios recursos, por eso se usó `ResourceSpecificResults` | PASS |

Veredicto de fase 0b: PASS (O17 completo; deriva de la Lambda BUCKET_NAME resuelta en la PR #47).

Nota: las filas 0b.1 a 0b.3 las ejecutó el orquestador, la 0b.5 la CI y la 0b.6 el owner; este documento registra su evidencia tal como se aportó, no la reejecuta el ejecutor.

### Fase 0c (spike de dbt-athena, rama `spike/gold-dbt-0c`, commit 4cfe307, resultados en `dbt/SPIKE.md`; la rama no se fusiona, la absorbe la fase 5)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 0c.1 | Parse y listado del proyecto (V7) | plan.md Testing Strategy; orquestador, 2026-11-23 | `.venv/bin/dbt parse --project-dir dbt --profiles-dir dbt/ci` y `dbt ls` | `dbt ls`: "Found 2 models, 1 test, 1 source" (`spike_bookings_table`, `spike_bookings_window`, `source silver.bookings_eur`, `window_matches_silver`). dbt-core 1.12.7, dbt-athena 1.11.2 | PASS |
| 0c.2 | Precondición: datos de silver para el spike | plan.md fase 0c; owner, 2026-11-23 | consulta de `skyroute_dev_silver.sessions` y de `skyroute_dev_silver.bookings_eur` | `skyroute_dev_silver.sessions` no existe (TABLE_NOT_FOUND); silver de dev solo tiene `bookings_eur` y `fx_daily`. Deriva frente al plan: el owner decidió reapuntar el spike a `bookings_eur` (2026-11-23); la ventana D-4..D de `sessions` queda para la fase 5. `bookings_eur`: `changed_at` entre 2026-11-20 y 2026-11-20, 132 filas | PASS (con deriva) |
| 0c.3 | Identidad del rol `local-dbt` | plan.md fase 0c; owner, 2026-11-23 | `sts get-caller-identity` y `dbt debug` con el perfil de `local-dbt` | Sin `mfa_serial` en el perfil, AssumeRole da AccessDenied porque la trust exige MFA. Con `mfa_serial = arn:aws:iam::437266392155:mfa/skyroute`, `sts get-caller-identity` muestra `assumed-role/skyroute-dev-local-dbt`. `dbt debug`: "All checks passed!" con el workgroup `skyroute-dev-dbt` y el schema `skyroute_dev_gold` | PASS |
| 0c.4 | Incremental: merge, pre_hook DELETE e incremental_predicates | plan.md fase 0c; owner, 2026-11-23 | 3 builds de `spike_bookings_window` y `window_matches_silver` con `run_date` 2026-11-20, 2026-11-20 y 2026-11-21 | Cada build: OK 132 y PASS=2 ERROR=0 | PASS |
| 0c.5 | Materialización table y full-refresh | plan.md fase 0c; owner, 2026-11-23 | `spike_bookings_table` dos veces; `--full-refresh` de `spike_bookings_window` | `spike_bookings_table`: OK 132 y PASS=1 las dos veces; `--full-refresh` de `spike_bookings_window`: OK 132 y PASS=2. Ningún AccessDenied, así que la tabla IAM de S5 queda vacía | PASS |
| 0c.6 | Idempotencia | plan.md fase 0c; owner, 2026-11-23 | `SELECT count(*), count(DISTINCT booking_id) FROM skyroute_dev_gold.spike_bookings_window` | `132, 132` | PASS |
| 0c.7 | Coste del spike | plan.md fase 0c; owner, 2026-11-23 | CloudWatch `ProcessedBytes` del workgroup `skyroute-dev-dbt` | Sum 45154 bytes y Maximum 4642 bytes, frente al corte de 100 MB | PASS |

Veredicto de fase 0c: PASS (spike sobre bookings_eur; ventana de sessions en la fase 5).

Nota: la fila 0c.1 la ejecutó el orquestador y las 0c.2 a 0c.7 el owner; este documento registra su evidencia tal como se aportó, no la reejecuta el ejecutor.

## Review

Fase 0a: security-reviewer OK. Un hallazgo low informativo (`gold/*` en `AllowLakehouseDelete` de prod): rechazado, es intencionado (S13). La review adversarial global sobre el diff completo queda pendiente hasta la fase 7.

## Follow-up

Filas de las fases 1 a 7 pendientes. Sin fallos ni diferidos en la fase 0a.

- Resuelto el 2026-11-23: la deriva de `BUCKET_NAME` venía del `Deny kms:Decrypt` de los roles de CI, que ocultaba las variables de entorno de la Lambda. Corregido en `bootstrap/` (PR #47, aplicado por el owner: 4 changed). El plan de CI de la #47 (run 45237668116) da `No changes` en dev y prod. Ver `findings.md`.
- `ci-boundary` queda en 6.068 de 6.144 caracteres: cualquier permiso nuevo de CI tiene que compactar algo o ir en otra boundary.
- fase 5: fijar `dbt-core==1.12.7` y `dbt-athena==1.11.2` en `requirements-dev.txt`.
- fase 5: añadir `dbt/ci/.user.yml` y `dbt/target/` y `dbt/logs/` a `.gitignore` si no lo están.
- runbooks: el perfil de `local-dbt` necesita `mfa_serial`.
- fase 5: probar la salida de filas de la ventana con varios días.
