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
| 6 | TS-W1 (parcial) | Run de `terraform-apply.yml` tras PR-W (#11) con `ci-apply-dev` y `ci-apply-prod` | push a `main` (commit `aeb3e7d4b9f2face485afebb7db521ca88a2ee70`), run 43574299596 (https://github.com/javiladino/skyroute/actions/runs/43574299596), verificado por el orquestador con `gh run view`, 2026-11-14 | conclusión `success`; apply-dev y apply-prod verdes (citas literales en "Fase 6: salida del run") | PASS |
| 8 | TS-B7 | Segundo re-apply de `bootstrap/`: plan solo con destroy de `ci-apply` y su inline; apply; T17 cerrada | `terraform -chdir=infra/terraform/bootstrap plan -out=b2.tfplan` y `apply b2.tfplan` (owner, 2026-11-14, desde `main` e3eca43 con las PR #12 y #13 fusionadas) | plan `0 to add, 4 to change, 2 to destroy`; `Apply complete! Resources: 0 added, 4 changed, 2 destroyed.`; intento 1 no aplicado (citas literales en "Fase 8: salida del owner") | PASS |
| 9 | PC6 | Cuota de concurrencia de Lambda de la cuenta en eu-west-3 (L-B99A9384) | `aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region eu-west-3` (owner, 2026-11-14) | `"Value": 10.0`, `Adjustable: true`. AWS exige dejar 10 sin reservar: `reserved_concurrent_executions = 1` no se puede aplicar. Hallazgo que activa el Ruling Implement decisions (concurrencia, PC6): la Fase 9 se despliega sin concurrencia reservada y `bootstrap/` pide subir la cuota | HALLAZGO (no es PASS/FAIL) |
| 9 | TS-A1 (PR-M) | Static checks de PR-M (#15) | job `static-checks` de CI; primer run con checkov en CKV_AWS_300, CKV_AWS_297 y CKV_AWS_18; corrección en d9de3c6 (regla abort-incomplete-multipart sin filtro; skips 297 y 18 con motivo); PR fusionada en `main` 6373456 | primer run FAIL, corregido en d9de3c6; el run del segundo `static-checks` no se cita aquí. Cubre también PC4 (reglas de checkov que disparan de verdad) | PASS (tras corrección; sin id de run del segundo intento) |
| 9 | Fase 9 (apply) | Apply de PR-M en dev y prod | run `terraform-apply.yml` 43579110988 (https://github.com/javiladino/skyroute/actions/runs/43579110988), verificado por el orquestador con `gh run view --log`, 2026-11-14 | apply-dev y apply-prod (con aprobación del owner): `Apply complete! Resources: 19 added, 0 changed, 0 destroyed.` en ambos; sin `AccessDenied`; todos los ARN en eu-west-3 (citas en "Fase 9: salida (literal)") | PASS |
| 9 | PC1 | arm64 de Lambda en eu-west-3 | primer `apply-dev` (run 43579110988) | `aws_lambda_function.generator` creada con `Creation complete after 11s [id=skyroute-dev-generator]` en dev y creada también en prod | PASS |
| 9 | PC5 | Trust del Scheduler con `aws:SourceAccount` y `aws:SourceArn` del schedule group; trust de Lambda con `aws:SourceAccount` | `aws s3 ls s3://skyroute-prod-data-437266392155/landing/ --recursive` y `aws cloudwatch get-metric-statistics` (`Errors`, `AWS/Lambda`) (owner, 2026-11-14) | el Scheduler invocó la función y esta escribió `landing/clickstream/ingest_date=2026-11-14/slot=36/part.json.gz` con su rol; `Errors` Sum 0.0 | PASS |
| 9 | TS-O2 (parcial) | Primer micro-lote del schedule de prod (mitad del criterio de hecho: "el schedule añade micro-lotes") | mismo listado de `landing/` de PC5 (owner, 2026-11-14) | slot 36 (09:00 UTC) de 2026-11-14 escrito por el schedule de prod. `rate(15 minutes)` cuenta desde la creación del schedule (09:10:48 UTC): las invocaciones caen en :10/:25/:40/:55 y el handler redondea a slot; los slots 00-35 de 2026-11-14 no existen (anteriores al schedule). Faltan los dos `aws s3 ls` separados 30 min, lo de dev (ninguno) y `get-schedule` en ambos | PARCIAL (pendiente la comparación a 30 min y dev) |
| 9 | Cuota Lambda (PC6, trabajo paralelo, PR #14) | Re-apply de `bootstrap/` con `lambda_quota.tf` y estado de la solicitud | `terraform -chdir=infra/terraform/bootstrap plan` y `apply` (owner, 2026-11-14); `aws service-quotas list-requested-service-quota-change-history-by-quota` | plan `1 to add, 0 to change, 0 to destroy`; `aws_servicequotas_service_quota.lambda_concurrent_executions` (L-B99A9384, valor 1000, eu-west-3) `Creation complete after 1s [id=lambda/L-B99A9384]`; `Apply complete! Resources: 1 added, 0 changed, 0 destroyed.`. Solicitud: Status `CASE_OPENED`, CaseId 179464611900230, DesiredValue 1000, creada 2026-11-14T09:48:23+01:00. AWS aún no aprueba | PASS (re-apply); solicitud SIN VEREDICTO (CASE_OPENED; aprobación pendiente, PR-Q, Fase 11) |
| 9 | D (OQ9) | Fecha concreta de D | decisión del owner, 2026-11-14 | D = 2026-11-14. Backfill: 2026-05-16..2026-11-13, 182 × 96 = 17.472 objetos; TS-O1 con `verify_landing.py --d 2026-11-14` | REGISTRADA (owner) |

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

### Fase 6: salida del run (literal)

Run 43574299596 de `terraform-apply.yml`, lanzado por el push a `main` de la PR-W #11 fusionada (commit `aeb3e7d4b9f2face485afebb7db521ca88a2ee70`). Verificado por el orquestador con `gh run view`, 2026-11-14. Conclusión: `success`.

```text
Job apply-dev:
role-to-assume: arn:aws:iam::437266392155:role/ci-apply-dev
Authenticated as assumedRoleId AROAWLTY3URN7L4YKQ3ZX:GitHubActions
init: Successfully configured the backend "s3"!
apply: No changes. Your infrastructure matches the configuration.
Apply complete! Resources: 0 added, 0 changed, 0 destroyed.

Job apply-prod (con aprobación del owner):
role-to-assume: arn:aws:iam::437266392155:role/ci-apply-prod
Authenticated as assumedRoleId AROAWLTY3URNQ2QUSFVKU:GitHubActions
init: backend s3 configurado
apply: No changes.
Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
```

Nota: el `init` de ambos jobs avisa "Terraform has made some changes to the provider dependency selections recorded in the .terraform.lock.hcl file". No es bloqueante; se revisa al regenerar el lock en la Fase 9.

Nota sobre TS-W1: el `ListBucket` con condición `s3:prefix = envs/<env>/` de los roles nuevos bastó para `init` y `apply` con el state vacío. Es evidencia parcial; la completa llega con recursos en el state (Fase 9).

### Fase 8: salida del owner (literal)

```text
Fase 8 — salida aportada por el owner (javiladino), 2026-11-14, desde main e3eca43 (PRs #12 y #13 fusionadas).

Intento 1 (NO aplicado): plan "1 to add, 6 to change, 3 to destroy". aws_iam_policy.ci_boundary salía como replacement (-/+) porque la description cambiada en la PR-B2 (#12) es inmutable en IAM ("# forces replacement"); permissions_boundary de ci-plan, ci-apply-dev y ci-apply-prod salía "(known after apply)". El orquestador lo paró; el owner borró b2.tfplan. Corrección: PR #13 (description restaurada a "Permissions boundary de los roles de CI (ci-plan, ci-apply).").

Intento 2:
$ terraform -chdir=infra/terraform/bootstrap plan -out=b2.tfplan
  # aws_iam_policy.ci_boundary will be updated in-place   (quita role/ci-apply de DenyCiAndOidcChanges)
  # aws_iam_role.ci_apply will be destroyed                (trust sub = environment:dev y environment:prod; causa de T17)
  # aws_iam_role_policy.ci_apply will be destroyed
  # aws_iam_role_policy.ci_apply_dev will be updated in-place   (quita role/ci-apply de DenyCiAndOidcChanges)
  # aws_iam_role_policy.ci_apply_prod will be updated in-place  (idem)
  # aws_iam_role_policy.ci_plan will be updated in-place        (idem)
  Sin replacement; permissions_boundary de los roles sin cambios.
Plan: 0 to add, 4 to change, 2 to destroy.

$ terraform -chdir=infra/terraform/bootstrap apply b2.tfplan
aws_iam_role_policy.ci_apply: Destroying... [id=ci-apply:ci-apply-backend]
aws_iam_role_policy.ci_apply: Destruction complete after 0s
aws_iam_role.ci_apply: Destroying... [id=ci-apply]
aws_iam_role.ci_apply: Destruction complete after 0s
aws_iam_policy.ci_boundary: Modifying... [id=arn:aws:iam::437266392155:policy/ci-boundary]
aws_iam_policy.ci_boundary: Modifications complete after 1s [id=arn:aws:iam::437266392155:policy/ci-boundary]
aws_iam_role_policy.ci_plan: Modifying... [id=ci-plan:ci-plan-backend]
aws_iam_role_policy.ci_apply_dev: Modifying... [id=ci-apply-dev:ci-apply-dev-backend]
aws_iam_role_policy.ci_apply_prod: Modifying... [id=ci-apply-prod:ci-apply-prod-backend]
aws_iam_role_policy.ci_plan: Modifications complete after 0s [id=ci-plan:ci-plan-backend]
aws_iam_role_policy.ci_apply_dev: Modifications complete after 0s [id=ci-apply-dev:ci-apply-dev-backend]
aws_iam_role_policy.ci_apply_prod: Modifications complete after 1s [id=ci-apply-prod:ci-apply-prod-backend]

Apply complete! Resources: 0 added, 4 changed, 2 destroyed.

Resultado: T17 cerrada (ya no existe ningún rol de apply con trust dev+prod). Fase 7 en código: PR-B2 #12 (556c1c6) + fix #13 (f412faa).
```

### PC6: cuota de concurrencia (valor aportado por el owner)

Owner (javiladino), 2026-11-14: cuota L-B99A9384 en eu-west-3 con `"Value": 10.0` y `Adjustable: true`. Activa el Ruling Implement decisions (owner javiladino, 2026-11-14), línea "Concurrencia (PC6)": Fase 9 sin `reserved_concurrent_executions`, solicitud de cuota a 1.000 desde `bootstrap/` y PR-Q posterior. Detalle en `working/plan.md`.

### Fase 9: salida (literal)

```text
Fase 9 — evidencia (2026-11-14)

PR-M #15 (a9f386e + fix checkov d9de3c6), fusionada en main 6373456. Primer static-checks: checkov falló en CKV_AWS_300, CKV_AWS_297 y CKV_AWS_18; se corrigió en d9de3c6 (regla abort-incomplete-multipart sin filtro; skips 297 y 18 con motivo). Revisión previa: security-reviewer (Opus) "listo con fixes" (secret ALARM_EMAIL y alarma de ConcurrentExecutions aplicados), cost-guard (Sonnet) aprobado.

Run terraform-apply 43579110988 (https://github.com/javiladino/skyroute/actions/runs/43579110988), verificado por el orquestador con gh run view --log:
- apply-dev: "Authenticated as assumedRoleId AROAWLTY3URN7L4YKQ3ZX:GitHubActions"; recursos creados (extracto): aws_lambda_function.generator "Creation complete after 11s [id=skyroute-dev-generator]", aws_scheduler_schedule.generator "[id=default/skyroute-dev-generator]", aws_s3_bucket.data "[id=skyroute-dev-data-437266392155]", alarmas skyroute-dev-generator-concurrency y skyroute-dev-generator-invocations, aws_sns_topic_subscription.email; "Apply complete! Resources: 19 added, 0 changed, 0 destroyed."
- apply-prod (con aprobación del owner): "Authenticated as assumedRoleId AROAWLTY3URNQ2QUSFVKU:GitHubActions"; los mismos 19 recursos con prefijo skyroute-prod; "Apply complete! Resources: 19 added, 0 changed, 0 destroyed."
- Sin AccessDenied en ninguno de los dos jobs.
=> PC1 (arm64 en eu-west-3): PASS (función creada en ambos entornos). Region: todos los ARN en eu-west-3.

Salida del owner (2026-11-14):
$ aws s3 ls s3://skyroute-prod-data-437266392155/landing/ --recursive --profile skyroute-dev
2026-11-14 10:11:35       2217 landing/clickstream/ingest_date=2026-11-14/slot=36/part.json.gz
$ aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Errors --dimensions Name=FunctionName,Value=skyroute-prod-generator --start-time 2026-11-14T09:00:00Z --end-time 2026-11-14T12:00:00Z --period 3600 --statistics Sum --region eu-west-3 --profile skyroute-dev
  Datapoints: Timestamp 2026-11-14T10:00:00+01:00, Sum 0.0
=> PC5 (trust del Scheduler con SourceAccount + SourceArn del schedule group, y trust de Lambda con SourceAccount): PASS — el Scheduler invocó la función y la función escribió en landing/ con su rol; Errors = 0.
=> Primer micro-lote del schedule de prod: slot 36 (09:00 UTC) de 2026-11-14 (mitad del criterio de hecho: "el schedule añade micro-lotes").
Nota: rate(15 minutes) cuenta desde la creación del schedule (09:10:48 UTC); las invocaciones caen en :10/:25/:40/:55 y el handler redondea a slot; los slots 00-35 de 2026-11-14 no existen (anteriores al schedule).

D (OQ9) confirmada por el owner: 2026-11-14. Backfill: 2026-05-16..2026-11-13, 182 × 96 = 17.472 objetos; TS-O1 con verify_landing.py --d 2026-11-14.

Cuota de Lambda (trabajo paralelo, PR #14):
- Re-apply de bootstrap del owner: plan "1 to add, 0 to change, 0 to destroy" (aws_servicequotas_service_quota.lambda_concurrent_executions, L-B99A9384, value 1000, eu-west-3); apply "Creation complete after 1s [id=lambda/L-B99A9384]", "Apply complete! Resources: 1 added, 0 changed, 0 destroyed."
- list-requested-service-quota-change-history-by-quota: Status "CASE_OPENED", CaseId 179464611900230, DesiredValue 1000, Created 2026-11-14T09:48:23+01:00. Pendiente de aprobación por AWS (PR-Q, Fase 11).
```

## Pendiente

Hechos en la Fase 9 (ver filas de "Evidencia por fase"): PC1, PC5, PC4, subida de cuota aplicada (re-apply 1/0/0) y D registrada (2026-11-14). Siguen abiertos:
- Cuota: la solicitud está en `CASE_OPENED`; el owner aporta la cuota aprobada (comando de PC6) cuando AWS la apruebe. Después, PR-Q (Fase 11) y TS-C2c.
- TS-A3 y PC3 (PR-T1, Fase 10): primer plan de PR con la función y el bucket en el state; ahí también OQ10 y TS-W1 completa.
- TS-O1 (backfill, Fase 10): D = 2026-11-14, rango 2026-05-16..2026-11-13 (182 × 96 = 17.472), `verify_landing.py --d 2026-11-14`, dentro de los 30 días.
- TS-O2: falta la segunda mitad (dos `aws s3 ls` separados 30 min en prod y dev, `get-schedule` `ENABLED` en prod y `DISABLED` en dev).
- TS-C4: invocación manual de un slot en dev y `aws s3 ls` de `landing/`; sigue sin evidencia.
- TS-C2 (arm64 en `get-function-configuration`, `Timeout = 60`, `MemorySize = 256`), TS-C2b, TS-O3, TS-O4 (suscripción SNS) y TS-O6 (retención 14 días): sin evidencia aún.
- PC7 (zip real de `archive_file`): sin evidencia aún.

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
- Behavior checks: TS-A1 para PR-M ya registrada (Fase 9); TS-A2 para PR-M; TS-A3 en la PR-T1 (Fase 10).
- Fase 6: TS-W1 parcial. Run 43574299596 (apply-dev y apply-prod verdes con los roles nuevos, state vacío; ver "Fase 6: salida del run"). Falta la evidencia completa con recursos en el state (Fase 9).
- Fase 8: TS-B7 (plan de destroy solo de `ci-apply` y `aws iam get-role --role-name ci-apply` con `NoSuchEntity`).
- TS-B4 (`grep -c` por Sid y archivo, tras la Fase 7).
- Fases 9 y 10: TS-C2, TS-C2b, TS-C4, TS-O1, TS-O2, TS-O3, TS-O4, TS-O5 (repetir), TS-O6. La fecha D (OQ9) ya está registrada: 2026-11-14.
- Revisión de `adversarial-reviewer` y protected-test diff del veredicto final de `reppit-test`.
