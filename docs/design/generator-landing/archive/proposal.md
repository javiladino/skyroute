---
type: Proposal
topic: generator-landing
date: 2026-11-13
---

# generator-landing: Solution Proposals

> **Task:** proponer 2–3 formas de implementar la Fase 2 (simulador OTA, Lambda + EventBridge Scheduler, Postgres local, archivos en `landing/`) dentro del Ruling "Research decisions", sin reabrirlo.
> **Date:** 2026-11-13
> **Research source:** `docs/design/generator-landing/working/research.md`; secciones usadas: Criterio de hecho (C1-C6), Hecho (a), (b), (c), Secretos, PII, Coste, componentes 1-5, Tensiones T1-T22, No verificado V1-V23.
> **Review:** ronda adversarial, de seguridad y de coste ejecutada por el orquestador (Step 4 de `reppit-propose`); este documento ya aplica sus hallazgos y las decisiones D1 y D2 del owner (2026-11-13).
> **Método:** ningún agente ejecutó `terraform` ni comandos AWS (Convention "Apply gate"). Las rutas de archivo de las propuestas son previstas; ninguna existe hoy salvo las de `bootstrap/` y `.github/workflows/` (research § Lo que existe hoy).

## Context

**Request:** implementar el generador determinista, su Lambda con schedule y backfill, el bucket de datos con `landing/`, el Postgres local sembrado y la separación de `ci-apply`, tal como fija el Ruling "Research decisions".

**Success criteria:**

1. Literal (README § Fases): "Simulador OTA coherente, Lambda + EventBridge, Postgres local, archivos en `landing/`. Hecho cuando hay 6 meses de histórico y llegan micro-lotes nuevos."
2. Fijado por el Ruling: "La Fase 2 está hecha cuando un backfill deja 182 días en `landing/` y el schedule añade micro-lotes."

Se puntúan por partes C1-C6 (research § Criterio de hecho).

**Decisiones del owner del 2026-11-13 (vinculantes, aplican a las tres propuestas):**

- **D1.** `terraform plan -lock=false` es obligatorio en `ci-plan`; `ci-plan` pierde `PutObject`/`DeleteObject` sobre el `.tflock` (`ci_roles.tf:152-158`). El lock deja de ser un diferenciador entre propuestas.
- **D2.** Una `workload-boundary` por entorno, `workload-boundary-dev` y `workload-boundary-prod`, acotada a ARNs `skyroute-<env>-*`, más un Deny que obliga a cada `ci-apply-<env>` a crear y adjuntar solo la boundary de su entorno. Esto **refina** el Ruling "Research decisions" (línea Boundary, que habla de una `workload-boundary`); se registra como ruling al cerrar el ciclo.

**Fijado por el Ruling "Research decisions" (no se reabre, salvo el refinamiento D2):** histórico regenerable, generador determinista por fecha lógica; backfill en la misma Lambda con payload `{from, to}` invocada por el owner; Postgres local sembrado por el mismo generador, extracción aplazada; re-apply de `bootstrap/` por el owner con sección nueva en el runbook; `ci-apply` separado en `ci-apply-dev`/`ci-apply-prod`; `workload-boundary` propia, roles con path `/workload/` y prefijo `skyroute-`, `iam:PassRole` con `iam:PassedToService` a lambda y scheduler; `ci-plan` de solo lectura sin acciones de datos; `(run_date, slot)` desde `scheduled-time` redondeado a 15 min; un bucket por entorno SSE-S3, TLS-only, public access block, sin versioning; schedule ENABLED en prod y DISABLED en dev por variable; concurrencia reservada 1, RetryPolicy acotada, logs 14 días, alarma de Invocations a SNS por email; skips de checkov por recurso con motivo.

**Key constraints from the research:**

- Hoy `ci-boundary` y las inline de `ci-plan`/`ci-apply` solo conceden state y lock (`ci_roles.tf:12-100`, `:136-159`, `:263-286`); todo recurso de Fase 2 exige ampliar boundary e inline a la vez, y lo aplica solo el owner (research Hecho (a); T2).
- `ci-apply` acepta `environment:dev` y `environment:prod` (`ci_roles.tf:246-247`) y escribe el state de prod (`:270-285`): un job de `dev` puede escribir el state de prod (research Hecho (c); T17). El Ruling ordena corregirlo antes de ampliar permisos.
- Los Deny de `ci_roles.tf:36-97` están duplicados en boundary e inline; toda ampliación debe mantener las dos copias (research Hecho (c); T22). Los Deny no cubren `UpdateAssumeRolePolicy`/`PutRolePolicy`/`AttachRolePolicy`/`CreatePolicy` en roles ajenos a CI (T18, inferido).
- El plan de PR ejecuta código de la PR con `ci-plan`, que hoy escribe el lock (`ci_roles.tf:152-158`) (T19); D1 lo cierra con `-lock=false`. Todas las PR comparten el mismo `sub` (`...:pull_request`, `ci_roles.tf:121`), así que no se puede separar `ci-plan` por entorno por `sub`.
- `local.ci_apply_role_arn` (`ci_roles.tf:6`) apunta a `role/ci-apply`, y `DenyCiAndOidcChanges` (`:46-54`, `:170-178`, `:297-305`) solo protege `ci-plan`, ese ARN y el OIDC: los roles nuevos `ci-apply-dev`/`ci-apply-prod` quedarían sin protección y un job de `dev` podría reescribir el trust de `ci-apply-prod`.
- `DenyCreateRoleWithoutBoundary` (`ci_roles.tf:56-65`, `:180-189`, `:307-316`) exige `ci-boundary` en todo `CreateRole`, lo que impide crear los roles de workload con `workload-boundary-<env>`; hay que reemplazarlo, no complementarlo.
- Nombre del bucket de state, comprobado en `variables.tf:10`: `skyroute-tfstate-437266392155-eu-west-3`. Encaja con `skyroute-*` pero **no** con `skyroute-<env>-*` ni con `skyroute-*-data-*`; aun así se mantiene el Deny explícito de S3 sobre el bucket de state en la boundary, porque un patrón `skyroute-*` lo cubriría.
- Lambda: Python `3.12`/`3.13`/`3.14`, x86_64 y arm64, zip 50 MB / 250 MB descomprimido, timeout 900 s; arm64 en París solo por fuente de terceros (research componente 2, H2, H5.3; V8).
- Librerías candidatas: Faker 40.54.0 (Python >=3.10), NumPy 2.5.4 (>=3.12), boto3 1.44.2, psycopg 3.3.9 (LGPL-3.0-only) (research componente 1, H7). Tamaño de Faker empaquetado sin medir (V11).
- Backfill dentro de Lambda: 17.472 invocaciones-slot × 15 GB-s = 262.080 GB-s, el 65 % de los GB-s gratuitos de un mes (research § Coste). Schedule: 96 invocaciones/día/entorno, dentro del nivel gratuito (Hecho (b)).
- El lifecycle de 30 días cuenta desde la creación del objeto: un backfill subido hoy expira 30 días después de hoy (research componente 4, H4; T1). La evidencia de "182 días en `landing/`" tiene que tomarse dentro de esa ventana.
- Puertos: Astro publica 5432 y 8080; OpenMetadata 8585-8586, 8080, 9200/9300; Marquez fija `postgres:14`; PostgreSQL 18.7 es la minor actual y el volumen va en `/var/lib/postgresql` (research componente 3; T11; V15).
- PII sintética del CRM (emails, consentimiento) llega a `landing/` (research § PII; pregunta 35).
- checkov 3.4.5 corre en CI sobre todo `infra/terraform`; las reglas que disparan los recursos de Fase 2 no están verificadas (research componente 5; V10). Convention "Bootstrap identity" limita los skips CKV_AWS_273/274 a `bootstrap/owner_user.tf`.
- KMS queda fuera: el Ruling fija SSE-S3 y `foundations/current/plan.md:237` (N1) veta `aws_kms` (research T10).

**Comunes a las tres propuestas (para no repetirlos):**

- Handler: si el evento trae `scheduled_time`, calcula `(run_date, slot)` redondeando hacia abajo a 15 min y genera un slot; si trae `{from, to}`, recorre los slots de `from` a `to` (backfill termina en D-1). Nunca llama a `now()` para decidir qué genera (Convention "Idempotency"). La clave S3 depende solo de `(source, run_date, slot)`, así que una reentrega at-least-once reescribe el mismo objeto (research componente 2, edge cases).
- El `Input` del schedule pasa `<aws.scheduler.scheduled-time>` (research H1.12).
- Bucket `skyroute-<env>-data-<account_id>` con prefijo `landing/`, lifecycle `Expiration` 30 días sobre `landing/` y `abort_incomplete_multipart`, `DenyInsecureTransport`, public access block, `BucketOwnerEnforced`, SSE-S3, sin versioning (Ruling; patrón de `state_bucket.tf`, research componente 4).
- Roles de workload `skyroute-<env>-generator-exec` y `skyroute-<env>-scheduler-invoke`, path `/workload/`, con `workload-boundary-<env>` (D2); Scheduler solo con `lambda:InvokeFunction` sobre una función (research Hecho (c), "Roles de Fase 2 inexistentes").
  - Trust del rol de scheduler: `Principal = scheduler.amazonaws.com` con `aws:SourceAccount` = la cuenta y `aws:SourceArn` = el ARN del schedule `schedule/default/skyroute-<env>-generator`. Trust del rol de ejecución de Lambda: `lambda.amazonaws.com` con `aws:SourceAccount` (condición inferida de la guía de confused deputy, no verificada contra la documentación de Lambda; V-nuevo).
  - Rol de ejecución, S3: `s3:PutObject` sobre el ARN exacto `arn:aws:s3:::skyroute-<env>-data-<account_id>/landing/*`, no sobre el patrón `skyroute-*-data-*`. Logs: `logs:CreateLogStream`/`PutLogEvents` sobre `arn:aws:logs:eu-west-3:<account_id>:log-group:/aws/lambda/skyroute-<env>-generator:*`.
  - La Lambda nunca escribe registros de datos en los logs (solo claves, conteos y `run_date`/`slot`).
- Log group `/aws/lambda/skyroute-<env>-generator` con `retention_in_days = 14` declarado en Terraform antes de la función; alarma `Invocations` con umbral por encima de 96/día (umbral exacto en Open Questions) a un topic SNS `skyroute-<env>-alarms`.
  - Política del topic: `sns:Publish` solo para `cloudwatch.amazonaws.com` con `aws:SourceArn` = ARN de la alarma y `aws:SourceAccount` = la cuenta. El email es una variable Terraform **sin valor versionado** (`TF_VAR_alarm_email` desde una variable de entorno de GitHub o del shell del owner), nunca en un `tfvars` versionado.
  - La suscripción email queda en `PendingConfirmation` hasta que el owner pulse el enlace del correo; sin eso la alarma no avisa (paso del owner y validación en cada propuesta).
- Secretos: la Lambda no lleva secretos; `POSTGRES_PASSWORD` en `.env` local ignorado (`.gitignore:51-52`, research § Secretos). `.env.example` solo lleva un placeholder (`POSTGRES_PASSWORD=change-me`), nunca un valor usable.
- Semilla: `seed = int.from_bytes(hashlib.sha256(f"{run_date}|{slot}|{source}".encode()).digest(), "big")`; nunca `hash((run_date, slot, source))`, que varía con `PYTHONHASHSEED` entre procesos y rompe Idempotency.
- PII (las tres propuestas, esquema de la 3): el email es `u<sha256(customer_id)[:12]>@example.com`; no hay nombres, ni proveedores de teléfono o dirección de Faker; el consentimiento lleva marca de tiempo lógica.
- Cómputo de la Lambda: `timeout = 60` s para una invocación de un slot y `memory_size = 256` MB explícitos. El techo por defecto (900 s, 1 GB) llegaría a ~36 USD/mes de GB-s si algo se cuelga en bucle, por encima del presupuesto de 10 USD; 60 s × 0,25 GB acota cada slot a 15 GB-s. El backfill usa un timeout aparte (ver backfill).
- Reintentos (A8): el schedule lleva `retry_policy { maximum_retry_attempts = 2, maximum_event_age_in_seconds = 900 }` (un evento viejo de 15 min ya no es su slot). Si el target se invoca de forma asíncrona, `aws_lambda_function_event_invoke_config` con `maximum_retry_attempts = 0` y `maximum_event_age_in_seconds = 900` para que los reintentos sean solo los de Scheduler. Con `reserved_concurrent_executions = 1`, una invocación concurrente se limita (throttle) y entra en esos reintentos.
- Backfill (A7): se invoca con `aws lambda invoke --cli-read-timeout 0 --cli-connect-timeout 0 --invocation-type RequestResponse --payload ...` con un rango por invocación; un rango = 7 días (672 slots) tarda ~11 min a 1 s por slot (supuesto sin medir, V12), de modo que el backfill de 182 días son 26 invocaciones, espaciadas hasta que termine la anterior. La función se despliega con `timeout = 60` y el owner sube el timeout del backfill a 900 s solo durante la ventana con una variable (`backfill_timeout`); la alternativa es invocación asíncrona (`--invocation-type Event`) con un rango por llamada. Todo el backfill compite con el schedule de prod bajo concurrencia reservada 1: los slots de prod caen en reintentos de Scheduler (2, 900 s) o se pierden si el rango dura más de 15 min; el owner evita el rango que cruza una hora de punta de la alarma. Se recomienda **un entorno por mes** (dev y prod en el mismo mes superan el nivel gratuito de Lambda en ~2 USD).
- ARNs por servicio en `ci-apply-<env>` (en vez del patrón genérico `skyroute-<env>-*`): `arn:aws:s3:::skyroute-<env>-data-<account_id>` y `/*`; `arn:aws:lambda:eu-west-3:<account_id>:function:skyroute-<env>-generator`; `arn:aws:scheduler:eu-west-3:<account_id>:schedule/default/skyroute-<env>-generator`; `arn:aws:iam::<account_id>:role/workload/skyroute-<env>-*`; `arn:aws:logs:eu-west-3:<account_id>:log-group:/aws/lambda/skyroute-<env>-generator` y `:*`; `arn:aws:sns:eu-west-3:<account_id>:skyroute-<env>-*`; `arn:aws:cloudwatch:eu-west-3:<account_id>:alarm:skyroute-<env>-*`.
- `ci-apply-dev` y `ci-apply-prod` con trust `StringEquals` y **un solo** `sub` por rol, en el formato de ID inmutable de `ci_roles.tf:246-247`: `repo:javiladino@97758532/skyroute@1455233709:environment:dev` y `...:environment:prod` (el formato `repo:javiladino/skyroute:environment:<env>` no coincidiría con el `sub` real). Permisos de state solo sobre `envs/<env>/terraform.tfstate` y su `.tflock`, y `s3:ListBucket` sobre el bucket de state con condición `StringEquals s3:prefix = envs/<env>/` (S-H14). Se borra `ci-apply` (ver orden de transición). `terraform-apply.yml` usa un rol por job.
- **Deny reemplazados (A2, A3; aplica a las tres copias de cada rol y a `ci-boundary`):** `DenyCreateRoleWithoutBoundary` (`ci_roles.tf:56-65`, `:180-189`, `:307-316`) se **reemplaza**, no se complementa, por: (a) Deny de `iam:CreateRole` y `iam:PutRolePermissionsBoundary` salvo que `iam:PermissionsBoundary` sea la `workload-boundary-<env>` del propio entorno (en `ci-apply-<env>`; el Deny de D2 prohíbe adjuntar la del otro entorno); (b) Deny de `iam:UpdateAssumeRolePolicy`, `PutRolePolicy`, `AttachRolePolicy`, `DetachRolePolicy`, `DeleteRolePolicy`, `CreatePolicy` y `iam:PassRole` en cualquier rol **fuera** de `role/workload/skyroute-<env>-*` (`NotResource`); (c) `iam:PassRole` permitido solo hacia `role/workload/skyroute-<env>-*` con `iam:PassedToService` en `lambda.amazonaws.com` y `scheduler.amazonaws.com`. `local.ci_apply_role_arn` (`ci_roles.tf:6`) y `DenyCiAndOidcChanges` (`:46-54`, `:170-178`, `:297-305`) pasan a listar todos los roles de CI: `ci-plan`, `ci-apply-dev`, `ci-apply-prod` (y los extra de cada propuesta) o `role/ci-*`, más el OIDC. `DenyBoundaryPolicyChanges` (`:73-82` y copias) añade los ARN de `workload-boundary-dev` y `workload-boundary-prod`. `DenyDeleteBoundary` (`:66-71`) se mantiene. Se mantiene también el Deny de todo S3 sobre el bucket de state (`skyroute-tfstate-437266392155-eu-west-3`) en la boundary.
- **Fila de `ci-plan` (A6, S-H8):** Allow de lectura de metadatos para el refresh: `s3:Get*Configuration`/`GetBucketPolicy`/`GetBucketLocation`/`ListBucket` sobre buckets `skyroute-<env>-data-*`, `lambda:GetFunctionConfiguration`/`ListVersionsByFunction`/`GetPolicy` (se **excluye** `lambda:GetFunction`: devuelve una URL prefirmada del código), `scheduler:GetSchedule`/`ListSchedules`, `iam:GetRole`/`GetRolePolicy`/`ListRolePolicies`/`ListAttachedRolePolicies`/`GetPolicy`/`GetPolicyVersion`, `logs:DescribeLogGroups`/`ListTagsForResource` (solo describe), `sns:GetTopicAttributes`/`ListTagsForResource`/`ListSubscriptionsByTopic`, `cloudwatch:DescribeAlarms`/`ListTagsForResource` y, en la P3, `ecr:DescribeRepositories`/`GetRepositoryPolicy`/`GetLifecyclePolicy`/`ListTagsForResource`. Deny explícito de `s3:GetObject` sobre `arn:aws:s3:::skyroute-*-data-*/*` y de `logs:GetLogEvents`/`FilterLogEvents`/`StartQuery`. La lista exacta queda para V4/T5; esta fila fija el principio.
- **Orden de transición (A4):** `ci-apply` se **destruye** y `ci-apply-dev`/`ci-apply-prod` se **crean** (cambia `name`, así que un `moved` no evita el reemplazo). Ventana sin rol de apply entre el destroy y el create: el owner hace el re-apply con su identidad, ejecuta el workflow de apply solo después, y no mergea nada a `main` durante la ventana. Orden del runbook: (1) crear `workload-boundary-<env>`, (2) crear `ci-apply-dev`/`ci-apply-prod`, (3) actualizar `terraform-apply.yml` en una PR aparte, (4) destruir `ci-apply`. Paso (4) tras (3) evita que el workflow asuma un rol borrado.
- **Costes estimados (cost guard; tarifas de eu-west-3 no verificadas):** P1 ~0,05–0,3 USD/mes; P2 ~0,05–0,45 USD/mes; P3 ~0,35–0,9 USD/mes (de ellos ECR 0,30–0,60). Escenario del techo (900 s, 1 GB) ~36 USD/mes: la razón del `timeout = 60`.
- CKV_AWS_18 (bucket sin access logging) se acepta explícitamente como riesgo; no se añade skip hasta que dispare en el primer `static-checks`; sus IDs siguen en V10.

## Proposal 1: Un módulo, zip único con stdlib, roles por entorno en archivos separados

### Overview

Minimizar superficie: el generador usa solo la biblioteca estándar (`random.Random` sembrado con SHA-256 de `run_date|slot|source`) más boto3 del runtime, y se empaqueta como un zip único con `archive_file` en Terraform, arm64, `python3.13`. Toda la Fase 2 de AWS es un módulo `modules/generator-landing` que llaman `envs/dev` y `envs/prod` con variables distintas. En `bootstrap/` cada rol de CI tiene su archivo y cada `workload-boundary-<env>` va en un archivo propio.

### Key Changes

| Component | Change |
|-----------|--------|
| `generators/ota/` (`model.py`, `clickstream.py`, `seed_postgres.py`, `keys.py`) | New: generador determinista, solo stdlib; claves compartidas `customer_id`, `session_id`, `booking_id`, `campaign_id`, `currency` (research componente 1, H2-H3) |
| `generators/lambda_handler.py` | New: rama schedule (`scheduled_time`) y rama backfill (`{from, to}`), escribe `landing/clickstream/ingest_date=<run_date>/slot=<NN>/part.json.gz` |
| `generators/tests/` | New: tests de determinismo y de claves (ver Validation) |
| `infra/terraform/modules/generator-landing/` (`bucket.tf`, `lambda.tf`, `scheduler.tf`, `iam.tf`, `alarm.tf`, `variables.tf`, `outputs.tf`) | New: bucket, función, log group, schedule, roles de workload, SNS y alarma; variable `schedule_enabled` |
| `infra/terraform/envs/dev/main.tf`, `envs/prod/main.tf` | Modified: llaman al módulo; `schedule_enabled = false` en dev, `true` en prod |
| `infra/terraform/bootstrap/ci_roles.tf` | Modified: se queda `ci-boundary` y `ci-plan`; `ci-plan` pierde `PutObject`/`DeleteObject` sobre el `.tflock` (`:152-158`, D1) y gana la fila de lectura de metadatos de Comunes; `local.ci_apply_role_arn` (`:6`) y `DenyCiAndOidcChanges` listan `ci-plan`, `ci-apply-dev` y `ci-apply-prod`; `DenyCreateRoleWithoutBoundary` se **reemplaza** en sus tres copias (ver Deny reemplazados en Comunes); `DenyBoundaryPolicyChanges` añade los ARN de las dos boundaries de workload |
| `infra/terraform/bootstrap/ci_apply_dev.tf`, `ci_apply_prod.tf` | New: un rol por entorno; trust `StringEquals` con un solo `sub` de ID inmutable (`ci_roles.tf:246-247`); state y lock solo de su entorno; `s3:ListBucket` con `s3:prefix = envs/<env>/`; Allow por ARN de servicio de Comunes; Deny de crear/adjuntar la boundary del otro entorno (D2) |
| `infra/terraform/bootstrap/workload_boundary_dev.tf`, `workload_boundary_prod.tf` | New: `aws_iam_policy` `workload-boundary-<env>` sin state: `s3:PutObject` en `arn:aws:s3:::skyroute-<env>-data-<id>/landing/*`, `logs:CreateLogStream`/`PutLogEvents` en el log group del generador, `lambda:InvokeFunction` en `function:skyroute-<env>-generator`; Deny explícito de todo S3 sobre el bucket de state (nombre comprobado en Context) |
| `.github/workflows/terraform-apply.yml` | Modified: `apply-dev` asume `ci-apply-dev`, `apply-prod` asume `ci-apply-prod` |
| `.github/workflows/terraform-plan.yml` | Modified: `terraform plan -lock=false` (D1) |
| `docker/postgres/compose.yml`, `docker/postgres/init/001_bookings.sql`, `.env.example` | New: compose propio, `postgres:18.7`, host `127.0.0.1:5433`, volumen en `/var/lib/postgresql`; `.env.example` solo con placeholder |
| `docs/runbooks/foundations-bootstrap.md` | Modified: sección "Re-apply de bootstrap" (Ruling) con el orden de transición de Comunes, y la nota de que el environment `prod` exige reviewers y restringe ramas a `main` (S-H18) |
| `Makefile` | New: `make seed-postgres`, `make test-generators` |

PII: esquema común de Comunes (`u<sha256(customer_id)[:12]>@example.com`, sin nombres, sin teléfono/dirección). Semilla con SHA-256, no `hash()`.

### Trade-offs

| Benefit | Risk |
|---------|------|
| Zip de pocos KB, sin dependencias que medir (evita V11) y sin capa que versionar | Sin Faker los datos son menos variados; la "coherencia" (C1) depende de listas propias escritas a mano |
| Un módulo: dev y prod no pueden divergir en estructura; un solo lugar para checkov | Un módulo grande mezcla bucket e IAM; cambiar uno replanifica todo el módulo en ambos entornos |
| arm64 más barato por GB-s según tarifas US East (research H2) | arm64 en París solo lo afirma una fuente de terceros (H5.3, V8): el primer apply a dev puede fallar y obligar a cambiar a x86_64 |
| Archivos de rol separados: el diff del re-apply es legible por entorno; dos boundaries (D2) limitan cada `ci-apply-<env>` a sus ARN | Los Deny se multiplican (boundary, plan, dev, prod: cuatro copias) más dos boundaries de workload; más copias que mantener sincronizadas (T22) |
| Coste estimado ~0,05–0,3 USD/mes (Lambda dentro del nivel gratuito, SNS/CloudWatch mínimos) | Tarifas de eu-west-3 no verificadas; el backfill de dos entornos en el mismo mes suma ~2 USD |
| Puerto 5433 evita el choque con 5432 de Astro (T11) | Cualquier cliente debe recordar 5433; el host del Postgres no puede ser nombre de red de Astro (T16) |

### Validation

1. `pytest generators/tests -q`: aserción `generate(run_date="2026-05-01", slot=17) == generate(run_date="2026-05-01", slot=17)` byte a byte (Idempotency).
2. Test: el `booking_id` de cada evento `purchase` del clickstream de un día existe en las filas que `seed_postgres.py` produce para ese día (C1, C3).
3. Test: `slot_from_scheduled_time("2026-11-13T10:14:59Z") == ("2026-11-13", 40)` y `...10:15:00Z` da 41.
4. Test: el backfill `{from: D-182, to: D-1}` produce 182 × 96 claves distintas y ninguna con `run_date >= D` (Ruling: backfill termina en D-1).
5. `terraform fmt -check -recursive infra/terraform`, `terraform -chdir=infra/terraform/envs/dev validate`, `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl` (executor).
6. CI: job `static-checks` de `terraform-plan.yml` sin fallos de checkov; cada skip aparece con su motivo (V10).
7. Owner: plan local de `bootstrap/` adjunto como evidencia; tras el re-apply, CI de PR planifica `envs/dev` y `envs/prod` sin `AccessDenied` (V4).
8. Owner, T17 cerrada: `aws iam get-role --role-name ci-apply-dev` muestra un solo `sub` (`repo:javiladino@97758532/skyroute@1455233709:environment:dev`) y `aws iam simulate-principal-policy` con `ci-apply-dev` sobre `s3:GetObject` de `envs/prod/terraform.tfstate` da `implicitDeny`.
9. Owner, A3: `aws iam simulate-principal-policy --policy-source-arn <ci-apply-dev> --action-names iam:UpdateAssumeRolePolicy --resource-arns <ci-apply-prod>` da `explicitDeny`.
10. Owner, D2/A2: `simulate-principal-policy` de `ci-apply-dev` con `iam:CreateRole` y `iam:PermissionsBoundary = workload-boundary-prod` da `explicitDeny`; con `workload-boundary-dev` sobre un rol `role/workload/skyroute-dev-x` pasa; `iam:PassRole` a un rol fuera de `role/workload/skyroute-dev-*` da `explicitDeny`.
11. Owner, A4: el plan local de `bootstrap/` muestra `destroy` de `aws_iam_role.ci_apply` y `create` de `ci-apply-dev` y `ci-apply-prod`; se ejecuta en el orden del runbook.
12. Owner, A6: `simulate-principal-policy` de `ci-plan` con `lambda:GetFunction` y con `s3:GetObject` sobre `skyroute-prod-data-<id>/landing/x` da `explicitDeny`/`implicitDeny`; con `lambda:GetFunctionConfiguration` da `allowed`; `ci-plan` sobre `s3:PutObject` del `.tflock` da `implicitDeny` (D1).
13. Owner, C5 (dentro de 30 días del backfill; un entorno por mes): `aws lambda invoke --function-name skyroute-prod-generator --cli-read-timeout 0 --cli-connect-timeout 0 --payload '{"from":"...","to":"..."}' out.json` con 26 rangos de 7 días, y luego `aws s3 ls s3://skyroute-prod-data-<id>/landing/clickstream/ --recursive --summarize` muestra 17.472 objetos de 182 `ingest_date`.
14. Owner, C6: dos `aws s3 ls` separados 30 min muestran al menos un `slot=` nuevo de D en prod; en dev ninguno. `aws scheduler get-schedule --name skyroute-prod-generator --region eu-west-3` da `State = ENABLED` y en dev `State = DISABLED`.
15. Owner, A8: `aws scheduler get-schedule --name skyroute-prod-generator --region eu-west-3` muestra `RetryPolicy` con `MaximumRetryAttempts = 2` y `MaximumEventAgeInSeconds = 900`; `aws lambda get-function-configuration --function-name skyroute-prod-generator` muestra `Timeout = 60` y `MemorySize = 256`.
16. Owner, A12: tras confirmar el email, `aws sns list-subscriptions-by-topic --topic-arn <arn>` no muestra `PendingConfirmation`.
17. Owner, S-H18: `gh api repos/javiladino/skyroute/environments/prod` muestra reviewers requeridos y `deployment_branch_policy` limitada a `main`.
18. Owner, C3: `docker compose -f docker/postgres/compose.yml up -d`, `make seed-postgres`, `psql -h 127.0.0.1 -p 5433 -c "select count(*) from bookings"` > 0.
19. Test: `generate` con `PYTHONHASHSEED=0` y con `PYTHONHASHSEED=1` da el mismo resultado byte a byte (A9); un test comprueba que los emails coinciden con `^u[0-9a-f]{12}@example\.com$`.

### Open Questions

1. ¿Basta stdlib para C1, o el owner quiere Faker? Si no basta, esta propuesta se acerca a la 2.
2. Tramos del backfill: un rango de 7 días (672 slots) cabe en 900 s solo si un slot tarda < 1,3 s (sin medir, V12); si no, se reduce a un rango por día (96 slots). Con concurrencia reservada 1, cada tramo bloquea el schedule de prod mientras dura.
3. Umbral de la alarma de Invocations (p. ej. > 120 en 1 h o > 200/día): el backfill legítimo la disparará; ¿se acepta esa alerta como esperada?

## Proposal 2: Módulos por pieza, zip de código + capa de dependencias, roles por entorno generados con `for_each`

### Overview

Separar lo que cambia a ritmos distintos: el código del handler en un zip pequeño y Faker/NumPy en una capa Lambda, x86_64 y `python3.12` (la combinación con más soporte documentado). Dos módulos, `modules/landing-bucket` y `modules/ota-generator`, que cada entorno compone. En `bootstrap/`, `ci-apply-dev` y `ci-apply-prod` salen de un único bloque `for_each = toset(["dev","prod"])`, con los Deny en un `data "aws_iam_policy_document"` reutilizado. `ci-plan` usa `-lock=false` como en las demás (D1) y Postgres va como servicio en el override de Astro.

### Key Changes

| Component | Change |
|-----------|--------|
| `generators/ota/` | New: generador con Faker (`seed_instance` por `(run_date, slot, source)`) y `numpy.random.default_rng` (V13) |
| `generators/lambda_handler.py`, `generators/tests/` | New: como en la Propuesta 1 |
| `generators/layer/requirements.txt`, `generators/layer/requirements.lock` | New: `faker==40.54.0`, `numpy==2.5.4` fijados (research H7); el lock lleva `--hash=sha256:...` de cada wheel y se instala con `pip install --require-hashes --only-binary=:all:` (S-H11) |
| `infra/terraform/modules/landing-bucket/` | New: bucket, lifecycle, política TLS, public access block, ownership |
| `infra/terraform/modules/ota-generator/` | New: capa, función, log group, schedule, roles de workload, SNS, alarma; recibe el ARN del bucket |
| `infra/terraform/envs/{dev,prod}/main.tf` | Modified: componen los dos módulos; `schedule_enabled` por entorno |
| `.github/workflows/terraform-plan.yml`, `terraform-apply.yml` | Modified: job (o paso previo) de build **sin credenciales AWS**, antes de `configure-aws-credentials`/OIDC: `pip install --target build/layer/python --require-hashes -r generators/layer/requirements.lock --platform manylinux2014_x86_64 --only-binary=:all:`; el zip pasa al job de plan/apply como artefacto; un rol por job de apply; `plan -lock=false` (D1) |
| `infra/terraform/bootstrap/ci_roles.tf` | Modified: `ci-apply` pasa a `aws_iam_role.ci_apply["dev"/"prod"]` con `for_each` (el `name` cambia, así que es destroy/create, ver Trade-offs); trust `StringEquals` con un solo `sub` de ID inmutable por rol (`ci_roles.tf:246-247`) y `s3:ListBucket` con `s3:prefix = envs/<env>/`; `ci-plan` pierde `PutObject`/`DeleteObject` del `.tflock` (`:152-158`) y gana la fila de metadatos de Comunes; `local.ci_apply_role_arn` y `DenyCiAndOidcChanges` listan todos los roles de CI; los Deny reemplazados de Comunes viven en un documento local compartido por boundary e inline (reduce T22); `DenyBoundaryPolicyChanges` añade las boundaries de workload |
| `infra/terraform/bootstrap/workload_boundary.tf` | New: dos `aws_iam_policy` (`workload-boundary-dev`, `-prod`, con `for_each`) con el contenido de la Propuesta 1 (ARN exactos por entorno) |
| `airflow/docker-compose.override.yml` (proyecto Astro, aún no existe) | New: servicio `ota-postgres` `postgres:18.7`, host `127.0.0.1:5433` |
| `docs/runbooks/foundations-bootstrap.md` | Modified: sección "Re-apply de bootstrap": destroy de `ci-apply` y create de `ci-apply-dev`/`ci-apply-prod` en el orden de Comunes (un `moved` no sirve porque el `name` cambia); ventana sin rol de apply; el environment `prod` exige reviewers y rama `main` (S-H18) |

PII: esquema común de Comunes: Faker solo para campos no personales (fechas, importes, rutas, códigos de aeropuerto); sin proveedores `name`, `phone_number` ni `address`; email `u<sha256(customer_id)[:12]>@example.com`. Semilla con SHA-256: `Faker.seed_instance(seed)` y `default_rng(seed)` con el `seed` de Comunes.

### Trade-offs

| Benefit | Risk |
|---------|------|
| Faker da variedad realista para C1 sin escribir listas | Tamaño de Faker + NumPy empaquetado sin medir (V11); la capa tiene que caber en 250 MB descomprimido junto con el código (H2) |
| La capa cambia poco: un cambio del handler no resube dependencias | El build de la capa corre en CI: `plan` de PR y `apply` deben producir el mismo zip byte a byte, o el apply ve un hash distinto al del plan |
| Dos módulos: cambiar el bucket no toca la función | Dependencia entre módulos por output; más archivos para checkov y tflint |
| `for_each` en bootstrap: un solo bloque de Deny para dev y prod, menos copias (T22) | El `name` pasa de `ci-apply` a `ci-apply-<env>`: Terraform lo reemplaza (destroy/create) aunque haya `moved`; hay una ventana sin rol de apply y el orden del runbook importa (Comunes, A4) |
| Coste estimado ~0,05–0,45 USD/mes (más import de Faker en cada arranque en frío: sin medir) | Tarifas de eu-west-3 no verificadas; el import de Faker alarga cada slot y puede forzar rangos de backfill más cortos |
| Dependencias fijadas con hashes: el zip es reproducible y verificable | Mantener `requirements.lock` con hashes por wheel; un `pip` sin `--require-hashes` aceptaría paquetes sustituidos (S-H11) |
| Postgres en el override de Astro: un solo `astro dev start` levanta todo | Ata el Postgres de datos a la red y al ciclo de vida de Astro (T16, V15): `astro dev kill` puede borrar sus volúmenes; además `airflow/` aún no existe y esta fase lo crearía antes de su topic |

### Validation

1. Validaciones 1-4 y 6-19 de la Propuesta 1, con `skyroute-<env>-generator` (la 11 es la de A4, que aquí también muestra el reemplazo).
2. Executor: `pip install --target build/layer/python --require-hashes -r generators/layer/requirements.lock --only-binary=:all:` y medir el directorio < 250 MB (V11); instalar con un hash alterado debe fallar.
3. CI: dos ejecuciones de `plan` sobre el mismo commit dan el mismo `source_code_hash` de la capa; el paso de build no tiene credenciales AWS (`grep` del workflow: el job de build no usa `configure-aws-credentials`).
4. Owner: el plan local de `bootstrap/` muestra `replace`/`destroy` de `ci-apply` y `create` de `ci-apply-dev` y `ci-apply-prod`.
5. Owner, C3: `astro dev start`, `psql -h 127.0.0.1 -p 5433 -c "select count(*) from bookings"` > 0; tras `astro dev stop` y `start`, el conteo se mantiene.

### Open Questions

1. ¿Se acepta crear `airflow/docker-compose.override.yml` en Fase 2, antes del topic de Airflow?
2. Wheels de NumPy para manylinux x86_64 y Python 3.12: disponibles según PyPI (H7), no comprobado contra la imagen de Lambda.
3. Si se prefiere un solo `plan` de PR y `apply` con el mismo zip, el paso de build sin credenciales debe publicar un artefacto firmado por hash; ¿basta el artefacto de Actions?

## Proposal 3: Imagen de contenedor única para Lambda y local, con ECR por entorno

### Overview

Paridad local/AWS: una sola imagen (`public.ecr.aws/lambda/python:3.13`, arm64, **fijada por digest** `@sha256:...`) contiene el generador y se usa tanto como Lambda (`package_type = "Image"`) como, en local, para sembrar Postgres con `docker compose run`. Un repositorio ECR por entorno, creado por Terraform. `ci-plan` sigue siendo un solo rol, con `-lock=false` (D1). Separarlo por entorno no es real: toda PR comparte el `sub` `...:pull_request` (`ci_roles.tf:121`), así que un rol por entorno con el mismo trust no limitaría nada; solo se podría con un `sub` personalizado de `job_workflow_ref`, **no verificado** (descartado de esta propuesta). Un compose local con perfiles reparte puertos entre Postgres, Astro y OpenMetadata/Marquez.

### Key Changes

| Component | Change |
|-----------|--------|
| `generators/Dockerfile`, `generators/ota/`, `generators/lambda_handler.py`, `generators/tests/` | New: imagen con Faker fijado y base por digest; `CMD` del handler; entrypoint alternativo `python -m ota.seed_postgres` |
| `infra/terraform/modules/generator-landing/` | New: como Propuesta 1 más `aws_ecr_repository` (`skyroute-<env>-generator`, `image_tag_mutability = IMMUTABLE`, `scan_on_push = true` básico, sin escaneo mejorado), lifecycle policy de ECR (conservar 3 imágenes) y `aws_ecr_repository_policy` que permite a `lambda.amazonaws.com` `ecr:BatchGetImage`/`ecr:GetDownloadUrlForLayer` con `aws:sourceARN` de la función (lista de acciones y condición inferidas de la guía de Lambda con imágenes de contenedor, no verificadas; V-nuevo) |
| `.github/workflows/terraform-apply.yml` | Modified: **el build se hace antes de asumir el rol**, en un paso sin credenciales AWS (`docker buildx build --platform linux/arm64`, base por digest); luego se asume `ci-apply-<env>` y se hace `docker push` solo a `repository/skyroute-<env>-generator` con tag = SHA del commit; después apply con `image_uri` por variable. **Orden del primer apply (resuelto):** (1) PR 1 crea el repositorio ECR y su policy con la función **desactivada** (`create_function = false`, variable del módulo); (2) el apply de esa PR deja el repositorio vacío; (3) el workflow empuja la imagen; (4) PR 2 pone `create_function = true` y `image_uri` con el SHA y crea función, schedule y alarma. No hace falta `-target` ni dos applies manuales: son dos merges consecutivos con el mismo workflow |
| `.github/workflows/terraform-plan.yml` | Modified: `terraform plan -lock=false` (D1); un solo rol `ci-plan` |
| `infra/terraform/bootstrap/ci_roles.tf` | Modified: `ci-plan` (un rol, sin `PutObject`/`DeleteObject` del `.tflock`, con la fila de metadatos de Comunes más `ecr:Describe*`/`Get*Policy`/`ListTagsForResource`) y `ci-apply-{dev,prod}` con trust `StringEquals` de un `sub` de ID inmutable cada uno (`ci_roles.tf:246-247`); permisos ECR: `ecr:GetAuthorizationToken` (`Resource = "*"`, no admite recurso) y push (`InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`, `PutImage`, `BatchCheckLayerAvailability`) solo sobre `arn:aws:ecr:eu-west-3:<account_id>:repository/skyroute-<env>-generator`; `local.ci_apply_role_arn` y `DenyCiAndOidcChanges` listan todos los roles de CI; `DenyCreateRoleWithoutBoundary` **reemplazado** en las tres copias (Comunes); `DenyBoundaryPolicyChanges` añade las boundaries |
| `infra/terraform/bootstrap/workload_boundary_dev.tf`, `workload_boundary_prod.tf` | New: como Propuesta 1 (dos boundaries, D2). Sin permisos de ECR: la extracción de la imagen la hace el servicio Lambda con la `aws_ecr_repository_policy`, no el rol de ejecución, así que `ecr:BatchGetImage`/`GetDownloadUrlForLayer` no van en la boundary (se añadirían solo si V-nuevo demuestra que hacen falta) |
| `docker/compose.yml` | New: perfil `data` (`postgres:18.7` en `127.0.0.1:5433`), perfil `observability` (Marquez con su `postgres:14` en `127.0.0.1:5434`, API en 5000/5001, OpenMetadata 8585-8586 y su Airflow de ingesta remapeado a 8081); Astro queda con 5432 y 8080 |
| `docs/runbooks/foundations-bootstrap.md` | Modified: re-apply de bootstrap con el orden de transición de Comunes; orden del primer apply (repositorio, push, función); el environment `prod` exige reviewers y rama `main` (S-H18) |

PII: esquema común de Comunes (es el de esta propuesta, adoptado por las tres).

### Trade-offs

| Benefit | Risk |
|---------|------|
| El mismo artefacto siembra Postgres y corre en Lambda: la coherencia de ids (C1, C3) no depende de dos entornos Python | Primer apply resuelto en dos merges (repositorio con función desactivada, push, función) sin `-target` (research componente 5): dos PR consecutivas y una variable `create_function` que solo existe por este orden; si el push falla tras el primer merge, la función no se crea |
| Límite de 10 GB de imagen frente a 250 MB del zip (H2): no hay que medir Faker | ECR almacena por GB-mes (no por hora, cumple No hourly-billed resources) pero su tarifa en eu-west-3 y su nivel gratuito no están verificados (V7); coste estimado ~0,35–0,9 USD/mes, de ellos ECR 0,30–0,60 |
| Imagen base por digest, build sin credenciales y push limitado a un repositorio: el artefacto es verificable | Un digest fijado exige renovarlo a mano para recibir parches de la base; `scan_on_push` básico avisa pero no bloquea |
| Puertos fijados para todo el stack local previsto (T11) | Fija ahora puertos de `observability/`, que es de otra fase; Marquez y OpenMetadata aún no existen |
| `docker build` en CI con imagen pública de AWS | El push da a `ci-apply-<env>` permisos ECR nuevos; el job de apply crece en minutos de Actions |
| Un solo `ci-plan`: sin cambio de trust ni de copias respecto a hoy | Cuatro copias de Deny (`ci-boundary`, `ci-plan`, `ci-apply-dev`, `ci-apply-prod`) más las dos boundaries de workload; T22 sigue abierta |

### Validation

1. Validaciones 1-4 y 6-19 de la Propuesta 1 (la 12 añade `ecr:Describe*` permitido y push de ECR denegado a `ci-plan`).
2. Executor: `docker build --platform linux/arm64 -t ota-gen generators/` y `docker run --rm --entrypoint python ota-gen -m pytest /var/task/tests -q`; `grep -n "FROM" generators/Dockerfile` muestra la base con `@sha256:`.
3. Executor: `docker compose -f docker/compose.yml --profile data config` lista solo el puerto `127.0.0.1:5433`; `--profile observability config` no publica 5432 ni 8080.
4. Owner: `aws ecr describe-images --repository-name skyroute-dev-generator --region eu-west-3` muestra el tag del SHA del merge.
5. Owner: `aws iam simulate-principal-policy` con `ci-apply-dev` sobre `ecr:PutImage` en `repository/skyroute-prod-generator` da `implicitDeny` y sobre `repository/skyroute-dev-generator` da `allowed`.
6. Owner: `aws ecr get-repository-policy --repository-name skyroute-dev-generator --region eu-west-3` muestra el principal `lambda.amazonaws.com`; `aws lambda get-function-configuration --function-name skyroute-dev-generator` muestra `State = Active` tras el segundo merge.
7. Executor: `grep -n "configure-aws-credentials" .github/workflows/terraform-apply.yml` aparece después del paso `docker buildx build` (build sin rol).

### Open Questions

1. ¿Se acepta fijar puertos de `observability/` antes de su topic?
2. Tarifa y nivel gratuito de ECR en eu-west-3 (V7).
3. ¿Qué acciones exactas exige Lambda en la policy del repositorio ECR y si el rol de ejecución necesita algo de ECR (V-nuevo; no verificado)?
4. ¿Quién renueva el digest de la imagen base y con qué cadencia?

## Skips de checkov previstos (las tres propuestas)

Por recurso, con `#checkov:skip=<ID>:<motivo>` en el bloque; nunca en la config global (Ruling; patrón `state_bucket.tf:5-8`). Los IDs son candidatos: qué reglas disparan de verdad lo dice el primer `static-checks` de CI (V10). CKV_AWS_273/274 siguen solo en `bootstrap/owner_user.tf` (Convention "Bootstrap identity").

| Recurso | ID candidato | Motivo |
|---------|--------------|--------|
| bucket de datos | CKV_AWS_21 | Sin versioning por Ruling (lifecycle 30 días, datos regenerables) |
| bucket de datos | CKV_AWS_145 | SSE-S3 por Ruling; KMS vetado (`foundations/current/plan.md:237`) |
| bucket de datos | CKV_AWS_18 (riesgo aceptado, **sin skip por ahora**) | Sin access logging, como el bucket de state (`state_bucket.tf:7`); el skip solo se añade, con motivo, si la regla dispara en el primer `static-checks` |
| bucket de datos | CKV_AWS_144 | Sin replicación entre regiones (Region) |
| bucket de datos | CKV2_AWS_62 | Sin notificaciones de eventos: no hay consumidor en Fase 2 |
| función Lambda | CKV_AWS_117 | Sin VPC (No hourly-billed resources) |
| función Lambda | CKV_AWS_116 | Sin DLQ: RetryPolicy acotada y regeneración determinista |
| función Lambda | CKV_AWS_173 | Sin variables de entorno secretas; KMS vetado |
| función Lambda | CKV_AWS_272 | Sin code signing (coste y complejidad de portfolio) |
| función Lambda | CKV_AWS_50 | Sin X-Ray |
| log group | CKV_AWS_158 | Sin KMS (vetado) |
| log group | CKV_AWS_338 | Retención 14 días por Ruling, no 1 año |
| topic SNS | CKV_AWS_26 | Sin KMS (vetado); el contenido es una alarma |
| repositorio ECR (solo P3) | CKV_AWS_136 | Sin KMS (vetado) |

## Recommendation

| Criteria | Proposal 1 | Proposal 2 | Proposal 3 |
|----------|-----------|-----------|-----------|
| C1 Simulador OTA coherente | Sí, con listas propias; menos variedad | Sí, Faker | Sí, Faker; mismo artefacto en Lambda y local |
| C2 Lambda + EventBridge en eu-west-3 | Sí; riesgo arm64 (V8) | Sí; x86_64 con menos dudas | Sí; riesgo arm64 y primer apply en dos pasos |
| C3 Postgres local | Compose propio, 5433 | Override de Astro (crea `airflow/` antes de tiempo) | Compose con perfiles, 5433 |
| C4 Archivos en `landing/` | Sí | Sí | Sí |
| C5 / Ruling: backfill de 182 días | Sí, por tramos (Q1.2) | Sí, por tramos; más lento por import de Faker (sin medir) | Sí, por tramos; arranque en frío de imagen (sin medir) |
| C6 / Ruling: el schedule añade micro-lotes | Sí, prod ENABLED | Sí | Sí |
| T17 (state de prod desde dev) cerrada | Sí | Sí; `ci-apply` se reemplaza (destroy/create), no se mueve | Sí |
| T19 (PR con `ci-plan`) | `-lock=false` (D1), sin escritura | `-lock=false` (D1) | `-lock=false` (D1); sin `ci-plan` por entorno (mismo `sub` de PR) |
| Coste estimado (No hourly-billed resources; eu-west-3 no verificado) | ~0,05–0,3 USD/mes | ~0,05–0,45 USD/mes | ~0,35–0,9 USD/mes (ECR 0,30–0,60, V7) |
| Superficie IAM nueva en CI | Menor | Menor | Mayor (ECR, push por rol) |
| Copias de Deny a sincronizar (T22) | Cuatro (más dos boundaries de workload) | Dos documentos compartidos (más dos boundaries) | Cuatro (más dos boundaries) |
| Cadena de suministro | Sin dependencias de terceros | Faker/NumPy con `--require-hashes`, build sin credenciales | Base por digest, build sin credenciales, push acotado |
| Primer apply | Un merge | Un merge | Dos merges consecutivos (repositorio, push, función) |

**Cuándo elegir cada una.** La 1 si prima la superficie mínima y el owner acepta datos menos ricos. La 2 si prima la variedad de Faker y el owner acepta mantener un lock de hashes y una capa x86_64. La 3 si prima la paridad local/AWS, a costa de ECR, más IAM en CI y un primer apply en dos merges. El lock de `ci-plan` ya no distingue entre ellas (D1).

**Gaps comunes.** Ninguna resuelve sola: la lista exacta de acciones IAM del refresh (V4) ni si hacen falta `Describe*`/`List*` con `Resource = "*"` en Allow (T5); arm64 y Lambda/Scheduler en eu-west-3 (V1, V8; el Ruling dice que se prueba con el primer apply a dev); la ventana de 30 días para tomar la evidencia de C5 (T1); la colisión del backfill con el schedule de prod bajo concurrencia reservada 1; la extracción de Reservas a `landing/`, aplazada por Ruling.

**Recomendación del autor:** Propuesta 1, con la combinación opcional de `for_each` y documento de Deny compartido de la Propuesta 2 en `bootstrap/` si el owner prefiere menos copias. Motivo: con D1 el lock ya no separa las propuestas; la 1 tiene la menor superficie IAM, el menor coste (~0,05–0,3 USD/mes), ninguna dependencia de terceros que fijar, un primer apply en un solo merge y no crea carpetas de fases futuras. Su coste es la menor variedad de datos (Open Question 1). La elección es del owner.

## Decision

**Elegida: Propuesta 1** (javiladino, 2026-11-13). Un módulo `modules/generator-landing`, zip único con stdlib, arm64, roles `ci-apply-dev`/`ci-apply-prod` en archivos separados, sin la combinación opcional de `for_each` de la Propuesta 2. Se aplican las decisiones previas del owner D1 (`-lock=false` obligatorio en `ci-plan`) y D2 (una boundary de workload por entorno). Siguiente: Plan sobre esta propuesta.
