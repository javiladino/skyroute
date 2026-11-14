---
type: Test
---

# generator-landing: Test Report

> **Date:** 2026-11-14 · **Base:** b14fdb59533f26b7c9f4314ff0ad3c8e39be9e81 (merge de la PR #6) · **Plan:** docs/design/generator-landing/working/plan.md

## Verdict: PENDIENTE

Los checks locales (pytest, fmt, validate, tflint, greps, diffs protegidos), los de GitHub y la evidencia del owner de hoy están en PASS; ninguno en FAIL. El veredicto no es PASS porque falta exactamente una cosa: el hallazgo 1 de la revisión (hueco del día D): backfill `{"from":"2026-11-14","to":"2026-11-14"}` desde 2026-11-15 y `KeyCount` de `ingest_date=2026-11-14` = 96 (la fila REV sigue PENDIENTE hasta entonces). TS-C3 y la comprobación de Postgres con datos son N/A porque `docker info` falla (el daemon no corre). PR-Q (Fase 11) y TS-C2c van como Follow-up.

Convención de la columna Result: "sesión" = comando ejecutado en esta sesión de Test (2026-11-14); "owner" o "CI run N" = evidencia literal ya registrada en el anexo "Evidencia (literal)".

## Checks

### Verify, archivos protegidos y reglas de archivos

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| TS-V1 | Tests del generador, 0 skips | plan.md TS-V1; AGENTS.md | `<venv>/bin/python -m pytest generators/tests -q` | sesión: `28 passed in 9.70s`, exit 0 | PASS |
| TS-V1b | Archivo protegido `owner_user.tf` sin cambios (Convention Bootstrap identity) | plan.md | `git diff b14fdb59533f26b7c9f4314ff0ad3c8e39be9e81 -- infra/terraform/bootstrap/owner_user.tf` | sesión: salida vacía | PASS |
| TS-V1c | Tests protegidos: solo altas, ninguna modificación (no había tests antes de la base) | plan.md | `git diff b14fdb59533f26b7c9f4314ff0ad3c8e39be9e81 --stat -- generators/tests` | sesión: 5 archivos, `287 insertions(+)`, 0 deletions (test_determinism, test_handler, test_keys, test_package, test_verify_landing) | PASS |
| TS-V2 | fmt | plan.md | `terraform fmt -check -recursive infra/terraform` | sesión: sin salida, exit 0 | PASS |
| TS-V3 | validate de bootstrap, envs/dev y envs/prod (con `.terraform/` existente) | plan.md | `terraform -chdir=infra/terraform/<bootstrap\|envs/dev\|envs/prod> validate` | sesión: `Success! The configuration is valid.` en los tres | PASS |
| TS-V4 | tflint de envs/dev y envs/prod | plan.md | `tflint --chdir=infra/terraform/envs/<dev\|prod> --config=$PWD/infra/terraform/.tflint.hcl` | sesión: sin hallazgos en ambos | PASS |
| TS-V5 | `docs/design/foundations` no se toca | plan.md | `git diff --stat b21c2f9 -- docs/design/foundations` | sesión: salida vacía | PASS |
| TS-V6 | Archivos cambiados solo los de Files Changed más `docs/design/generator-landing/` | plan.md | `git diff --name-only b21c2f9` | sesión: 46 rutas; todas en Files Changed salvo `docs/design/CONTEXT.md`, `docs/design/CHANGELOG.md` y `docs/design/generator-landing/context.md`/`working/*` (cierre de sesión de design-memory, no código). `.tflint.hcl`, `owner_user.tf` y `docs/design/foundations` no aparecen | PASS (con nota: CONTEXT.md y CHANGELOG.md están fuera de `generator-landing/`; los exige el cierre de sesión) |
| TS-R1 | `reserved_concurrent_executions` ausente del módulo (Ruling Implement decisions, PC6) | Ruling | `grep -rn "reserved_concurrent_executions" infra/terraform/modules` | sesión: salida vacía | PASS |
| TS-R2 | Workflows sin `vars.ALARM_EMAIL` | Ruling (secret, no variable) | `grep -rn "vars.ALARM_EMAIL" .github/workflows` | sesión: salida vacía | PASS |

### Behavior checks de AGENTS.md (CI)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| TS-A1 | `static-checks` (checkov + tflint) verde en PR-B1 y PR-M | plan.md TS-A1 | job `static-checks` de CI | PR-B1 (#10): owner/orquestador, run 43572417056, checkov sin hallazgos. PR-M (#15): primer run FAIL (CKV_AWS_300, 297, 18), corregido en d9de3c6; sesión: `gh pr checks 15 --repo javiladino/skyroute` da `static-checks pass 34s` (run 43578985348) | PASS |
| TS-A2 | Plan de PR-L (#8) y PR-M (#15) `OK` en dev y prod, sin AccessDenied | plan.md TS-A2 | job de CI | PR-L: run 43494752105, plan-dev, plan-prod y static-checks pass. Hallazgo 4 de la revisión (Fase 3): se quitó `-lock-timeout=60s` de `terraform plan ... -lock=false` en `.github/workflows/terraform-plan.yml` (no aplica con `-lock=false`); sesión: `grep -n "lock-timeout" .github/workflows/terraform-plan.yml` sin coincidencias y `grep -n "terraform plan -input=false -no-color -lock=false" ...` da 1 coincidencia (línea 65). FIXED en esta rama; su run de CI llega con la PR de esta rama. PR-M: sesión: `gh pr checks 15` da `plan-dev pass 26s`, `plan-prod pass 26s` (run 43578985348) | PASS |
| TS-A3 | Plan de PR-T1 (#16) con función y bucket en el state, sin AccessDenied | plan.md TS-A3 | job de CI | run 43579984929 tras PR #17: prod `Plan: 0 to add, 1 to change, 0 to destroy.` (`timeout = 60 -> 300`), refresh de 23 recursos sin AccessDenied; dev `No changes.` Primer intento falló por AccessDenied (SNS/Lambda), corregido con PR #17 | PASS (tras corrección, PR #17) |

### Unit tests (`generators/tests/`)

Cada fila se corresponde con el test indicado, recogido por `pytest --collect-only -q` (28 tests) y pasado en la ejecución TS-V1 de esta sesión.

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| TS-U1 | `generate` dos veces da los mismos bytes | plan.md | `pytest generators/tests/test_determinism.py` | `test_ts_u1_same_bytes_twice` pasa (sesión, dentro de los 28) | PASS |
| TS-U2 | Mismo resultado con `PYTHONHASHSEED=0` y `=1` | plan.md | idem | `test_ts_u2_same_bytes_across_hashseeds` pasa | PASS |
| TS-U3 | `booking_id` de cada `purchase` existe en `rows_for_day` | plan.md | `pytest generators/tests/test_keys.py` | `test_ts_u3_purchase_booking_ids_exist_in_rows` pasa | PASS |
| TS-U4 | Email `^u[0-9a-f]{12}@example\.com$`, sin campos PII | plan.md | idem | `test_ts_u4_email_format_and_no_pii_fields` pasa. Los eventos `consent` (campo email) siguen con revisión pendiente (ver Follow-up) | PASS |
| TS-U5 | `slot_from_scheduled_time` (10:14:59Z da slot 40; 10:15:00Z da 41) | plan.md | `pytest generators/tests/test_handler.py` | `test_ts_u5_slot_from_scheduled_time` pasa | PASS |
| TS-U6 | Backfill D-182..D-1: 17.472 claves, ninguna con `run_date >= D` | plan.md | idem | `test_ts_u6_backfill_182_days` pasa | PASS |
| TS-U7 | Backfill con `to >= hoy` falla sin escribir | plan.md | idem | `test_ts_u7_backfill_to_today_or_future_fails_without_writing` pasa | PASS |
| TS-U8 | Reinvocar el mismo slot da misma clave y mismos bytes | plan.md | idem | `test_ts_u8_redelivery_same_key_same_bytes` pasa | PASS |
| TS-U9 | `import lambda_handler` solo con `generators/` en `PYTHONPATH`; excluidos no importados | plan.md | `pytest generators/tests/test_package.py` | `test_ts_u9_handler_imports_like_lambda` pasa | PASS |
| TS-U10 | `verify_landing`: 0 faltantes/0 sobrantes, nombra la que falta o sobra, ignora `>= D` | plan.md | `pytest generators/tests/test_verify_landing.py` | 5 tests pasan (`test_ts_u10_complete_listing_has_no_diff`, `missing_key`, `extra_key`, `keys_from_d_onward_are_ignored`, `main_exit_codes`) | PASS |

### Integration y evidencia por criterio (plan.md § Integration Tests)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| TS-C3 | Postgres local sembrado, conteo de `bookings` > 0 | plan.md TS-C3 | `docker compose -f docker/postgres/compose.yml up -d`; `make seed-postgres`; `docker compose ... exec postgres psql -U postgres -c "select count(*) from bookings"` | sesión: `docker info` falla (`failed to connect to the docker API at unix:///Users/javierladino/.orbstack/run/docker.sock ... no such file or directory`, exit 1); el daemon no corre | N/A |
| TS-C3b | Compose de Postgres resuelve y publica solo `127.0.0.1:5433` (no necesita daemon) | plan.md Fase 2 verify | `docker compose -f docker/postgres/compose.yml config` | sesión: sin error; `host_ip: 127.0.0.1`, `published: "5433"`, `target: 5432`, `postgres:18.7`, volumen `/var/lib/postgresql` | PASS |
| TS-B1 | Plan de Fase 5 solo con create/update; 0 destroy | plan.md TS-B1 | `terraform -chdir=infra/terraform/bootstrap plan -out=b1.tfplan` y `apply` | owner 2026-11-14: `Plan: 7 to add, 2 to change, 0 to destroy.`; `Apply complete! Resources: 7 added, 2 changed, 0 destroyed.` | PASS |
| TS-B2 | `ci-apply-dev` con un solo `sub` dev; `implicitDeny` sobre el state de prod | plan.md TS-B2 | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::437266392155:role/ci-apply-dev` con `s3:GetObject` y `s3:PutObject` sobre `.../envs/prod/terraform.tfstate` | owner 2026-11-14: `implicitDeny` / `implicitDeny` (el `sub` único de dev consta en el plan de TS-B1) | PASS |
| TS-B3 | `ci-apply-dev` no puede cambiar el trust de `ci-apply-prod` | plan.md TS-B3 | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::437266392155:role/ci-apply-dev --action-names iam:UpdateAssumeRolePolicy iam:PutRolePolicy --resource-arns arn:aws:iam::437266392155:role/ci-apply-prod` | owner 2026-11-14: `explicitDeny` / `explicitDeny` | PASS |
| TS-B4 | Cada Sid aparece el número de veces de la tabla, por archivo | plan.md TS-B4 | `grep -c 'Sid *= *"<Sid>"' ci_roles.tf ci_apply_dev.tf ci_apply_prod.tf` (13 Sid, una llamada por Sid con los tres archivos) | sesión (ci_roles/dev/prod): DenyOwnerIdentity 2/1/1; DenyCiAndOidcChanges 2/1/1; DenyCreateRoleWithoutBoundary 2/1/1; DenyRoleWritesOutsideWorkload 2/1/1; DenyPassRoleWrongService 2/1/1; DenyDeleteBoundary 2/1/1; DenyBoundaryPolicyChanges 2/1/1; DenyStateBucketProtectionChanges 2/1/1; DenyAttachRolePolicy 1/1/1; DenyLambdaUrlAndPermission 1/1/1; DenyAttachCrossEnvBoundary 0/1/1; DenyNonEmailSnsSubscribe 1/1/1; DenyLogRead 2/0/0. Coincide con la tabla | PASS |
| TS-B5 | Boundary por entorno: `CreateRole` con boundary prod, con boundary dev; `PassRole` fuera de `workload` | plan.md TS-B5 | tres `aws iam simulate-principal-policy` de `ci-apply-dev` (`iam:CreateRole` sobre `role/workload/skyroute-dev-x` con `iam:PermissionsBoundary` = `workload-boundary-prod` y luego `workload-boundary-dev`; `iam:PassRole` sobre `role/workload/skyroute-dev-generator-exec` con `iam:PassedToService=ec2.amazonaws.com`) | owner 2026-11-14: `explicitDeny`; `allowed`; `explicitDeny` | PASS |
| TS-B6 | `ci-plan`: `lambda:GetFunction` (allowed solo sobre `function:skyroute-*-generator`), `s3:GetObject` en `landing/x` deny, `GetFunctionConfiguration`, `PutObject` del `.tflock` dev `implicitDeny` | plan.md TS-B6 | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::437266392155:role/ci-plan --action-names <cada acción> --resource-arns <recurso de cada caso>` | owner 2026-11-14: `lambda:GetFunction` y `GetFunctionConfiguration` sobre `function:skyroute-prod-generator` `allowed` / `allowed`; `s3:GetObject` sobre `skyroute-prod-data-437266392155/landing/x` `explicitDeny`; `s3:PutObject` sobre `envs/dev/terraform.tfstate.tflock` `implicitDeny`. Coherente con el plan de CI (run 43579984929) | PASS |
| TS-B7 | Fase 8: plan solo con destroy de `ci-apply` y su inline; `get-role ci-apply` da `NoSuchEntity` | plan.md TS-B7 | `terraform ... plan -out=b2.tfplan`/`apply`; `aws iam get-role --role-name ci-apply` | owner 2026-11-14: plan `0 to add, 4 to change, 2 to destroy`, `Apply complete! Resources: 0 added, 4 changed, 2 destroyed.`; `get-role`: `An error occurred (NoSuchEntity) when calling the GetRole operation: The role with name ci-apply cannot be found.` | PASS |
| TS-B8 | `ci-apply-dev`: cinco acciones con `explicitDeny` (`iam:AttachRolePolicy`; `lambda:CreateFunctionUrlConfig`, `UpdateFunctionUrlConfig`, `AddPermission`; `iam:CreateRole` sin boundary) | plan.md TS-B8 | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::437266392155:role/ci-apply-dev` con `lambda:CreateFunctionUrlConfig`, `UpdateFunctionUrlConfig`, `AddPermission` sobre `function:skyroute-dev-generator` e `iam:AttachRolePolicy` sobre `role/workload/skyroute-dev-generator-exec` | owner 2026-11-14: `explicitDeny` en las tres de Lambda y en `AttachRolePolicy`. `iam:CreateRole` sin boundary: sin salida propia (el deny por boundary de TS-B5a cubre el mismo Sid `DenyCreateRoleWithoutBoundary`, contado en TS-B4) | PASS (cuatro de cinco acciones con salida; la quinta, sin boundary, queda cubierta por TS-B4 y TS-B5a) |
| TS-W1 | `apply-dev` y `apply-prod` verdes con los roles nuevos; `s3:prefix = envs/<env>/` no rompe `init` | plan.md TS-W1 | runs de `terraform-apply.yml` | run 43574299596 (PR-W, state vacío): success, init y apply sin error. Con recursos en el state: run 43579110988 (19 recursos creados en dev y prod) y run 43587443950 (apply de PR-T1, success), sin AccessDenied | PASS |
| TS-C2 | Función de prod: `Architectures = [arm64]`, `Timeout = 60`, `MemorySize = 256` | plan.md TS-C2 | `aws lambda get-function-configuration --function-name skyroute-prod-generator --region eu-west-3 --query '{Arch:Architectures,Timeout:Timeout,Mem:MemorySize}'` | owner 2026-11-14 (tras la PR-T2 #18): `Arch ["arm64"]`, `Timeout 60`, `Mem 256`; `--query Timeout` solo da `60` | PASS |
| TS-C2b | `RetryPolicy` 2 / 900 en el schedule de prod | plan.md TS-C2b | `aws scheduler get-schedule --name skyroute-prod-generator --region eu-west-3 --query Target.RetryPolicy` | owner 2026-11-14: `{"MaximumEventAgeInSeconds": 900, "MaximumRetryAttempts": 2}` | PASS |
| TS-C2c | `ReservedConcurrentExecutions = 1` | plan.md TS-C2c; condicionado a la PR-Q | `aws lambda get-function-concurrency --function-name skyroute-prod-generator --region eu-west-3` | no aplica hasta la PR-Q (Fase 11); ver Follow-up. La ausencia de `reserved_concurrent_executions` en el módulo está comprobada en TS-R1 | N/A (Follow-up PR-Q) |
| TS-C4 | Invocación manual de un slot en dev deja `clickstream/ingest_date=.../slot=.../part.json.gz` | plan.md TS-C4 | `aws lambda invoke --function-name skyroute-dev-generator --region eu-west-3 --cli-binary-format raw-in-base64-out --payload '{"scheduled_time":"2026-11-14T10:14:59Z"}' /tmp/c4.json` y luego `aws s3 ls s3://skyroute-dev-data-437266392155/landing/ --recursive` | owner 2026-11-14: `StatusCode 200`; `{"objects": 1, "key": "landing/clickstream/ingest_date=2026-11-14/slot=40/part.json.gz"}`; el listado muestra `2026-11-14 12:30:30       1973 landing/clickstream/ingest_date=2026-11-14/slot=40/part.json.gz` (único objeto) | PASS |
| TS-O1 | 182 × 96 = 17.472 objetos, sin faltantes ni sobrantes, con D = 2026-11-14 | plan.md TS-O1 | `aws s3api list-objects-v2 ... --prefix landing/clickstream/` y `python3 generators/verify_landing.py --listing ... --d 2026-11-14` | owner 2026-11-14: `days` 182, `objects_in_range` 17472, `days_not_96` `{}`, `missing` `[]`, `extra` `[]` | PASS |
| TS-O2a | El schedule de prod añade micro-lotes consecutivos | plan.md TS-O2 | `aws s3 ls s3://skyroute-prod-data-437266392155/landing/clickstream/ingest_date=2026-11-14/ --recursive` | owner 2026-11-14: 9 slots consecutivos (36 a 44), uno cada 15 min, sin huecos | PASS |
| TS-O2b | `get-schedule` State: ENABLED en prod, DISABLED en dev | plan.md TS-O2; proposal Validation 14 | `aws scheduler get-schedule --name skyroute-prod-generator --region eu-west-3 --query State` y `aws scheduler get-schedule --name skyroute-dev-generator --region eu-west-3 --query State` | owner 2026-11-14: prod `"ENABLED"`, dev `"DISABLED"` | PASS |
| TS-O2c | dev no recibe micro-lotes: `landing/` de dev vacío | plan.md TS-O2 | `aws s3 ls s3://skyroute-dev-data-437266392155/landing/ --recursive` (descontando la invocación manual de TS-C4) | owner 2026-11-14: `landing/` de dev sin objetos previos; el único objeto es el que creó TS-C4 (`slot=40`) | PASS |
| TS-O3 | Alarma `skyroute-prod-generator-invocations`: umbral de OQ3 y acción al topic SNS | plan.md TS-O3 | `aws cloudwatch describe-alarms --alarm-name-prefix skyroute-prod-generator --region eu-west-3` | owner 2026-11-14: `skyroute-prod-generator-concurrency` en `OK`; `skyroute-prod-generator-invocations` en `ALARM` (esperado: el backfill superó 120 invocaciones/h; prueba que la alarma dispara). La salida registrada no cita umbral ni acción SNS literal | PASS (con nota: umbral y acción al topic sin salida literal) |
| TS-O4 | Suscripción SNS confirmada (sin `PendingConfirmation`) | plan.md TS-O4 | `aws sns list-subscriptions-by-topic --topic-arn <arn de skyroute-prod-alarms> --region eu-west-3` | owner 2026-11-14: `skyroute-prod-alarms` -> `["PendingConfirmation"]`; `skyroute-dev-alarms` -> `["PendingConfirmation"]`. Después el owner confirmó por email las dos suscripciones (2026-11-14); páginas "Subscription confirmed!" con ids `arn:aws:sns:eu-west-3:437266392155:skyroute-dev-alarms:ed3fcd6c-1a1a-4987-b968-13baa07535e3` y `arn:aws:sns:eu-west-3:437266392155:skyroute-prod-alarms:c5348778-bd4a-4227-b4e3-fcf3efffaad8`, en los topics que creó el apply de la PR-M (run 43579110988). No se repitió `list-subscriptions-by-topic` tras confirmar | PASS |
| TS-O5 | Environments de GitHub: `prod` con `required_reviewers` y una branch policy `main`; `dev` con `can_admins_bypass:false` y una branch policy `main` | plan.md TS-O5 | `gh api repos/javiladino/skyroute/environments/prod` y `.../dev` (más `deployment-branch-policies`) | sesión: prod `can_admins_bypass:false`, `custom_branch_policies:true`, reglas `branch_policy` y `required_reviewers` [javiladino], `prevent_self_review:false`, políticas `["main"]`; dev `can_admins_bypass:false`, `custom_branch_policies:true`, políticas `["main"]` | PASS |
| TS-O6 | Retención del log group de prod = 14 días | plan.md TS-O6 | `aws logs describe-log-groups --log-group-name-prefix /aws/lambda/skyroute-prod-generator --region eu-west-3 --query 'logGroups[].retentionInDays'` | owner 2026-11-14: `[14]` | PASS |

### Comprobaciones pendientes (PC)

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| PC1 | arm64 de Lambda en eu-west-3 | plan.md PC1 | primer `apply-dev` | run 43579110988: `aws_lambda_function.generator` `Creation complete after 11s [id=skyroute-dev-generator]`; creada también en prod; ARN en eu-west-3 | PASS |
| PC2 | Slot UTC `floor(minutos/15)`, formato `slot=NN` | plan.md PC2 | `pytest` (TS-U5, `test_landing_key_format`) | sesión: ambos tests pasan; el listado real muestra `slot=36` a `slot=44`. La confirmación previa del owner no está citada en este archivo | PASS |
| PC3 | Acciones de refresh de `ci-plan` | plan.md PC3 | plan de PR-T1 | run 43579984929: primer intento AccessDenied (`SNS:GetSubscriptionAttributes`, `lambda:GetFunctionCodeSigningConfig`); PR #17 añadió las lecturas; segundo intento sin AccessDenied; OQ10 (`GetFunction`) confirmada | PASS (tras corrección, PR #17) |
| PC4 | Reglas de checkov que disparan | plan.md PC4 | `static-checks` de PR-M | CKV_AWS_300, CKV_AWS_297 y CKV_AWS_18 en el primer run; corregido en d9de3c6; run final verde (43578985348) | PASS |
| PC5 | Trust del Scheduler con `aws:SourceAccount` y `aws:SourceArn` (schedule group) y trust de Lambda con `aws:SourceAccount` | plan.md PC5 | `aws s3 ls ...landing/ --recursive` y `aws cloudwatch get-metric-statistics` (`Errors`) | owner 2026-11-14: el Scheduler invocó la función y esta escribió `slot=36` con su rol; `Errors` Sum 0.0 | PASS |
| PC6 | Cuota de concurrencia de Lambda | plan.md PC6 | `aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region eu-west-3` | owner 2026-11-14: `"Value": 10.0`; resuelta por el Ruling Implement decisions (Fase 9 sin concurrencia reservada). Solicitud a 1.000: `CASE_OPENED` (ver Follow-up) | PASS (resuelta por Ruling; aprobación de AWS pendiente) |
| PC7 | `archive_file`: `excludes` con directorios y zip determinista | plan.md PC7 | `aws lambda get-function --function-name skyroute-dev-generator --region eu-west-3 --query 'Code.Location' --output text`, descarga con `curl` y `unzip -l` | owner 2026-11-14: `lambda_handler.py` (3672), `ota/__init__.py` (0), `ota/clickstream.py` (3202), `ota/keys.py` (1512), `ota/model.py` (3252); 5 files, 11638 bytes. Sin `tests/`, `seed_postgres.py`, `verify_landing.py` ni `__pycache__`. El plan de PR-T1 sin cambio de hash indica además zip determinista | PASS |

### Success criteria de la Propuesta 1

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| SC-C1 | Simulador OTA coherente (booking ids coherentes con Postgres, sin PII) | proposal C1 | `pytest generators/tests` (TS-U3, TS-U4) | sesión: 28 passed | PASS |
| SC-C2 | Lambda + EventBridge Scheduler en eu-west-3 | proposal C2 | apply de PR-M y `get-function-configuration` | run 43579110988: función, schedule y alarmas creados en dev y prod, ARN en eu-west-3. Configuración final (arm64, Timeout 60, MemorySize 256) en TS-C2 y RetryPolicy 2/900 en TS-C2b, ambas PASS | PASS |
| SC-C3 | Postgres local sembrado | proposal C3 | TS-C3 | Docker no corre; solo se probó que el compose resuelve (TS-C3b) | N/A |
| SC-C4 | Archivos en `landing/` | proposal C4 | `aws s3 ls .../landing/ --recursive` | owner: en prod, `landing/clickstream/ingest_date=2026-11-14/slot=36/part.json.gz` y 17.472 objetos del backfill. En dev, TS-C4: `slot=40/part.json.gz` de 1973 bytes | PASS |
| SC-C5 | Backfill de 182 días en `landing/` (criterio de hecho) | proposal C5 | TS-O1 | `days` 182, `objects_in_range` 17472, sin faltantes ni sobrantes | PASS |
| SC-C6 | El schedule añade micro-lotes (criterio de hecho) | proposal C6 | TS-O2a, TS-O2b, TS-O2c | prod: 9 slots consecutivos (36 a 44). `ENABLED` en prod y `DISABLED` en dev (TS-O2b); dev sin micro-lotes (TS-O2c). Hueco de los slots 00-35 del día D: ver hallazgo 1 de la revisión | PASS (el hueco del día D queda en el hallazgo 1) |
| SC-1 | Criterio literal del README: 6 meses de histórico y micro-lotes nuevos | proposal criterio 1 | TS-O1 y TS-O2a | 17.472 objetos de 182 días y slots 36 a 44 | PASS |
| SC-2 | Criterio del Ruling: un backfill deja 182 días en `landing/` y el schedule añade micro-lotes | proposal criterio 2 | TS-O1 y TS-O2a | idem | PASS |

### Review

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| REV | `adversarial-reviewer` sobre plan.md, proposal.md y el diff completo contra la base | reppit-test Step 1.4 | agente `adversarial-reviewer` (Opus) | veredicto GO-WITH-FIXES; 10 hallazgos (ver "## Review"). Fixes en alcance: hallazgo 3 RESUELTO, hallazgo 4 FIXED, hallazgo 1 PENDIENTE-OWNER | PENDIENTE (GO-WITH-FIXES solo cuenta como PASS con los fixes en alcance resueltos; falta la evidencia del hallazgo 1) |

## Review

Revisor: `adversarial-reviewer` (Opus). Veredicto: **GO-WITH-FIXES**.

| # | Severidad | Hallazgo | Estado |
|---|-----------|----------|--------|
| 1 | medium (en alcance) | Hueco del día D: los slots 00-35 de 2026-11-14 no existen (el schedule nació a las 09:10 UTC y el backfill llega hasta D-1) | PENDIENTE-OWNER: desde 2026-11-15, backfill `{"from":"2026-11-14","to":"2026-11-14"}` y `KeyCount` de `ingest_date=2026-11-14` = 96 |
| 2 | medium | `rate(15 minutes)` no queda alineado al reloj | follow-up: `cron(0/15 * * * ? *)` y check periódico de 96 objetos/día desde D |
| 3 | medium (en alcance) | `ConcurrentExecutions` quizá sin datos y la alarma no dispararía | RESUELTO: `list-metrics` devuelve la métrica por `FunctionName=skyroute-prod-generator` (2 métricas; evidencia del owner) |
| 4 | low (en alcance) | `-lock-timeout=60s` en el plan de CI no aplica con `-lock=false` | FIXED en esta rama (`grep -n "lock-timeout" .github/workflows/terraform-plan.yml` sin coincidencias; 1 coincidencia del comando sin la opción) |
| 5 | low | `test_package` no prueba el zip desplegado | resuelto en la práctica por PC7 PASS (zip real con 5 archivos); follow-up opcional: test del zip |
| 6 | low | Determinismo del gzip entre intérpretes | follow-up; dato a favor: el slot 40 mide 1973 bytes en dev y en prod |
| 7 | low | El histórico del backfill caduca junto hacia 2026-12-14 (lifecycle de 30 días) | follow-up para la Fase 3 (el orquestador lo recoge en `findings.md`) |
| 8 | low | `concurrency_alarm_threshold` y la segunda alarma no están en Files Changed | follow-up documental (respaldados por el Ruling Implement decisions) |
| 9 | low | Sin `iam:UpdateAssumeRolePolicy`: un cambio de trust exige re-apply de `bootstrap/` | follow-up: nota en el runbook |
| 10 | low | El secret `ALARM_EMAIL` está disponible en el job de plan de PR | follow-up / riesgo residual |

La fila REV queda PENDIENTE hasta que el hallazgo 1 tenga evidencia.

## Follow-up

1. **PR-Q (Fase 11), restaurar `reserved_concurrent_executions = 1`.** Espera a que AWS apruebe la cuota L-B99A9384 (solicitud `CASE_OPENED`, CaseId 179464611900230, valor 1000, 2026-11-14T09:48:23+01:00). Comando del owner: `aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region eu-west-3`. TS-C2c (`aws lambda get-function-concurrency --function-name skyroute-prod-generator --region eu-west-3` con `ReservedConcurrentExecutions = 1`) se ejecuta tras la PR-Q. No es FAIL.
2. **PR-T2 (#18):** aplicada; TS-C2 confirma `Timeout 60` (el plan de CI `300 -> 60` no está citado).
3. **TS-C2c / PR-Q:** ver punto 1 (cuota `CASE_OPENED`, caso 179464611900230).
4. **Hallazgos de la revisión (ver "## Review"):** 2 (cron alineado al reloj y check de 96/día desde D), 5 (test del zip, opcional), 6 (determinismo de gzip entre intérpretes), 7 (caducidad conjunta del histórico hacia 2026-12-14, Fase 3), 8 (documentar `concurrency_alarm_threshold` y la segunda alarma), 9 (nota de runbook sobre `iam:UpdateAssumeRolePolicy`), 10 (secret `ALARM_EMAIL` en el plan de PR, riesgo residual).
5. **Pendiente del owner para cerrar el veredicto:** solo el hallazgo 1 (backfill del día D desde 2026-11-15, `KeyCount` = 96).
6. **Eventos `consent` con campo email:** revisión de PII pendiente (relación con TS-U4); no tiene id propio en el plan.
7. **TS-C3 (Postgres con datos):** repetir cuando el daemon de Docker corra (`docker info` falla hoy).
8. **Limitación conocida de la alarma:** la alarma de `Invocations` no detecta un generador parado (Observability, limitación C4 del plan); se vigila con TS-O2.
9. Nota de procedencia: la fila TS-A1 de PR-M se apoya en `gh pr checks 15` de esta sesión; el run del segundo `static-checks` (43578985348) no estaba antes citado. TS-V6 incluye `docs/design/CONTEXT.md` y `CHANGELOG.md`, fuera de `generator-landing/`, por el cierre de sesión de design-memory.

## Evidencia (literal)

Registro de evidencia por fase conservado del archivo anterior. Lo que la Convention "Apply gate" impide ejecutar a los agentes se prueba con la salida que aporta el owner (Convention "Verification ownership").

### Evidencia por fase

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
| 10 | TS-A3 | Plan de PR-T1 (#16) con la función y el bucket en el state | job de CI, run 43579984929, re-ejecutado tras el re-apply de ci-plan (PR #17) | prod: `Terraform plan: prod (OK)`, refresh de los 23 recursos sin AccessDenied, único cambio `timeout = 60 -> 300`, `Plan: 0 to add, 1 to change, 0 to destroy.`; dev: `No changes.` (citas en "Fase 10: salida (literal)") | PASS |
| 10 | PC3 | Lecturas de refresh de `ci-plan` sobre los recursos del módulo | mismo run 43579984929; PR #17 (re-apply de `bootstrap/`, plan `0 to add, 1 to change, 0 to destroy`, `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.`) | primer intento FALLO: AccessDenied en `SNS:GetSubscriptionAttributes` y `lambda:GetFunctionCodeSigningConfig` para `assumed-role/ci-plan` en dev y prod. Tras la PR #17 (añade `lambda:GetFunctionCodeSigningConfig`, `GetFunctionEventInvokeConfig`, `GetFunctionConcurrency`, `ListTags` y `sns:GetSubscriptionAttributes`) el plan pasa sin AccessDenied. OQ10 (`lambda:GetFunction`) confirmada | PASS (tras corrección, PR #17) |
| 10 | Backfill (PR-T1) | Backfill de 182 días con timeout 300 | apply de PR-T1: run 43587443950 (430e5cf), success; `aws lambda get-function-configuration ... --query Timeout` y bucle de 182 `aws lambda invoke` síncronos (owner, 2026-11-14) | `Timeout` = `300`; prueba de 1 día: `{"objects": 96, "from": "2026-05-16", "to": "2026-05-16"}`; bucle 2026-05-16..2026-11-13 completado sin ningún `FALLO` | COMPLETADO |
| 10 | TS-O2 (segunda mitad) | El schedule de prod añade micro-lotes consecutivos (mitad del criterio de hecho) | `aws s3 ls s3://skyroute-prod-data-437266392155/landing/clickstream/ingest_date=2026-11-14/ --recursive --profile skyroute-dev` (owner, 2026-11-14) | 9 slots consecutivos (36 a 44), uno cada 15 min, sin huecos; horas locales +01:00 (09:11 a 11:11 UTC): 10:11:35 slot 36, 10:26:36 slot 37, 10:41:35 slot 38, 10:56:36 slot 39, 11:11:36 slot 40, 11:26:35 slot 41, 11:41:35 slot 42, 11:56:35 slot 43, 12:11:35 slot 44 (tamaños 1522 a 2342 bytes). Con TS-O1 (17.472 objetos) quedan cumplidas las dos mitades del criterio de hecho de la Fase 2. Completa la fila TS-O2 (parcial) de la Fase 9 | PASS |
| 10 | TS-O1 | Backfill completo en `landing/` (criterio de hecho C5) | `aws s3api list-objects-v2 ... --prefix landing/clickstream/` y `python3 generators/verify_landing.py --listing /tmp/landing-listing.json --d 2026-11-14` (owner, 2026-11-14) | `days` 182, `objects_in_range` 17472, `days_not_96` `{}`, `missing` `[]`, `extra` `[]`; 182 × 96 = 17.472, dentro de los 30 días del lifecycle | PASS |

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

### Fase 10: salida (literal)

```text
Fase 10 — evidencia (owner javiladino, 2026-11-14)

PR-T1 (#16): plan de PR re-ejecutado tras el re-apply de ci-plan (PR #17, bootstrap 0/1/0) en el run 43579984929:
- prod: "Terraform plan: prod (OK)"; refresh de los 23 recursos del módulo (incluidos event_invoke_config, scheduler_schedule y las dos alarmas) sin AccessDenied; único cambio "aws_lambda_function.generator ... timeout = 60 -> 300"; "Plan: 0 to add, 1 to change, 0 to destroy."
- dev: "Terraform plan: dev (OK)"; "No changes. Your infrastructure matches the configuration."
=> TS-A3 PASS, PC3 PASS (lecturas añadidas: lambda:GetFunctionCodeSigningConfig, GetFunctionEventInvokeConfig, GetFunctionConcurrency, ListTags; sns:GetSubscriptionAttributes), OQ10 (GetFunction) confirmada.
Primer intento (FALLO, mismo run antes del re-apply): AccessDenied en SNS:GetSubscriptionAttributes y lambda:GetFunctionCodeSigningConfig para assumed-role/ci-plan en dev y prod.
PR #17 re-apply de bootstrap: plan "0 to add, 1 to change, 0 to destroy" (aws_iam_role_policy.ci_plan); apply "Apply complete! Resources: 0 added, 1 changed, 0 destroyed."
Apply de PR-T1: run 43587443950 (430e5cf), success.

Backfill:
$ aws lambda get-function-configuration --function-name skyroute-prod-generator --query Timeout ...
300
$ aws lambda invoke ... --payload '{"from":"2026-05-16","to":"2026-05-16"}' /tmp/bf-2026-05-16.json
{"StatusCode": 200, "ExecutedVersion": "$LATEST"}
{"objects": 96, "from": "2026-05-16", "to": "2026-05-16"}
Bucle de 182 invocaciones síncronas de 1 día (2026-05-16 .. 2026-11-13), --cli-read-timeout 0, parada ante FunctionError: completado sin ningún "FALLO".

TS-O1 (criterio de hecho C5):
$ aws s3api list-objects-v2 --bucket skyroute-prod-data-437266392155 --prefix landing/clickstream/ --region eu-west-3 --profile skyroute-dev --output json > /tmp/landing-listing.json
$ python3 generators/verify_landing.py --listing /tmp/landing-listing.json --d 2026-11-14
{
  "d": "2026-11-14",
  "days": 182,
  "objects_in_range": 17472,
  "days_not_96": {},
  "missing": [],
  "extra": []
}
=> TS-O1 PASS: 182 días × 96 = 17.472 objetos, sin faltantes ni sobrantes. Tomado dentro de los 30 días del lifecycle.
```

### Etapa Test: salidas del owner (literal)

```text
Etapa Test — salidas del owner (javiladino), 2026-11-14 (aws CLI con --profile skyroute-dev, eu-west-3)

Timeout de prod tras PR-T2:  get-function-configuration --query Timeout -> 60

TS-B2  simulate ci-apply-dev s3:GetObject/PutObject sobre .../envs/prod/terraform.tfstate -> implicitDeny / implicitDeny  (PASS)
TS-B3  simulate ci-apply-dev iam:UpdateAssumeRolePolicy, iam:PutRolePolicy sobre role/ci-apply-prod -> explicitDeny / explicitDeny  (PASS)
TS-B5a simulate ci-apply-dev iam:CreateRole role/workload/skyroute-dev-x con iam:PermissionsBoundary=workload-boundary-prod -> explicitDeny  (PASS)
TS-B5b idem con workload-boundary-dev -> allowed  (PASS)
TS-B5c simulate ci-apply-dev iam:PassRole role/workload/skyroute-dev-generator-exec con iam:PassedToService=ec2.amazonaws.com -> explicitDeny  (PASS)
TS-B6  simulate ci-plan lambda:GetFunction, lambda:GetFunctionConfiguration sobre function:skyroute-prod-generator -> allowed / allowed; s3:GetObject skyroute-prod-data-437266392155/landing/x -> explicitDeny; s3:PutObject .../envs/dev/terraform.tfstate.tflock -> implicitDeny  (PASS)
TS-B8  simulate ci-apply-dev lambda:CreateFunctionUrlConfig, UpdateFunctionUrlConfig, AddPermission sobre function:skyroute-dev-generator -> explicitDeny x3; iam:AttachRolePolicy sobre role/workload/skyroute-dev-generator-exec -> explicitDeny  (PASS)
TS-B7  aws iam get-role --role-name ci-apply -> "An error occurred (NoSuchEntity) when calling the GetRole operation: The role with name ci-apply cannot be found."  (PASS)

TS-C4  aws lambda invoke skyroute-dev-generator --payload '{"scheduled_time":"2026-11-14T10:14:59Z"}' -> StatusCode 200; {"objects": 1, "key": "landing/clickstream/ingest_date=2026-11-14/slot=40/part.json.gz"}
       aws s3 ls s3://skyroute-dev-data-437266392155/landing/ --recursive -> "2026-11-14 12:30:30       1973 landing/clickstream/ingest_date=2026-11-14/slot=40/part.json.gz" (único objeto)  (PASS)
TS-O2c dev landing/ sin objetos previos: el único objeto es el que creó TS-C4  (PASS)
Determinismo entre entornos (dato extra, hallazgo 6 de la revisión): el slot 40 de 2026-11-14 mide 1973 bytes en dev (invocación manual) y 1973 bytes en prod (schedule).

Hallazgo 3 de la revisión: aws cloudwatch list-metrics --namespace AWS/Lambda --metric-name ConcurrentExecutions --dimensions Name=FunctionName,Value=skyroute-prod-generator -> 2 métricas con FunctionName=skyroute-prod-generator (una con Resource). La métrica se publica sin concurrencia reservada  (RESUELTO, la alarma recibe datos)
TS-O2b get-schedule State: prod "ENABLED", dev "DISABLED"  (PASS)
TS-C2  get-function-configuration prod -> Arch ["arm64"], Timeout 60, Mem 256  (PASS)
TS-C2b get-schedule prod --query Target.RetryPolicy -> {"MaximumEventAgeInSeconds": 900, "MaximumRetryAttempts": 2}  (PASS)
TS-O3  describe-alarms prefix skyroute-prod-generator -> skyroute-prod-generator-concurrency OK; skyroute-prod-generator-invocations ALARM (esperado: el backfill superó 120 invocaciones/h; prueba que la alarma dispara)  (PASS)
TS-O6  describe-log-groups /aws/lambda/skyroute-prod-generator retentionInDays -> [14]  (PASS)
TS-O4  list-subscriptions-by-topic skyroute-prod-alarms -> ["PendingConfirmation"]; skyroute-dev-alarms -> ["PendingConfirmation"]  (luego confirmadas por email, ver abajo)
TS-O4 (confirmación, owner 2026-11-14): "Subscription confirmed! You have successfully subscribed. Your subscription's id is: arn:aws:sns:eu-west-3:437266392155:skyroute-dev-alarms:ed3fcd6c-1a1a-4987-b968-13baa07535e3"
TS-O4 (confirmación, owner 2026-11-14): "Subscription confirmed! You have successfully subscribed. Your subscription's id is: arn:aws:sns:eu-west-3:437266392155:skyroute-prod-alarms:c5348778-bd4a-4227-b4e3-fcf3efffaad8"  (PASS)
PC7    zip desplegado de skyroute-dev-generator (unzip -l): lambda_handler.py (3672), ota/__init__.py (0), ota/clickstream.py (3202), ota/keys.py (1512), ota/model.py (3252); 5 files, 11638 bytes. Sin tests/, seed_postgres.py, verify_landing.py ni __pycache__  (PASS)

Pendiente: backfill del día D (desde 2026-11-15): invoke {"from":"2026-11-14","to":"2026-11-14"} y KeyCount de ingest_date=2026-11-14 = 96 (hallazgo 1 de la revisión).
```

### Pendiente (registro histórico previo a la etapa Test; superado por la tabla Checks)

Hechos en la Fase 9 (ver filas de "Evidencia por fase"): PC1, PC5, PC4, subida de cuota aplicada (re-apply 1/0/0) y D registrada (2026-11-14). Hechos en la Fase 10: TS-A3, PC3, TS-O1, TS-O2 (segunda mitad) y OQ10 (filas de "Evidencia por fase"). Siguen abiertos:
- PR-T2 aplicada: el timeout de prod vuelve a 60 (cambio en `envs/prod/main.tf`, pendiente de PR, plan de CI y apply); evidencia: plan `timeout = 300 -> 60` y `get-function-configuration` con `Timeout = 60`.
- Cuota: la solicitud está en `CASE_OPENED`; el owner aporta la cuota aprobada (comando de PC6) cuando AWS la apruebe. Después, PR-Q (Fase 11) y TS-C2c (cuota en `CASE_OPENED`).
- TS-W1 completa (con recursos en el state): sin cita explícita en la evidencia de la Fase 10; confirmar.
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
