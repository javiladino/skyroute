---
type: Plan
---

# generator-landing: Simulador OTA, Lambda + Scheduler y `landing/` Design Document

> **Propuesta implementada:** Propuesta 1 de `working/proposal.md` § Decision (javiladino, 2026-11-13): un módulo `modules/generator-landing`, zip único con stdlib, arm64, roles `ci-apply-dev`/`ci-apply-prod` en archivos separados, sin el `for_each` de la Propuesta 2; con D1 y D2 (Ruling "Propose decisions").
> **Reglas que aplica (sin reabrir):** Ruling "Research decisions" y Ruling "Propose decisions" (`../context.md` § Rulings); Conventions "Region", "IaC only", "Apply gate", "No hourly-billed resources", "Idempotency", "Medallion layers", "Bootstrap identity", "Verification ownership" y "Simple shell commands" (`docs/design/CONTEXT.md` § Conventions).
> **Método:** ningún agente ejecutó `terraform plan`/`apply` ni comandos AWS (Convention "Apply gate"). Las líneas citadas se leyeron el 2026-11-13 en la rama `docs/generator-landing-plan`.
> **Decisiones del owner (2026-11-13, tras la ronda de revisión):** (1) Transición: crear antes de destruir, con dos re-applies (Fases 5 y 8); la ventana sin rol solo existe en la vuelta atrás; la PR del módulo (Fase 9) espera a la Fase 8. (2) Alcance: solo lo de la Propuesta 1 (clickstream en `landing/` y Reservas en Postgres local); las demás fuentes son OQ8, fuera de este plan.
> **Verificado por executor (2026-11-13, `gh api`):** environment `dev` con `can_admins_bypass:false`, `deployment_branch_policy.custom_branch_policies:true` y una sola branch policy `main`; `prod` igual más `required_reviewers` (javiladino, `prevent_self_review:false`). `terraform-plan.yml` (trigger `pull_request`) no declara `environment:`; `terraform-apply.yml` solo se dispara por `push` y sus jobs son `apply-dev` (environment `dev`) y `apply-prod` (environment `prod`, `needs: apply-dev`).
> **Pendiente al cerrar el ciclo (no lo hace este plan):** enmendar el Ruling Foundations design (`foundations/context.md`): de dos roles de CI a tres (`ci-plan`, `ci-apply-dev`, `ci-apply-prod`) y las boundaries de workload; y registrar D2 como refinamiento del Ruling "Research decisions" (línea Boundary).

## Current Context

- `envs/dev` y `envs/prod` solo tienen backend y provider (`infra/terraform/envs/dev/backend.tf:1-21`, `envs/prod/backend.tf`); no existen `generators/`, `infra/terraform/modules/`, `docker/`, `Makefile` ni `.env.example` (research § Lo que existe hoy).
- `bootstrap/ci_roles.tf` define `ci-boundary` (`:12-100`), `ci-plan` (`:104-224`) y `ci-apply` (`:228-351`); boundary e inline solo conceden state y lock (research Hecho (a)). Los Deny están copiados tres veces (`:36-97`, `:160-221`, `:287-348`; T22).
- `ci-apply` acepta `environment:dev` y `environment:prod` (`:245-248`) y escribe el state de prod (`:270-285`): un job de `dev` puede escribir el state de prod (research Hecho (c), T17). El Ruling "Research decisions" (línea Prod) ordena corregirlo antes de ampliar permisos.
- `ci-plan` escribe el `.tflock` (`:151-159`) desde código de PR (T19); `terraform-plan.yml:63` planifica con lock. D1 lo cierra.
- `DenyCreateRoleWithoutBoundary` (`:55-65`, `:179-189`, `:306-316`) impide crear roles de workload con otra boundary, y `DenyCiAndOidcChanges` (`:45-54`, `:169-178`, `:296-305`) solo protege `ci-plan`, `role/ci-apply` (`local.ci_apply_role_arn`, `:6`) y el OIDC (proposal § Key constraints).

## Requirements

### Functional Requirements

Criterio de hecho (Ruling "Research decisions", línea Histórico): "La Fase 2 está hecha cuando un backfill deja 182 días en `landing/` y el schedule añade micro-lotes." Se descompone en C1-C6 (research § Criterio de hecho).

- **FR1 (C1).** Generador determinista solo con stdlib: `(run_date, slot, source)` produce los mismos bytes en cualquier proceso; claves compartidas `customer_id`, `session_id`, `booking_id`, `campaign_id`, `currency` (proposal P1 Key Changes, `generators/ota/`).
- **FR2 (C2).** Lambda `skyroute-<env>-generator` (arm64, `python3.13`, zip con `archive_file`) y schedule `skyroute-<env>-generator` de EventBridge Scheduler cada 15 min en `eu-west-3`, creados por Terraform (Conventions "Region", "IaC only").
- **FR3 (Ruling, Tiempo lógico).** Rama schedule: `scheduled_time` redondeado hacia abajo a 15 min da `(run_date, slot)`. Rama backfill: payload `{from, to}`, termina en D-1. Nunca `now()` para generar datos (Convention "Idempotency"). **Única excepción de reloj:** el handler lee el reloj UTC solo para validar `to <= hoy-1` y rechazar un backfill con fechas futuras; el reloj no influye en ningún byte escrito. **D es una fecha concreta, no un cálculo:** la fija el owner tras la Fase 9 (OQ9); opción por defecto, la fecha del primer slot del schedule de prod. El backfill cubre `D-182` a `D-1` y la evidencia (TS-O1) se calcula con esa D, no con la fecha del día en que se mide.
- **FR4 (C4).** Clave `landing/clickstream/ingest_date=<run_date>/slot=<NN>/part.json.gz` en el bucket `skyroute-<env>-data-<account_id>`; reentrega reescribe el mismo objeto (Convention "Medallion layers": `landing/` crudo, 30 días).
- **FR5 (C3).** Postgres local `postgres:18.7` en `127.0.0.1:5433`, sembrado por el mismo generador con `booking_id` coherentes con los `purchase` del clickstream. Extracción a `landing/` aplazada (Ruling, línea Reservas).
- **FR6 (C5).** Backfill de 182 días en prod = 17.472 objetos de 182 `ingest_date`, evidenciado dentro de los 30 días del lifecycle (T1).
- **FR7 (C6).** Schedule `ENABLED` en prod y `DISABLED` en dev por la variable `schedule_enabled` (Ruling, línea Schedule).
- **FR8 (Ruling, línea Prod; D2).** `ci-apply` se sustituye por `ci-apply-dev` y `ci-apply-prod`, cada uno con un solo `sub` y solo el state de su entorno; cada uno crea o adjunta solo `workload-boundary-<env>`.
- **FR9 (D1).** `terraform plan -lock=false` en `ci-plan`; `ci-plan` pierde `PutObject`/`DeleteObject` sobre el `.tflock` y gana solo lectura de metadatos.

### Non-Functional Requirements

- **Coste:** ~0,05–0,3 USD/mes estimado (proposal P1 Trade-offs; tarifas de eu-west-3 sin verificar). Topes: `timeout = 60` en régimen normal, `memory_size = 256`, `reserved_concurrent_executions = 1` (proposal § Comunes; Ruling, línea Schedule), **este último condicionado a la PR-Q**: la cuota de la cuenta es 10 (PC6) y la Fase 9 se despliega sin concurrencia reservada (Ruling Implement decisions, "Concurrencia (PC6)"); mientras tanto, los topes son el timeout, la `retry_policy` del Scheduler, la alarma de `Invocations` y la cuota de 10 de la cuenta. Reintentos, dos mecanismos distintos que no se mezclan: la `retry_policy { maximum_retry_attempts = 2, maximum_event_age_in_seconds = 900 }` existe **solo en el Scheduler**; la función lleva `aws_lambda_function_event_invoke_config` con **0 reintentos y 900 s** de edad máxima de evento, de modo que los únicos reintentos son los del Scheduler (proposal § Comunes, A8). Ningún recurso con cobro por hora (Convention "No hourly-billed resources": sin VPC).
- **Observabilidad:** log group con 14 días, alarma de `Invocations` a SNS por email (Ruling, línea Schedule).
- **Seguridad:** sin secretos en la Lambda; PII sintética con email `u<sha256(customer_id)[:12]>@example.com`; ARNs exactos por servicio y entorno (proposal § Comunes).
- **Reproducibilidad:** semilla `sha256(f"{run_date}|{slot}|{source}")`, nunca `hash()` (A9).

## Design Decisions

### 1. Generador solo con stdlib, zip único con `archive_file`
Se implementa `random.Random(seed)` con la semilla SHA-256 de Comunes y boto3 del runtime, empaquetado por `data "archive_file"` en el módulo (proposal P1 Overview; § Decision).
- Evita medir Faker (V11) y no hay dependencias que fijar ni capa que versionar.
- Trade-off: menos variedad de datos; C1 depende de listas propias (Open Question OQ1).
- Alternativas descartadas por la Decision: Faker en capa (P2), imagen de contenedor con ECR (P3).

### 2. arm64 y `python3.13`, con salida a x86_64 por variable
La función usa `architectures = [var.architecture]` con default `"arm64"` (proposal P1 Overview).
- Más barato por GB-s (research H2); arm64 en París solo lo afirma una fuente de terceros (V8). El Ruling "Research decisions" (línea Plan Free) fija que Region se prueba con el primer apply a dev.
- Si el apply a dev falla por arquitectura, el owner cambia la variable a `"x86_64"` en una PR; el código stdlib no depende de arquitectura. Pendiente PC1.

### 3. Un módulo `modules/generator-landing` llamado por los dos entornos
Bucket, función, log group, schedule, roles de workload, SNS y alarma en un módulo; `envs/<env>/main.tf` solo pasa `env`, `schedule_enabled`, `alarm_email` y `backfill_timeout` (proposal P1 Key Changes).
- dev y prod no divergen en estructura; un solo lugar para skips de checkov.
- Trade-off aceptado: cualquier cambio replanifica todo el módulo en ambos entornos.

### 4. Roles de CI por entorno en archivos separados (sin `for_each`)
`ci_apply_dev.tf` y `ci_apply_prod.tf`, cada uno con rol e inline propios; `ci_roles.tf` conserva `ci-boundary` y `ci-plan` (proposal § Decision: "sin la combinación opcional de `for_each`").
- Diff legible por entorno en el plan del owner.
- Trade-off: cuatro copias de Deny (`ci-boundary`, `ci-plan`, `ci-apply-dev`, `ci-apply-prod`) más dos boundaries de workload (T22). Se mitiga con el check TS-B4 (cada Sid esperado aparece el número de veces de su tabla por archivo).
- `ci-apply-<env>` sigue con `permissions_boundary = ci-boundary`; `ci-boundary` se amplía con los ARN por servicio de los dos entornos, porque es común. El aislamiento por entorno lo dan la inline de cada rol y el Deny de D2. Esto es una lectura del plan sobre la proposal, que no fija qué boundary lleva `ci-apply-<env>`: queda **provisional hasta que el owner resuelva OQ6**, que es gate de la PR-B1 (Fase 4). La alternativa es `ci-boundary-<env>`, una boundary de CI por entorno, para que el techo de `ci-apply-dev` no incluya los ARN de prod (hallazgo S7).

### 5. Una boundary de workload por entorno (D2)
`workload_boundary_dev.tf` y `workload_boundary_prod.tf` con `aws_iam_policy` `workload-boundary-<env>`: solo `s3:PutObject` en `landing/*` de su bucket, logs del generador y `lambda:InvokeFunction` de su función; Deny de todo S3 sobre el bucket de state (Ruling "Propose decisions", línea Boundary).
- `DenyCreateRoleWithoutBoundary` se **reemplaza** en sus copias por los Deny (a)-(c) de proposal § Comunes "Deny reemplazados": en `ci-boundary` y `ci-plan` la condición admite solo las dos workload boundaries (CI ya no crea roles con `ci-boundary`); en cada `ci-apply-<env>` solo la de su entorno.
- Alternativa descartada por el owner: una sola `workload-boundary` (texto original del Ruling "Research decisions", refinado por D2).

### 6. `ci-plan` sin lock y con lectura de metadatos (D1)
`terraform-plan.yml` pasa a `-lock=false`; la inline de `ci-plan` pierde el Sid `StateLock` (`ci_roles.tf:151-159`) y gana la fila de lectura de metadatos de Comunes con los Deny de `s3:GetObject` sobre `skyroute-*-data-*/*` y Deny de lectura de logs (Ruling "Propose decisions", línea Lock).
- **Atribución corregida:** el Ruling línea Lock fija `-lock=false` y la lectura de metadatos; la exclusión de `lambda:GetFunction` **no viene del Ruling**, viene de proposal § Comunes "Fila de `ci-plan`" (A6, S-H8: la acción devuelve una URL prefirmada del código).
- **Riesgo (A1, alta):** el refresh de `aws_lambda_function` llama a `GetFunction`; con la acción excluida, todo plan de PR falla tras la Fase 9 en cuanto el state contenga la función. Es decisión del owner (OQ10, Future Considerations); este plan no la resuelve, y TS-A3 la detecta con un plan de PR posterior al primer apply.
- El workflow cambia **antes** de quitar el permiso: si se quita primero, todo plan de PR falla al pedir el lock.
- `ci-boundary` conserva el `.tflock` en `AllowStateObjects` (`:25-35`) porque los roles de apply sí lo usan.

### 7. Transición de `ci-apply` en dos re-applies de `bootstrap/`
`ci-apply-dev`/`ci-apply-prod` se crean en un primer re-apply con `ci-apply` aún presente; `terraform-apply.yml` cambia en una PR aparte; `ci-apply` se destruye en un segundo re-apply (orden (1)-(4) de proposal § Comunes "Orden de transición", A4).
- Un `moved` no evita el reemplazo porque cambia `name`.
- **Decisión del owner (2026-11-13): crear antes de destruir.** Cierra el choque con el texto de proposal § Comunes "Orden de transición" (que habla de una ventana entre destroy y create): los dos re-applies son las Fases 5 (crear) y 8 (destruir), y no hay ventana en el camino normal.
- Ventaja de partirlo en dos: entre el primer y el segundo re-apply sigue habiendo un rol de apply válido; la ventana sin rol solo existe en la vuelta atrás (Rollout Strategy).
- Restricción derivada del Ruling (línea Prod: corregir T17 antes de ampliar permisos): la PR del módulo (Fase 9) no se mergea hasta que `ci-apply` esté destruido, y `ci-apply` nunca recibe permisos nuevos.

### 8. Email de la alarma fuera del repo
`alarm_email` es variable Terraform con `sensitive = true` (en el módulo y en `envs/*/variables.tf`, S3), sin default ni `tfvars` versionado; los workflows la pasan como `TF_VAR_alarm_email` desde una variable de repositorio de GitHub (proposal § Comunes). El job de plan no usa environment, así que una variable de environment no le llegaría; se propone variable de repositorio (OQ5).

### 9. Postgres en compose propio, puerto 5433
`docker/postgres/compose.yml` con `postgres:18.7`, `127.0.0.1:5433`, volumen en `/var/lib/postgresql`, `POSTGRES_PASSWORD` desde `.env` ignorado (`.gitignore:51-52`) (proposal P1 Key Changes; T11). `.env` no existe en un clon limpio, y Compose falla en `config` si un `env_file` falta: el compose declara `env_file` con `required: false` y el `Makefile` tiene un objetivo previo que copia `.env.example` a `.env` solo si no existe (A7). `.gitignore:52` (`.env.*`) también ignora `.env.example`; se añade la excepción `!.env.example` (ver Files Changed).
- Ni el archivo `.env` ni su contenido se leen ni se imprimen en ninguna fase.

## Technical Design

### 1. Core Components
- `generators/ota/keys.py`: `seed_for(run_date: str, slot: int, source: str) -> int` (SHA-256 de Comunes) y derivación de ids estables (`customer_id`, `session_id`, `booking_id`, `campaign_id`).
- `generators/ota/model.py`: catálogos propios (rutas, aeropuertos, campañas, divisas) y reglas de coherencia; listas escritas a mano (OQ1).
- `generators/ota/clickstream.py`: `generate(run_date: str, slot: int) -> bytes` (JSON lines gzip con `mtime=0` para que el gzip sea byte a byte estable); inyecta duplicados y tardíos por semilla, nunca por reloj.
- `generators/ota/seed_postgres.py`: `rows_for_day(run_date: str) -> list[dict]` y un `main()` que inserta en Postgres local; los `booking_id` salen de las mismas funciones que los `purchase` del clickstream. Sin dependencias de terceros en el código de Lambda; el driver de Postgres de esta pieza local se decide en OQ7.
- `generators/lambda_handler.py`: `handler(event, context)`. Evento con `scheduled_time` → `slot_from_scheduled_time()` → un `PutObject`. Evento con `from`/`to` → recorre slots de `from` 00:00 a `to` 23:45, con `to <= hoy-1` (si no, error sin escribir; es la única lectura de reloj, solo para validar, FR3). Entrada de Lambda `lambda_handler.handler`; los imports son absolutos desde la raíz del zip (`from ota.keys import ...`), sin prefijo `generators.` (A12). `boto3` se importa solo dentro del writer real. Error de validación del evento: excepción sin reintento útil. Logs solo con clave, conteo, `run_date` y `slot`.
- `generators/verify_landing.py`: `expected_keys(d: str) -> set[str]` (las 182 × 96 claves de `D-182` a `D-1`, con la misma función de clave que el generador) y un `main()` que lee un listado de claves guardado a archivo, compara por prefijo `ingest_date` y escribe el recuento por día y las claves que faltan o sobran (A5). Solo stdlib; no entra en el zip.
- `infra/terraform/modules/generator-landing`: entradas `env`, `schedule_enabled`, `alarm_email` (`sensitive = true`), `architecture` (default `"arm64"`), `backfill_timeout` (default `60`; el valor de la ventana de backfill lo pone la PR de la Fase 10, OQ2), `alarm_threshold` (OQ3); salidas `bucket_name`, `function_name`, `topic_arn`.
- Empaquetado (A12): `data "archive_file"` con `type = "zip"`, `source_dir = "${path.module}/../../../../generators"` (raíz del repo desde `infra/terraform/modules/generator-landing`), `excludes = ["tests", "ota/seed_postgres.py", "verify_landing.py", "__pycache__"]` y `output_path` bajo `${path.root}/.terraform/` (ignorado, `.gitignore:5`). `handler = "lambda_handler.handler"`. Que `excludes` acepte directorios no está verificado; lo cubre TS-U9 para el contenido importable y queda como PC7 para el zip real.

### 2. Data Models
- Objeto de `landing/`: `landing/clickstream/ingest_date=YYYY-MM-DD/slot=NN/part.json.gz`, `NN` de `00` a `95`. Un evento por línea con al menos `event_id`, `event_type`, `event_ts`, `customer_id`, `session_id`, `campaign_id`, `booking_id` (solo en `purchase`), `currency`, `amount`, `email` (solo CRM-like, formato de Comunes), `consent_ts`.
- Tabla local `bookings` (`docker/postgres/init/001_bookings.sql`): `booking_id` PK, `customer_id`, `session_id`, `campaign_id`, `status`, `currency`, `amount`, `created_at`, `updated_at` (lo pone el generador, Ruling línea Tiempo lógico).
- Restricciones: `run_date` ISO; `slot` entero 0-95; backfill con `from <= to <= D-1`. Payload de backfill: `{"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}`.

### 3. Integration Points
- Scheduler → (rol `skyroute-<env>-scheduler-invoke`) → Lambda con `Input` `{"scheduled_time": "<aws.scheduler.scheduled-time>"}` (research H1.12) → `PutObject` en `landing/` (rol `skyroute-<env>-generator-exec`).
- Owner → `aws lambda invoke` con `{from, to}` → misma Lambda (Ruling, línea Backfill; sin credenciales nuevas).
- Generador local → Postgres `127.0.0.1:5433`. Postgres no es alcanzable desde Lambda; la extracción queda aplazada.
- Consumidor futuro: Bronze (Fase 3) lee `landing/`; fuera de alcance.
- Alarma CloudWatch `Invocations` → SNS `skyroute-<env>-alarms` → email (`PendingConfirmation` hasta que el owner confirme).

### 4. Files Changed

Estos son los únicos archivos que toca el cambio. Todos trazan a la Propuesta 1 (Key Changes) o al Ruling citado. Las líneas de los archivos existentes se leyeron el 2026-11-13.

**Generador (Fase 1-2; P1 Key Changes `generators/`, `docker/`, `Makefile`)**
- `generators/ota/__init__.py` (NEW: paquete vacío).
- `generators/ota/keys.py` (NEW: semilla SHA-256 e ids estables; A9, Convention "Idempotency").
- `generators/ota/model.py` (NEW: catálogos y reglas de coherencia; C1).
- `generators/ota/clickstream.py` (NEW: `generate(run_date, slot)`; C1, C4).
- `generators/ota/seed_postgres.py` (NEW: filas de `bookings` coherentes y carga local; C3; Ruling línea Reservas).
- `generators/lambda_handler.py` (NEW: ramas schedule y backfill; Ruling líneas Backfill y Tiempo lógico).
- `generators/tests/test_determinism.py` (NEW: proposal Validation 1 y 19).
- `generators/tests/test_keys.py` (NEW: Validation 2 y regex de email de la 19).
- `generators/tests/test_handler.py` (NEW: Validation 3 y 4; S3 sustituido por un writer inyectado, sin boto3 real).
- `generators/tests/test_package.py` (NEW: importa `lambda_handler` como lo hará Lambda, con solo el directorio `generators/` en `PYTHONPATH` y un directorio de trabajo distinto; A12, TS-U9).
- `generators/verify_landing.py` (NEW: comparación del listado de `landing/clickstream/` con las claves esperadas de `D-182` a `D-1`; A5).
- `generators/tests/test_verify_landing.py` (NEW: el script detecta una clave que falta, una que sobra y un día con menos de 96 slots; TS-U10).
- `docker/postgres/compose.yml` (NEW: `postgres:18.7`, `127.0.0.1:5433:5432`, volumen en `/var/lib/postgresql`, `env_file` con `path: ../../.env` y `required: false`; A7).
- `docker/postgres/init/001_bookings.sql` (NEW: DDL de `bookings`).
- `.env.example` (NEW: `POSTGRES_PASSWORD=change-me`, solo placeholder).
- `.gitignore` (line 52: añadir debajo `!.env.example`; `.env.*` ignora hoy `.env.example` y no se podría versionar. No figura en P1 Key Changes: consecuencia directa de `.env.example`).
- `Makefile` (NEW: `test-generators`; objetivo `env` que copia `.env.example` a `.env` solo si no existe; `seed-postgres` depende de `env`).

**Workflows (Fases 3 y 7)**
- `.github/workflows/terraform-plan.yml` (line 63: añadir `-lock=false` al `terraform plan` y quitar `-lock-timeout=60s`, que deja de aplicar; D1. Paso "Terraform plan" `:59-66`: añadir un bloque `env:` con `TF_VAR_alarm_email` desde variable de repositorio; Decision 8. Lines 29-31 son `defaults.run.working-directory` y no se tocan). La parte de `TF_VAR_alarm_email` entra en la Fase 9, cuando el módulo declara la variable.
- `.github/workflows/terraform-apply.yml` (line 41 y line 77: renombrar los pasos "Configure AWS credentials (ci-apply)" a "(ci-apply-dev)" y "(ci-apply-prod)" (A11); line 44: `apply-dev` asume `role/ci-apply-dev`; line 80: `apply-prod` asume `role/ci-apply-prod`; P1 Key Changes. Pasos de apply `:50-51` y `:86-87`: `TF_VAR_alarm_email`, en la Fase 9).

**Bootstrap, primer re-apply (Fase 4; P1 Key Changes `bootstrap/`; D1, D2; Ruling línea Prod)**
- `infra/terraform/bootstrap/ci_roles.tf`:
  - lines 3-8: añadir `ci_apply_dev_role_arn`, `ci_apply_prod_role_arn`, `workload_boundary_dev_arn`, `workload_boundary_prod_arn`, ARN del bucket de datos por entorno; `ci_apply_role_arn` (`:6`) se conserva hasta la Fase 8.
  - lines 12-100 (`ci-boundary`): `AllowStateObjects` sin cambio; nuevo Allow con los ARN por servicio de Comunes para `dev` y `prod`, más la lectura de metadatos de `ci-plan` (lista abajo); nuevos Deny de `lambda:CreateFunctionUrlConfig`, `lambda:UpdateFunctionUrlConfig` y `lambda:AddPermission` (S4) y de `iam:AttachRolePolicy` (S2); la boundary sigue el desenlace de OQ6; `DenyCiAndOidcChanges` (`:45-54`) lista `ci-plan`, `ci-apply`, `ci-apply-dev`, `ci-apply-prod` y OIDC; `DenyCreateRoleWithoutBoundary` (`:55-65`) reemplazado por los Deny (a)-(c) de Comunes; `DenyBoundaryPolicyChanges` (`:72-82`) añade las dos workload boundaries; Deny de todo S3 sobre el bucket de state se conserva (`:83-97` más el Deny de Comunes).
  - lines 129-224 (inline `ci-plan`): quitar Sid `StateLock` (`:151-159`, D1); añadir fila de metadatos y sus Deny; mismas sustituciones de Deny que en la boundary (`DenyCiAndOidcChanges` `:169-178`, `DenyCreateRoleWithoutBoundary` `:179-189`, `DenyBoundaryPolicyChanges` `:196-206`).
  - **Fila de metadatos de `ci-plan`, S3 (A2).** Para el refresh de `aws_s3_bucket` sobre `arn:aws:s3:::skyroute-<env>-data-*`, acciones explícitas y sin comodines: `s3:GetBucketAcl`, `s3:GetBucketCors`, `s3:GetBucketWebsite`, `s3:GetBucketLogging`, `s3:GetBucketVersioning`, `s3:GetBucketTagging`, `s3:GetBucketRequestPayment`, `s3:GetAccelerateConfiguration`, `s3:GetBucketObjectLockConfiguration`, `s3:GetReplicationConfiguration`, más las que ya trae la fila de proposal § Comunes (`GetBucketPolicy`, `GetBucketLocation`, `ListBucket` y las `Get*Configuration` de los recursos `aws_s3_bucket_*`). Lo que falte lo cierra PC3.
  - **`lambda:GetFunction` en `ci-plan`:** no se decide aquí (OQ10). El borrador de bootstrap sigue la fila de Comunes (excluida) hasta que el owner resuelva.
  - lines 228-351 (`ci-apply`): sin cambio de permisos en esta fase (no recibe nada nuevo; Decision 7).
- `infra/terraform/bootstrap/ci_apply_dev.tf` (NEW: `aws_iam_role.ci_apply_dev` con `permissions_boundary = ci-boundary`, trust `StringEquals` `aud` y un solo `sub` `repo:javiladino@97758532/skyroute@1455233709:environment:dev` (formato de `ci_roles.tf:246`); inline con state y lock solo de `envs/dev/`, `s3:ListBucket` con `s3:prefix = envs/dev/`, Allow por ARN de servicio `skyroute-dev-*`, Deny (a)-(c) de Comunes con `workload-boundary-dev`, Deny de adjuntar `workload-boundary-prod` (D2) y el resto de Deny comunes).
  - **Allow de IAM (S2), sin `iam:*`**, solo sobre `arn:aws:iam::<account_id>:role/workload/skyroute-dev-*`: `iam:CreateRole`, `iam:DeleteRole`, `iam:GetRole`, `iam:UpdateRole`, `iam:UpdateAssumeRolePolicy`, `iam:TagRole`, `iam:UntagRole`, `iam:ListRoleTags`, `iam:PutRolePolicy`, `iam:GetRolePolicy`, `iam:DeleteRolePolicy`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:ListInstanceProfilesForRole` e `iam:PassRole` (este con `iam:PassedToService` en `lambda.amazonaws.com` y `scheduler.amazonaws.com`). Sin `iam:AttachRolePolicy`, `iam:CreatePolicy` ni `iam:PutRolePermissionsBoundary`. La lista exacta se confirma con PC3.
  - **Deny de `iam:AttachRolePolicy` (S2)** sobre cualquier rol, sin lista de PolicyARN permitidos: el módulo usa solo políticas inline (nota S11 en `iam.tf`), así que la lista cerrada es vacía. Si el módulo necesitara una política gestionada, se añade su ARN a una lista cerrada en bootstrap, no se quita el Deny.
  - **Deny de `lambda:CreateFunctionUrlConfig`, `lambda:UpdateFunctionUrlConfig` y `lambda:AddPermission` (S4):** la función no tiene URL pública ni política de recursos; el módulo no declara `aws_lambda_function_url` ni `aws_lambda_permission` (el Scheduler invoca con el rol `scheduler-invoke`, no con permiso de recurso).
- `infra/terraform/bootstrap/ci_apply_prod.tf` (NEW: espejo de `ci_apply_dev.tf` con `environment:prod` (`ci_roles.tf:247`), `envs/prod/` y `workload-boundary-prod`; mismos Allow de IAM y mismos Deny de S2 y S4).
- Si el owner acepta en OQ11 la opción por defecto: `infra/terraform/bootstrap/account_public_access_block.tf` (NEW: `aws_s3_account_public_access_block` con los cuatro bloqueos en `true`; S9). Con la alternativa, no se crea ese archivo y se añade a `ci-apply-<env>` un Deny de `s3:PutBucketPublicAccessBlock` sobre el bucket de datos, que solo puede ponerse tras crear el bucket (otro re-apply).
- Si el owner elige en OQ6 la alternativa `ci-boundary-<env>`: se añaden `infra/terraform/bootstrap/ci_boundary_dev.tf` y `ci_boundary_prod.tf` (NEW), `ci_apply_<env>` usa su boundary, y `ci-boundary` queda para `ci-plan`. Los Deny pasan a seis copias más las dos workload boundaries. Sin esa decisión no se escribe la PR-B1.
- `infra/terraform/bootstrap/workload_boundary_dev.tf` (NEW: `aws_iam_policy` `workload-boundary-dev`, contenido de P1 Key Changes).
- `infra/terraform/bootstrap/workload_boundary_prod.tf` (NEW: `workload-boundary-prod`).
- `docs/runbooks/foundations-bootstrap.md` (after line 68, antes de "Antes de cerrar la cuenta Free" `:70`: nueva sección "Re-apply de bootstrap" con el orden de transición, la ventana (solo en la vuelta atrás), qué no mergear y la vuelta atrás, que reabre T17; nota de S-H18 sobre el environment `prod`; Ruling línea Bootstrap).

**Bootstrap, segundo re-apply (Fase 8; A4)**
- `infra/terraform/bootstrap/ci_roles.tf` (lines 226-351: borrar `aws_iam_role.ci_apply` y `aws_iam_role_policy.ci_apply`; line 6: borrar `ci_apply_role_arn` y sus usos en los `DenyCiAndOidcChanges`; lines 10-14: el comentario de `ci-boundary` pasa a nombrar los tres roles; la `description` **no se cambia**: cambiar la `description` de una `aws_iam_policy` fuerza replacement (inmutable en IAM) y el owner paró el primer plan de la Fase 8 por eso. Se conserva el texto original ("ci-plan, ci-apply"; Ruling Implement decisions, PR #13)).

**Bootstrap, cuota de Lambda (trabajo paralelo, owner; PC6)**
- `infra/terraform/bootstrap/lambda_quota.tf` (NEW: `aws_servicequotas_service_quota` de `lambda`, cuota `L-B99A9384` en `eu-west-3`, valor 1000; Ruling Implement decisions, "Concurrencia (PC6)"). Lo aplica el owner en un re-apply de `bootstrap/` sin destroy (Convention "Apply gate"); AWS decide la aprobación, que puede tardar.
- `docs/runbooks/foundations-bootstrap.md` (sección "Re-apply de bootstrap": subsección de la solicitud de cuota: qué crea, que el re-apply no destruye nada, cómo leer el estado de la solicitud y que la PR-Q espera a la aprobación).

**Módulo y entornos (Fase 9; P1 Key Changes `modules/`, `envs/`)**
- `infra/terraform/modules/generator-landing/variables.tf` (NEW: `env`, `schedule_enabled`, `alarm_email` sin default y con `sensitive = true` (S3), `architecture`, `backfill_timeout`, `alarm_threshold`).
- `infra/terraform/modules/generator-landing/bucket.tf` (NEW: bucket `skyroute-<env>-data-<account_id>`, SSE-S3, public access block, `BucketOwnerEnforced`, `DenyInsecureTransport`, lifecycle `Expiration` 30 días en `landing/` y `abort_incomplete_multipart`, sin versioning; skips por recurso con motivo según proposal § Skips; patrón `state_bucket.tf:5-8`).
- `infra/terraform/modules/generator-landing/lambda.tf` (NEW: `archive_file` con `source_dir`, `excludes` y `output_path` de Technical Design § Core Components (A12), log group `/aws/lambda/skyroute-<env>-generator` con 14 días declarado antes de la función, función arm64 `python3.13`, `timeout = var.backfill_timeout`, `memory_size = 256`, **sin `reserved_concurrent_executions`** hasta que la cuota de la cuenta sea ≥ 11 (PC6, Ruling Implement decisions; la PR-Q lo restaura a 1), `aws_lambda_function_event_invoke_config` con 0 reintentos y 900 s de edad máxima; sin `aws_lambda_function_url` ni `aws_lambda_permission`, S4).
- `infra/terraform/modules/generator-landing/scheduler.tf` (NEW: `aws_scheduler_schedule` `rate(15 minutes)`, `state = var.schedule_enabled ? "ENABLED" : "DISABLED"`, `Input` con `<aws.scheduler.scheduled-time>`, `retry_policy` 2/900, la única `retry_policy` del módulo).
- `infra/terraform/modules/generator-landing/iam.tf` (NEW: roles `/workload/skyroute-<env>-generator-exec` y `/workload/skyroute-<env>-scheduler-invoke` con `workload-boundary-<env>`, trusts y políticas de Comunes. **Solo `aws_iam_role_policy` (inline):** `aws_iam_policy` queda fuera porque `iam:CreatePolicy` está denegado por (b) (S11). Trust del rol de scheduler con `aws:SourceAccount` y `aws:SourceArn` = `arn:aws:scheduler:eu-west-3:<account_id>:schedule-group/default` (opción por defecto de PC5; S5; fuente: `https://docs.aws.amazon.com/scheduler/latest/UserGuide/cross-service-confused-deputy-prevention.html`). La proposal (§ Comunes, línea del trust de scheduler) pone `aws:SourceArn` en el ARN del schedule `schedule/default/...`; la guía (leída el 2026-11-13) dice que el ARN debe ser el de un grupo, no el de un schedule ni un prefijo, así que este plan sigue la guía y se prueba en el primer apply a dev).
- `infra/terraform/modules/generator-landing/alarm.tf` (NEW: topic `skyroute-<env>-alarms`, política del topic, suscripción email, alarma `skyroute-<env>-generator-invocations`).
- `infra/terraform/modules/generator-landing/outputs.tf` (NEW: `bucket_name`, `function_name`, `topic_arn`).
- `infra/terraform/modules/generator-landing/versions.tf` (NEW: `required_providers` `aws ~> 6.73` y `archive`; necesario para tflint).
- `infra/terraform/envs/dev/main.tf` (NEW: `module "generator_landing"` con `env = "dev"`, `schedule_enabled = false`, `alarm_email = var.alarm_email`).
- `infra/terraform/envs/dev/variables.tf` (NEW: `alarm_email`, sin default y con `sensitive = true`; S3).
- `infra/terraform/envs/prod/main.tf` (NEW: igual con `env = "prod"`, `schedule_enabled = true`).
- `infra/terraform/envs/prod/variables.tf` (NEW: `alarm_email`, sin default y con `sensitive = true`; S3).
- `infra/terraform/envs/dev/backend.tf` y `envs/prod/backend.tf` (lines 4-9: añadir el provider `hashicorp/archive` a `required_providers`); `.terraform.lock.hcl` de cada entorno se regenera con `terraform init` (executor, sin backend).

La proposal lista `envs/<env>/main.tf` como "Modified"; hoy no existen y se crean (research § Lo que existe hoy). `versions.tf` del módulo, `variables.tf` de los entornos y el bloque `archive` no figuran en P1 Key Changes: son consecuencia directa de `archive_file` y de `alarm_email` y no añaden alcance.

**Cobertura de lint (A13).** No hay tflint para `bootstrap/` ni para `modules/`: el job `static-checks` solo recorre `envs/dev` y `envs/prod` (`terraform-plan.yml:142`), y el módulo se lintea solo en la medida en que lo llaman los entornos. `bootstrap/` tiene `terraform validate`, `terraform fmt` y checkov (`checkov -d infra/terraform`, `:131`), pero no tflint. Este plan no añade un tflint de `bootstrap/` (sería otro cambio de workflow).

## Implementation Plan

Cada fase cita su origen y su verify command (un comando simple, Convention "Simple shell commands"). Las fases de owner existen porque la Convention "Apply gate" impide a los agentes `terraform plan`/`apply` y comandos AWS; su salida la aporta el owner y el orquestador la copia en `working/test.md` (Convention "Verification ownership"). Cada fase de código va en su propia rama y PR (Convention "Git workflow").

| # | Fase | Ejecutor | Depende de | PR |
|---|------|----------|------------|----|
| 1 | Generador y tests | executor | — | PR-G |
| 2 | Postgres local | executor | 1 | PR-G |
| 3 | `-lock=false` en `terraform-plan.yml` | executor; merge del owner | — | PR-L |
| 4 | Código de bootstrap, primer estado | executor | 3 mergeada; **OQ6, OQ10 y OQ11 resueltas por el owner** | PR-B1 |
| 5 | Primer re-apply de `bootstrap/` | **owner** | 4 | — |
| 6 | Transición de `ci-apply`: workflow de apply | executor; merge y evidencia del **owner** | 5 | PR-W |
| 7 | Código de bootstrap, retirada de `ci-apply` | executor | 6 verificada | PR-B2 |
| 8 | Transición de `ci-apply`: segundo re-apply (destroy) | **owner** | 7 | — |
| 9 | Módulo `generator-landing` y entornos | executor; merge y aprobación de prod del **owner** | 8 aplicada (decisión del owner: la PR-M espera a la Fase 8); PC6 resuelta (valor 10, 2026-11-14; Ruling Implement decisions) | PR-M |
| 10 | Backfill, schedule y alarma | **owner** | 9 aplicada; OQ9 resuelta | PR-T1, PR-T2 |
| 11 | PR-Q: restaurar `reserved_concurrent_executions = 1` | executor; merge del **owner** | 9 aplicada; el owner aporta la cuota aprobada (≥ 11) tras el re-apply paralelo de `lambda_quota.tf`; no bloquea la Fase 10 | PR-Q |

1. **Fase 1: Generador y tests** (P1 Key Changes `generators/`; Convention "Idempotency"; A9).
   - Escribir `generators/ota/*`, `generators/lambda_handler.py`, `generators/verify_landing.py` y los cinco tests de Files Changed (`test_determinism`, `test_keys`, `test_handler`, `test_package`, `test_verify_landing`); `Makefile` con `test-generators`.
   - Medir en el test del handler el tiempo de 96 slots en local, como indicio para OQ2 (no sustituye a V12, que se mide en Lambda).
   - Verify: `pytest generators/tests -q` (todo verde).

2. **Fase 2: Postgres local** (P1 Key Changes `docker/`; Ruling línea Reservas).
   - `docker/postgres/compose.yml`, `init/001_bookings.sql`, `.env.example`, excepción `!.env.example` en `.gitignore`, objetivos `env` y `seed-postgres` del `Makefile`.
   - Verify: `docker compose -f docker/postgres/compose.yml config` (resuelve sin error aunque no exista `.env`, por `required: false`, y publica solo `127.0.0.1:5433`; A7). La prueba con datos (TS-C3) la corre executor en Fase de test: es Docker local, no AWS. La proposal (Validation 18) la marca como "Owner"; si el owner prefiere correrla él, se respeta.

3. **Fase 3: `-lock=false` en `terraform-plan.yml`** (D1; Decision 6).
   - Cambiar `terraform-plan.yml:63`. Va antes de la Fase 4: con el permiso del lock aún presente, el cambio es inocuo; al revés, todo plan de PR fallaría.
   - Verify: `grep -n "terraform plan -input=false -no-color -lock=false" .github/workflows/terraform-plan.yml` (una coincidencia).
   - Evidencia de CI: el comentario de plan de la PR-L sale `OK` en dev y prod.

4. **Fase 4: Código de bootstrap, primer estado** (P1 Key Changes `bootstrap/`; D1; D2; proposal § Comunes "Deny reemplazados", "Fila de `ci-plan`"; runbook por Ruling línea Bootstrap).
   - **Gate del owner antes de abrir la PR-B1:** OQ6 (qué boundary lleva `ci-apply-<env>`), OQ10 (`lambda:GetFunction` para `ci-plan`) y OQ11 (bloqueo público a nivel de cuenta). No se implementa la opción por defecto de ninguna sin decisión.
   - Editar `ci_roles.tf` según Files Changed (sin tocar `ci-apply`); crear `ci_apply_dev.tf`, `ci_apply_prod.tf`, `workload_boundary_dev.tf`, `workload_boundary_prod.tf`.
   - Escribir la sección "Re-apply de bootstrap" del runbook con las Fases 5, 6 y 8 (orden, ventana, vuelta atrás). El runbook dice de forma explícita que la vuelta atrás de la Fase 8 recrea `ci-apply` y **reabre T17** (S8, A10).
   - Verify: `terraform -chdir=infra/terraform/bootstrap validate` (antes, `terraform -chdir=infra/terraform/bootstrap init -backend=false`, que no toca AWS ni el state). Además `terraform fmt -check -recursive infra/terraform`.
   - La PR-B1 dispara `terraform-plan.yml`, que solo planifica `envs/*` (sin cambios); checkov revisa `bootstrap/` en `static-checks`.

5. **Fase 5: Primer re-apply de `bootstrap/`, OWNER** (Ruling "Research decisions", línea Bootstrap; Convention "Apply gate"; Convention "Bootstrap identity").
   - Con la PR-B1 mergeada en `main` y desde `main` actualizado: `aws login` con `skyroute-dev`; en `infra/terraform/bootstrap/`, `terraform init` (backend remoto `bootstrap/terraform.tfstate`, `backend.tf`), `terraform plan -out=b1.tfplan`, revisión, `terraform apply b1.tfplan`.
   - El plan debe mostrar solo `create` de `ci-apply-dev`, `ci-apply-prod`, sus inline, `workload-boundary-dev`, `workload-boundary-prod`, y `update in-place` de `ci-boundary` y la inline de `ci-plan`; **ningún** `destroy`. Si aparece un `destroy`, el owner no aplica.
   - Evidencia: salida de `terraform plan` (sin `budget_email`; si aparece, el owner la recorta) que el orquestador copia en `working/test.md` § TS-B1; salidas de `simulate-principal-policy` de TS-B2, TS-B3, TS-B5 y TS-B6.
   - Verify (owner): `terraform -chdir=infra/terraform/bootstrap plan -detailed-exitcode` tras el apply sale con código 0 (sin cambios pendientes).

6. **Fase 6: Transición de `ci-apply`, cambio de workflow** (proposal § Comunes "Orden de transición" paso (3); A4; Decision 7).
   - Executor: `terraform-apply.yml:44` → `role/ci-apply-dev` y `:80` → `role/ci-apply-prod`; los nombres de paso de `:41` y `:77` pasan a "Configure AWS credentials (ci-apply-dev)" y "(ci-apply-prod)" (A11).
   - Owner: mergea la PR-W. El push a `main` lanza `terraform-apply.yml`: `apply-dev` con `ci-apply-dev` y `apply-prod` (con aprobación) con `ci-apply-prod`; `envs/*` siguen vacíos, así que el apply es "No changes" y prueba la asunción de rol y el acceso al state.
   - Evidencia: URL del run de apply en verde en los dos jobs.
   - Verify (executor, antes del merge): `grep -c "role/ci-apply-" .github/workflows/terraform-apply.yml` da `2`, `grep -c "role/ci-apply$" .github/workflows/terraform-apply.yml` da `0` y `grep -c "credentials (ci-apply)" .github/workflows/terraform-apply.yml` da `0`.

7. **Fase 7: Código de bootstrap, retirada de `ci-apply`** (proposal § Comunes "Orden de transición" paso (4); A4; Ruling línea Prod).
   - Solo después de la evidencia de la Fase 6. Borrar `ci_roles.tf:226-351` y `ci_apply_role_arn` (`:6`) con sus usos; actualizar comentario y `description` (`:10-14`).
   - Verify: `terraform -chdir=infra/terraform/bootstrap validate`.

8. **Fase 8: Transición de `ci-apply`, segundo re-apply, OWNER** (A4; Ruling línea Prod; Convention "Apply gate").
   - Con la PR-B2 mergeada: `terraform plan -out=b2.tfplan` en `bootstrap/`. Debe mostrar `destroy` de `aws_iam_role.ci_apply` y `aws_iam_role_policy.ci_apply` y `update in-place` de las políticas que pierden el ARN de `ci-apply` en `DenyCiAndOidcChanges`; ningún `create` ni `destroy` de `ci-apply-dev`/`-prod`. Luego `terraform apply b2.tfplan`.
   - Evidencia: plan (TS-B7) y `aws iam get-role --role-name ci-apply` con `NoSuchEntity`.
   - Verify (owner): `terraform -chdir=infra/terraform/bootstrap plan -detailed-exitcode` sale con código 0.
   - Ventana, qué no mergear y vuelta atrás: Rollout Strategy.
   - Nota: el primer plan (intento 1) se paró porque la PR-B2 cambió la `description` de `ci-boundary`, y cambiar la `description` de una `aws_iam_policy` fuerza replacement (inmutable en IAM). Se conservó el texto original (PR #13; Ruling Implement decisions). El plan aplicado fue 0 add / 4 change / 2 destroy (evidencia en `working/test.md`).

9. **Fase 9: Módulo `generator-landing` y entornos** (P1 Key Changes `modules/`, `envs/`; Ruling líneas Bucket, Schedule; proposal § Skips de checkov).
   - Solo tras la Fase 8: el Ruling (línea Prod) exige T17 cerrada antes de ampliar permisos, y los permisos de la Fase 5 solo se usan aquí.
   - Owner, antes del merge: crear la variable de repositorio `ALARM_EMAIL` (OQ5) y tener resuelta la cuota de concurrencia de Lambda (PC6). Resuelta el 2026-11-14: valor 10 (`aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region eu-west-3`; `"Value": 10.0`, `Adjustable: true`), y AWS exige dejar 10 sin reservar. Ruling Implement decisions (owner javiladino, 2026-11-14), opción C: la Fase 9 se despliega **sin `reserved_concurrent_executions`**; `bootstrap/` pide la subida a 1.000 (`lambda_quota.tf`, trabajo paralelo del owner) y la PR-Q (Fase 11) restaura la concurrencia reservada de 1. Executor: añadir `TF_VAR_alarm_email` a los dos workflows.
   - Escribir el módulo y `envs/{dev,prod}`; regenerar `.terraform.lock.hcl` con `terraform -chdir=infra/terraform/envs/dev init -backend=false` (y prod).
   - Verify: `terraform -chdir=infra/terraform/envs/dev validate`; además `terraform -chdir=infra/terraform/envs/prod validate`, `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl` y el de prod, `terraform fmt -check -recursive infra/terraform`.
   - CI: comentario de plan de la PR-M en dev y prod sin `AccessDenied` (V4) y `static-checks` en verde (V10). Si checkov dispara reglas no previstas, executor añade skips por recurso con motivo y el orquestador lo comunica; un skip de CKV_AWS_273/274 fuera de `owner_user.tf` no se acepta (Convention "Bootstrap identity").
   - Owner: mergea; `apply-dev` crea los recursos con schedule DISABLED (primer apply a dev: prueba de Region y de arm64, PC1); aprueba `apply-prod`. En el primer apply a dev se comprueba el trust del Scheduler con `aws:SourceAccount` y `aws:SourceArn` del schedule group (PC5, S5). El plan de la PR-M **no** prueba el refresh de `ci-plan` (el state está vacío en ese plan): PC3, TS-A3 y OQ10 se comprueban en la primera PR posterior a este apply (PR-T1, Fase 10). Si `apply-dev` falla por AccessDenied, se corrige en bootstrap (vuelta a Fase 4/5 con un re-apply más), no con permisos a mano (Convention "IaC only").

10. **Fase 10: Backfill, schedule y alarma, OWNER** (criterio de hecho; Ruling líneas Histórico, Backfill, Schedule).
   - Confirmar la suscripción SNS (TS-O4).
   - Registrar D (OQ9): el owner anota la fecha del primer slot del schedule de prod (opción por defecto) en `working/test.md`; a partir de ahí D es fija.
   - **PR-T1** (primera PR posterior al apply de la Fase 9): sube `backfill_timeout` de prod a 300 s (OQ2, C1). Su plan es el primer plan de PR con recursos en el state: ahí se comprueban TS-A3, PC3 y OQ10. Si el plan falla con `AccessDenied`, no se mergea y se corrige en bootstrap con otro re-apply del owner.
   - Backfill en prod (un entorno por mes, proposal § Comunes): invocar un tramo por día de `D-182` a `D-1` (182 invocaciones, OQ2), esperar a que termine cada una antes de la siguiente y evitar las horas cercanas al umbral de la alarma (OQ3). Comando exacto de cada tramo (proposal.md:68; `<día>` es la fecha ISO del tramo):
     `aws lambda invoke --function-name skyroute-prod-generator --region eu-west-3 --cli-read-timeout 0 --cli-connect-timeout 0 --invocation-type RequestResponse --cli-binary-format raw-in-base64-out --payload '{"from":"<día>","to":"<día>"}' <archivo-de-respuesta>.json`
     `--cli-binary-format raw-in-base64-out` no figura en proposal.md:68: AWS CLI v2 lo exige para pasar el payload como JSON literal (sin verificar contra la versión instalada del owner).
   - **PR-T2:** en cuanto termine el backfill, devuelve `backfill_timeout` de prod a 60 s. Mientras no se mergee, el techo de riesgo con el schedule de prod `ENABLED` es el de OQ2 (ver Known Limitations).
   - Tomar la evidencia de TS-O1 dentro de los 30 días siguientes (T1) y la de TS-O2 tras 30 min.
   - Verify (owner): guardar el listado con `aws s3api list-objects-v2 --bucket skyroute-prod-data-<id> --prefix landing/clickstream/ --region eu-west-3 --output json` en un archivo y comprobarlo con `python3 generators/verify_landing.py` con D fijada: 96 objetos por cada `ingest_date` de `D-182` a `D-1` (182 × 96 = 17.472), ninguna clave que falte ni sobre dentro del rango. Un total de `--summarize` no vale: mezclaría los objetos del schedule de D en adelante.

**Trabajo paralelo: solicitud de cuota de Lambda (owner; PC6; Ruling Implement decisions).** No es una fase numerada ni bloquea las Fases 9 y 10.
   - Executor: `infra/terraform/bootstrap/lambda_quota.tf` (`aws_servicequotas_service_quota` a 1000) y la sección del runbook, en una PR de `bootstrap/` (verify: `terraform -chdir=infra/terraform/bootstrap validate`).
   - Owner: tras mergear, re-apply de `bootstrap/` (`plan -out`, revisión, `apply`; solo `add`, sin destroy). Cuando AWS apruebe, el owner aporta la cuota aprobada (comando de PC6).

11. **Fase 11: PR-Q, restaurar `reserved_concurrent_executions = 1`** (PC6; Ruling Implement decisions).
   - Depende de la Fase 9 aplicada y de que el owner aporte la cuota aprobada (≥ 11). Mientras no llegue, la función sigue sin concurrencia reservada.
   - Executor: en `modules/generator-landing/lambda.tf`, añadir `reserved_concurrent_executions = 1` a la función. Sin otro cambio.
   - Verify: `terraform -chdir=infra/terraform/envs/dev validate`; el plan de la PR muestra un `update in-place` de la función en dev y prod; el merge y la aprobación de `apply-prod` son del owner.
   - Evidencia (TS-C2c): `aws lambda get-function-concurrency --function-name skyroute-prod-generator --region eu-west-3` da `ReservedConcurrentExecutions = 1`.

## Testing Strategy

Contrato de `reppit-test`. "Ejecuta" dice quién aporta la salida: executor (y el orquestador la reejecuta, Convention "Verification ownership"), CI o owner (Convention "Apply gate"). Base de comparación: `main` en `b21c2f9`.

### Verify command del proyecto y reglas de archivos

| ID | Check | Ejecuta | Esperado |
|----|-------|---------|----------|
| TS-V1 | `pytest generators/tests -q` | executor | todo verde, 0 skips |
| TS-V2 | `terraform fmt -check -recursive infra/terraform` | executor | código 0 |
| TS-V3 | `terraform -chdir=infra/terraform/envs/dev validate` (y prod, y `bootstrap`; antes `init -backend=false`) | executor | `Success!` en los tres |
| TS-V4 | `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl` (y prod; antes `tflint --init`, nunca `--recursive`) | executor | sin hallazgos. No existe check equivalente para `bootstrap/` ni `modules/` (A13): solo `validate`, `fmt` y checkov |
| TS-V5 | `git diff --stat b21c2f9 -- docs/design/foundations` | executor | vacío: el Ruling Foundations design no se toca en este ciclo |
| TS-V6 | `git diff --name-only b21c2f9` | executor | solo rutas de Files Changed más `docs/design/generator-landing/` |

### Behavior checks de AGENTS.md

| ID | Check | Ejecuta | Esperado |
|----|-------|---------|----------|
| TS-A1 | job `static-checks` de `terraform-plan.yml` (checkov 3.4.5 + tflint) en PR-B1 y PR-M | CI | verde; cada skip con `#checkov:skip=<ID>:<motivo>` en su recurso (V10) |
| TS-A2 | comentario de plan de PR-L, PR-M | CI | `OK` en dev y prod, sin `AccessDenied` (V4). El plan de PR-M no refresca nada (state vacío): no prueba los permisos de refresh |
| TS-A3 | comentario de plan de la **primera PR posterior al apply de la Fase 9** (PR-T1), con la función y el bucket ya en el state | CI | `OK` en dev y prod: el refresh de `aws_lambda_function` (`GetFunction`, A1) y de `aws_s3_bucket` (A2) no da `AccessDenied`. Un `AccessDenied` bloquea el merge de PR-T1 hasta resolver OQ10 o PC3 |

### Unit Tests (`generators/tests/`)

| ID | Caso | Criterio |
|----|------|----------|
| TS-U1 | `generate("2026-05-01", 17)` dos veces da los mismos bytes | Idempotency (Validation 1) |
| TS-U2 | mismo resultado lanzando el generador en subprocesos con `PYTHONHASHSEED=0` y `=1` | A9 (Validation 19) |
| TS-U3 | todo `booking_id` de un `purchase` de un día existe en `rows_for_day` de ese día | C1, C3 (Validation 2) |
| TS-U4 | todo email cumple `^u[0-9a-f]{12}@example\.com$`; no hay campos de nombre, teléfono ni dirección | PII (Validation 19) |
| TS-U5 | `slot_from_scheduled_time("2026-11-13T10:14:59Z") == ("2026-11-13", 40)` y `10:15:00Z` da 41 | Ruling línea Tiempo lógico (Validation 3) |
| TS-U6 | backfill `{from: D-182, to: D-1}` con writer en memoria: 182 × 96 = 17.472 claves distintas, ninguna con `run_date >= D` | C5; Ruling (Validation 4) |
| TS-U7 | backfill con `to >= hoy` (reloj inyectado, no el real) falla sin escribir nada | Ruling: backfill termina en D-1; FR3 (única lectura de reloj) |
| TS-U8 | reinvocar el mismo slot escribe la misma clave y los mismos bytes | at-least-once, Idempotency |
| TS-U9 | con solo `generators/` en `PYTHONPATH` y otro directorio de trabajo, `import lambda_handler` funciona y `lambda_handler.handler` es invocable; tras el import no están en `sys.modules` `seed_postgres`, `pytest` ni `verify_landing` | A12: el handler se importa como lo hará Lambda; los excluidos del zip no son necesarios |
| TS-U10 | `verify_landing` con un listado de 182 × 96 claves da 0 faltantes y 0 sobrantes; con una clave menos o una de más, las nombra; ignora las claves con `ingest_date >= D` | A5 (TS-O1) |

Sin mocks de AWS: el handler recibe el writer por inyección; boto3 solo se usa en el writer real.

### Integration Tests y evidencia por criterio de éxito

| ID | Criterio | Check | Ejecuta | Esperado |
|----|----------|-------|---------|----------|
| TS-C3 | C3 | `docker compose -f docker/postgres/compose.yml up -d` (tras `make env`), `make seed-postgres`, `docker compose -f docker/postgres/compose.yml exec postgres psql -U postgres -c "select count(*) from bookings"` (llamadas separadas; sin `psql` en el host, A7) | executor (u owner) | conteo > 0 |
| TS-B1 | Ruling línea Bootstrap | plan de Fase 5 | owner | solo create/update de la Fase 5; 0 destroy |
| TS-B2 | T17 (Validation 8) | `aws iam get-role --role-name ci-apply-dev`; `simulate-principal-policy` de `ci-apply-dev` con `s3:GetObject` sobre `envs/prod/terraform.tfstate` | owner | un solo `sub` `...:environment:dev`; `implicitDeny` |
| TS-B3 | A3 (Validation 9) | `simulate-principal-policy` de `ci-apply-dev`, `iam:UpdateAssumeRolePolicy` sobre `ci-apply-prod` | owner | `explicitDeny` |
| TS-B4 | T22 | por cada Sid esperado de la tabla siguiente, `grep -c 'Sid *= *"<Sid>"' <archivo>` (una llamada por Sid y archivo) | executor | coincidencias iguales al número de la tabla; un Sid ausente o duplicado falla el check |
| TS-B8 | S2, S4 | `simulate-principal-policy` de `ci-apply-dev`: `iam:AttachRolePolicy` sobre `role/workload/skyroute-dev-x`; `lambda:CreateFunctionUrlConfig`, `lambda:UpdateFunctionUrlConfig` y `lambda:AddPermission` sobre `function:skyroute-dev-generator`; `iam:CreateRole` sin boundary | owner | `explicitDeny` en las cinco |
| TS-B5 | D2/A2 (Validation 10) | `simulate-principal-policy` de `ci-apply-dev` con `iam:CreateRole` y `iam:PermissionsBoundary` = `workload-boundary-prod`; luego `= workload-boundary-dev` sobre `role/workload/skyroute-dev-x`; `iam:PassRole` fuera de `role/workload/skyroute-dev-*` | owner | `explicitDeny`; `allowed`; `explicitDeny` |
| TS-B6 | D1/A6 (Validation 12) | `simulate-principal-policy` de `ci-plan`: `lambda:GetFunction`; `s3:GetObject` en `skyroute-prod-data-<id>/landing/x`; `lambda:GetFunctionConfiguration`; `s3:PutObject` del `.tflock` de dev | owner | `explicitDeny`/`implicitDeny` (si OQ10 mantiene la exclusión; con la opción por defecto de OQ10, `allowed` solo sobre `function:skyroute-*-generator`); deny; `allowed`; `implicitDeny` |
| TS-B7 | A4 (Validation 11) | plan de Fase 8 y `aws iam get-role --role-name ci-apply` | owner | destroy solo de `ci-apply` y su inline; `NoSuchEntity` |
| TS-W1 | A4, S10 | run de `terraform-apply.yml` tras PR-W | CI | `apply-dev` y `apply-prod` verdes con los roles nuevos, lo que prueba que la condición `s3:prefix = envs/<env>/` de `ListBucket` no rompe `terraform init`. Si `init` falla por esa condición, la corrección es `StringLike` con `envs/<env>/*` en bootstrap (otro re-apply); la condición no se quita |
| TS-C2 | C2 | `aws lambda get-function-configuration --function-name skyroute-prod-generator --region eu-west-3` | owner | `Architectures = [arm64]` (o `x86_64` si PC1 falla), `Timeout = 60` (fuera de la ventana de backfill; durante ella, 300), `MemorySize = 256` (A8, Validation 15) |
| TS-C2c | PC6; **condicionado a la PR-Q** (hasta entonces no aplica: la función no lleva concurrencia reservada) | `aws lambda get-function-concurrency --function-name skyroute-prod-generator --region eu-west-3` | owner | `ReservedConcurrentExecutions = 1` tras la PR-Q; antes de ella, respuesta sin `ReservedConcurrentExecutions` |
| TS-C2b | A8 | `aws scheduler get-schedule --name skyroute-prod-generator --region eu-west-3` | owner | `RetryPolicy` 2 / 900 |
| TS-C4 | C4 | `aws s3 ls s3://skyroute-dev-data-<id>/landing/` tras una invocación manual de un slot en dev | owner | aparece `clickstream/ingest_date=.../slot=.../part.json.gz` |
| TS-O1 | C5, criterio de hecho | listado `aws s3api list-objects-v2 --bucket skyroute-prod-data-<id> --prefix landing/clickstream/ --region eu-west-3 --output json` guardado a archivo y comparado con `python3 generators/verify_landing.py`, con D fija (OQ9), dentro de los 30 días del backfill | owner | 96 objetos por cada `ingest_date` de `D-182` a `D-1` (182 × 96 = 17.472), sin claves que falten ni sobren; no vale un total `--summarize` |
| TS-O2 | C6, criterio de hecho | dos `aws s3 ls` de `landing/clickstream/ingest_date=<D>/` en prod separados 30 min; lo mismo en dev; `get-schedule` en ambos | owner | al menos un `slot=` nuevo en prod, ninguno en dev; `ENABLED` en prod, `DISABLED` en dev (Validation 14) |
| TS-O3 | Ruling línea Schedule | `aws cloudwatch describe-alarms --alarm-names skyroute-prod-generator-invocations --region eu-west-3` | owner | umbral = el elegido en OQ3; acción al topic SNS |
| TS-O4 | A12 (Validation 16) | `aws sns list-subscriptions-by-topic --topic-arn <arn>` | owner | sin `PendingConfirmation` |
| TS-O5 | S-H18 (Validation 17); S1 | `gh api repos/javiladino/skyroute/environments/prod` y `gh api repos/javiladino/skyroute/environments/dev` | orquestador | `prod`: `required_reviewers` y `deployment_branch_policy` con una sola branch policy `main`; `dev`: `can_admins_bypass:false` y una sola branch policy `main`. **Verificado por executor el 2026-11-13** (`dev`: `can_admins_bypass:false`, `custom_branch_policies:true`, branch policy `main`; `prod` igual más reviewer javiladino, `prevent_self_review:false`); se repite al ejecutar `reppit-test` |
| TS-O6 | Ruling línea Schedule | `aws logs describe-log-groups --log-group-name-prefix /aws/lambda/skyroute-prod-generator --region eu-west-3` | owner | `retentionInDays = 14` |

**Tabla de TS-B4** (coincidencias esperadas por archivo tras la Fase 7; `ci_roles.tf` contiene `ci-boundary` y `ci-plan`). Los Sid de (a)-(c) mantienen el nombre del Deny que reemplazan o son nombres propuestos por este plan:

| Sid | `ci_roles.tf` | `ci_apply_dev.tf` | `ci_apply_prod.tf` |
|-----|---------------|-------------------|--------------------|
| `DenyOwnerIdentity` | 2 | 1 | 1 |
| `DenyCiAndOidcChanges` | 2 | 1 | 1 |
| `DenyCreateRoleWithoutBoundary` (a) | 2 | 1 | 1 |
| `DenyRoleWritesOutsideWorkload` (b, `NotResource`) | 2 | 1 | 1 |
| `DenyPassRoleWrongService` (c) | 2 | 1 | 1 |
| `DenyDeleteBoundary` | 2 | 1 | 1 |
| `DenyBoundaryPolicyChanges` | 2 | 1 | 1 |
| `DenyStateBucketProtectionChanges` | 2 | 1 | 1 |
| `DenyAttachRolePolicy` (S2) | 1 (solo `ci-boundary`) | 1 | 1 |
| `DenyLambdaUrlAndPermission` (S4) | 1 (solo `ci-boundary`) | 1 | 1 |
| `DenyAttachCrossEnvBoundary` (D2) | 0 | 1 | 1 |
| `DenyNonEmailSnsSubscribe` | 1 (solo `ci-boundary`) | 1 | 1 |
| `DenyLogRead` | 2 (`ci-plan` y `ci-boundary`) | 0 | 0 |

Si el executor usa otros nombres de Sid, actualiza esta tabla en el mismo cambio. Antes de la Fase 7 (con `ci-apply` aún presente) cada "2" de `ci_roles.tf` es "3", salvo `DenyRoleWritesOutsideWorkload` y `DenyPassRoleWrongService`, que valen 2 también antes de la Fase 7 porque el `ci-apply` antiguo nunca los tuvo (solo `ci-boundary` y `ci-plan`). Si OQ6 elige `ci-boundary-<env>`, la tabla pasa a seis políticas y se rehace en la PR-B1.

## Observability

### Logging
- Una línea JSON por slot escrito: `run_date`, `slot`, `key`, `events`; en backfill, una línea de inicio y otra de fin del tramo con el conteo. Nunca registros de datos ni emails (proposal § Comunes).
- Log group `/aws/lambda/skyroute-<env>-generator`, 14 días, declarado en Terraform antes de la función (Ruling línea Schedule).

### Metrics
- Alarma `skyroute-<env>-generator-invocations` sobre `AWS/Lambda Invocations` a `skyroute-<env>-alarms`. Umbral: OQ3.
- El budget de 10 USD no detecta un desbocado dentro del nivel gratuito (research § Coste); la alarma es la única señal.
- **Limitación conocida (C4):** la alarma de `Invocations` con umbral por encima de lo esperado detecta un exceso de invocaciones, no un generador parado (schedule `DISABLED` por error, rol roto, función en error): con 0 invocaciones la alarma no salta. Nada en este plan detecta ese caso; el owner lo ve al mirar `landing/` (TS-O2). Una alarma de mínimo o de `Errors` no entra en la Propuesta 1 y no se añade aquí.

## Future Considerations

### Open Questions que cambian el plan (para el owner; no resueltas aquí, salvo OQ8, decidida el 2026-11-13)

Gates antes de la PR-B1 (Fase 4): OQ6, OQ10 y OQ11. PC6 (gate antes de la Fase 9) resuelta el 2026-11-14 (ver su fila). Gate antes de la Fase 10: OQ9.

| ID | Pregunta (origen) | Qué cambia | Opción por defecto propuesta |
|----|-------------------|------------|------------------------------|
| OQ1 | ¿Basta stdlib para C1 o se quiere Faker? (P1 OQ1) | Si Faker, el empaquetado y la Decision dejan de valer: vuelta a Propose | stdlib con catálogos propios; el owner revisa una muestra de un día generada en la Fase 1 antes de la Fase 9 |
| OQ2 | Tramos y espera del backfill (P1 OQ2; V12) | Número de invocaciones de la Fase 10 y valor de `backfill_timeout` | Tramo de **1 día** (96 slots), `backfill_timeout = 300` s (C1; no 900), invocación síncrona y la siguiente solo al terminar la anterior: 182 invocaciones. Un tramo mayor solo si N días × la duración medida del tramo de 1 día queda por debajo de 200 s. `backfill_timeout` baja a 60 en la PR-T2 en cuanto termine el backfill. **Techo de riesgo con el schedule de prod `ENABLED`:** mientras el timeout sea 300, una función colgada consume hasta 300 s × 0,25 GB = 75 GB-s por invocación, hasta 7.200 GB-s/día con 96 slots (21.600 con los 2 reintentos del Scheduler), frente a 1.440 GB-s/día con 60 s; estimación sin verificar contra el nivel gratuito. **Sin concurrencia reservada (PC6, hasta la PR-Q):** un backfill puede solaparse con el schedule de prod (las escrituras son idempotentes, Convention "Idempotency") y el tope de coste efectivo es la cuota de 10 de la cuenta, no 1 ejecución |
| OQ3 | Umbral de la alarma de Invocations (P1 OQ3) | Valor de `alarm_threshold`; si el backfill la dispara | `> 120` en 1 h (`Sum`, periodo 3600 s); una alerta durante el backfill se acepta como esperada y se anota en `test.md` |
| OQ4 | Variedad de datos sin Faker (P1 Trade-offs) | Contenido de `model.py`; si C1 se da por cumplido | Inyectar solo duplicados y tardíos (≤ 72 h) por semilla en clickstream; las "dificultades" de otras fuentes, con ellas (ver OQ8) |
| OQ5 | Dónde vive `ALARM_EMAIL` en GitHub (Decision 8) | Paso del owner en Fase 9 y bloque `env` de los workflows | Variable de repositorio (no secreto, no versionada); el job de plan no tiene environment |
| OQ6 | **Gate de la PR-B1 (Fase 4).** Qué boundary lleva `ci-apply-<env>` (Decision 4; la proposal no lo fija; hallazgo S7) | Si el Allow de `ci-boundary` es común a dev y prod, o hay una boundary de CI por entorno (`ci-boundary-<env>`: archivos nuevos y seis copias de Deny) | `ci-boundary` común ampliada con los ARN de los dos entornos; el aislamiento lo dan la inline y el Deny de D2. **No se implementa sin decisión del owner**; alternativa: `ci-boundary-<env>` |
| OQ7 | Driver de Postgres para `seed_postgres.py` (psycopg es LGPL-3.0-only, research H7) | Dependencia local de `make seed-postgres` | Emitir SQL `INSERT` con stdlib y cargarlo con `psql` dentro del contenedor; sin driver |
| OQ8 | Las otras fuentes (gasto CSV, CRM, BCE) en `landing/` | Alcance de C1/C4: P1 Key Changes solo nombra clickstream y Reservas | **Decidido por el owner (2026-11-13): fuera de este plan.** Solo clickstream en `landing/` y Reservas en Postgres local; si más adelante entran en la Fase 2, se vuelve a Propose |
| OQ9 | Fecha concreta de D, el día del primer slot del schedule de prod (FR3; A4) | `to` del backfill, el rango `D-182..D-1` y la comparación de TS-O1 | La fecha del primer slot del schedule de prod, que el owner registra en `working/test.md` tras la Fase 9 |
| OQ10 | **`lambda:GetFunction` para `ci-plan`** (A1; la exclusión viene de proposal § Comunes, no del Ruling Lock) | Si el plan de PR hace refresh de la función tras la Fase 9; fila de `ci-plan` en la PR-B1 | Permitir `lambda:GetFunction` a `ci-plan` solo sobre `function:skyroute-*-generator`, aceptando que `GetFunction` devuelve una URL prefirmada del código (código sintético, sin secretos). Alternativa: excluir la función del plan de PR con `-refresh=false` o `-target` en `terraform-plan.yml`, a costa de un plan menos fiel. **Decisión del owner antes de la PR-B1** |
| OQ11 | **Bloqueo público de S3 a nivel de cuenta** (S9) | Que CI pueda o no desactivar el public access block del bucket de datos | `aws_s3_account_public_access_block` en `bootstrap/` (bloqueo a nivel de cuenta). Alternativa: Deny de `s3:PutBucketPublicAccessBlock` para CI sobre el bucket de datos, aplicable solo tras crear el bucket. **Decisión del owner antes de la PR-B1** |

### Comprobaciones pendientes

| ID | Qué (origen) | Cuándo se resuelve | Opción por defecto |
|----|--------------|--------------------|--------------------|
| PC1 | arm64 de Lambda en eu-west-3 (V8) | primer `apply-dev` de la Fase 9 | arm64; si falla, `architecture = "x86_64"` en una PR |
| PC2 | ID de un slot: `slot` 0-95 desde `scheduled-time` UTC redondeado hacia abajo, y formato `NN` con dos dígitos | antes de la Fase 1 (confirmación del owner) | UTC, `floor(minutos_del_día / 15)`, `slot=00`…`slot=95` |
| PC3 | Lista exacta de acciones del refresh de `ci-plan` y `ci-apply-<env>` (V4, T5) | **primera PR posterior al apply de la Fase 9** (PR-T1; el plan de la PR-M parte de un state vacío y no refresca nada) y primer apply | la fila de Comunes más las diez acciones S3 de Files Changed; lo que falte se añade en bootstrap con otro re-apply |
| PC4 | Reglas de checkov que disparan de verdad (V10) | `static-checks` de PR-M | skips candidatos de proposal § Skips; CKV_AWS_18 sin skip |
| PC5 | Condiciones del trust: `aws:SourceAccount` en el de Lambda (V-nuevo) y, en el de Scheduler, `aws:SourceAccount` más `aws:SourceArn` del schedule group `schedule-group/default` (S5; guía de confused deputy de Scheduler) | primer apply a dev de la Fase 9 | incluirlas; si el servicio rechaza alguna, quitarla en una PR y anotarlo en `working/test.md` |
| PC6 | Cuota de concurrencia de Lambda de la cuenta (C3): AWS exige dejar 10 sin reservar y una cuenta nueva puede tener límite 10, lo que impediría `reserved_concurrent_executions = 1` | **Resuelta el 2026-11-14** con valor 10 (salida del owner: `"Value": 10.0`, `Adjustable: true`; `aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region eu-west-3`) | Ruling Implement decisions (owner javiladino, 2026-11-14), "Concurrencia (PC6)": opción C. Fase 9 sin `reserved_concurrent_executions`; `bootstrap/` pide por Terraform (`aws_servicequotas_service_quota`) la cuota a 1.000 y el owner la aplica en un re-apply; cuando AWS la apruebe, la PR-Q (Fase 11) devuelve la concurrencia reservada de 1. Mientras tanto, los topes son el timeout, la RetryPolicy del Scheduler, la alarma de Invocations y la cuota de 10 de la cuenta. Un backfill puede solaparse con el schedule de prod; las escrituras son idempotentes |
| PC7 | `excludes` de `archive_file` con directorios y zip determinista (A12) | plan/apply de dev de la Fase 9 | `excludes` como en Technical Design; si el zip lleva `tests/` o cambia de hash sin cambios, se ajusta en una PR |

### Known Limitations
- La evidencia de C5 caduca a los 30 días del backfill (lifecycle; T1).
- Hasta la PR-Q (sin concurrencia reservada, PC6) un backfill puede solaparse con el schedule de prod; las escrituras son idempotentes y el tope de coste efectivo es la cuota de 10 de la cuenta. Tras la PR-Q (concurrencia reservada 1), durante cada tramo de backfill el schedule de prod cae en reintentos o pierde slots; se acepta y se regeneran por backfill si hace falta.
- Con `backfill_timeout = 300` y el schedule de prod `ENABLED`, el techo de coste de una función colgada es más alto que con 60 s hasta la PR-T2 (cifras en OQ2).
- La alarma de `Invocations` no detecta un generador parado (Observability, C4).
- La vuelta atrás de la Fase 8 recrea `ci-apply` y reabre T17 hasta un nuevo destroy (Rollout Strategy).
- Cuatro copias de Deny más dos boundaries (T22).
- Riesgo residual de `s3:PutBucketPolicy` en `ci-apply-<env>`, aceptado por el owner (Security Considerations).

## Dependencies

### Development Dependencies
- Python 3.13 local con `pytest` (solo tests; no entra en el zip).
- Terraform 1.17.1 (`terraform-plan.yml:15`), provider `hashicorp/aws ~> 6.73` (`envs/dev/backend.tf:7`) y `hashicorp/archive`; tflint 0.65.0; Docker con Compose.

## Security Considerations
- T17 se cierra en la Fase 8; ningún permiso de workload llega a CI antes (Ruling línea Prod).
- Trust de `ci-apply-<env>` con `StringEquals` y un solo `sub` de ID inmutable; state y `ListBucket` acotados a `envs/<env>/`.
- Deny (a)-(c) de Comunes: crear/adjuntar solo la workload boundary propia (D2), ninguna escritura IAM fuera de `role/workload/skyroute-<env>-*`, `iam:PassRole` solo a lambda y scheduler (Ruling línea Boundary).
- `ci-plan`: sin lock, sin `GetObject` de datos, sin lectura de logs; `lambda:GetFunction` pendiente de OQ10 (la exclusión es de proposal § Comunes, no del Ruling) (D1; Ruling línea Plan en PR).
- IAM de `ci-apply-<env>` sin `iam:*`: lista de acciones en Files Changed (S2); `iam:AttachRolePolicy` denegado; el módulo solo usa `aws_iam_role_policy` (S2, S11).
- Sin URL de función ni `lambda:AddPermission` para CI (S4).
- Trust del Scheduler con `aws:SourceAccount` y `aws:SourceArn` del schedule group (S5, PC5).
- Bloqueo público de S3: OQ11 (S9).
- `alarm_email` con `sensitive = true` (S3); el módulo no lo emite en salidas ni logs.
- Environments de GitHub: `dev` y `prod` con branch policy `main` y sin bypass de admins; `prod` con reviewer (S1, verificado el 2026-11-13; TS-O5). `terraform-plan.yml` no usa environment, de modo que el rol `ci-plan` solo acepta el `sub` `pull_request`.
- PII sintética con email derivado; `.env` ignorado; `alarm_email` fuera del repo.
- SSE-S3, TLS-only, public access block; KMS fuera (`foundations/current/plan.md:237`).
- **Riesgo residual aceptado por el owner (2026-11-14, revisión de seguridad de la Fase 4):** `ci-apply-<env>` tiene `s3:PutBucketPolicy` sobre el bucket de datos de su entorno porque el Ruling Bucket exige política TLS-only; podría poner una política que comparta el bucket con otra cuenta (el account public access block no lo impide y no existe condition key que inspeccione el contenido de la política). Mitigación: el apply solo corre desde `main` (environment con branch policy `main`) y prod exige aprobación del owner.
- `iam:UpdateAssumeRolePolicy` se retira de los roles de CI sobre roles de workload: el trust se crea una vez; cambiarlo exige re-apply de bootstrap.
- `sns:Subscribe` denegado salvo protocolo `email`; `DenyLogRead` también en `ci-boundary`.
- `ci-boundary` usa comodines por servicio sobre los ARN exactos de dev y prod (statement `AllowWorkloadServices`) por el límite de 6.144 caracteres; el permiso efectivo lo fija la inline enumerada de cada rol (boundary = techo). Tamaño estimado 4.300-4.800 caracteres, no medido; lo confirma el plan del owner en la Fase 5.

## Rollout Strategy

### Transición de `ci-apply` (Fases 5-8; A4)

Decisión del owner (2026-11-13): **crear antes de destruir**, con dos re-applies (Fases 5 y 8); la ventana sin rol solo existe en la vuelta atrás; la PR del módulo (Fase 9) espera a la Fase 8. Esto cierra el choque con el texto de proposal § Comunes "Orden de transición", que describía una ventana entre destroy y create.

Orden (proposal § Comunes "Orden de transición"): (1) crear `workload-boundary-<env>` y (2) `ci-apply-dev`/`ci-apply-prod` en la Fase 5; (3) cambiar `terraform-apply.yml` en la PR-W (Fase 6); (4) destruir `ci-apply` en la Fase 8.

| Tramo | Rol de apply válido | Qué no se puede fusionar a `main` |
|-------|---------------------|-----------------------------------|
| Fase 5 aplicada → PR-W mergeada | `ci-apply` (lo usa el workflow) y los nuevos, aún sin usar | PR-M (Fase 9) ni nada que toque `envs/*`: `ci-apply` sigue abierto a T17 |
| PR-W mergeada → Fase 8 aplicada | `ci-apply-dev`/`-prod` | PR-M; cualquier PR que toque `bootstrap/` salvo la PR-B2 |
| **Ventana sin rol de apply**: solo en la vuelta atrás de la Fase 8 (se destruyó `ci-apply`, los roles nuevos fallan y todavía no se ha recreado `ci-apply`) | ninguno | **nada** salvo las PR de la propia vuelta atrás: todo push a `main` lanza `terraform-apply.yml` y fallaría al asumir el rol. El owner no mergea más hasta cerrar la ventana |

- El owner aplica con su identidad (`skyroute-dev`, Convention "Bootstrap identity"); ningún paso depende de un rol de CI.
- Si un push a `main` cae en la ventana, el run falla en "Configure AWS credentials" sin tocar el state; se relanza al cerrar la ventana.
- La PR-M (Fase 9) espera a la Fase 8 aplicada: sin `ci-apply`, T17 está cerrada antes de que CI reciba permisos de workload.

### Vuelta atrás
- **Fase 5 falla o el plan muestra algo inesperado:** el owner no aplica; se corrige la PR-B1 con otra PR. Si el apply quedó a medias, `terraform plan` en `bootstrap/` desde `main` y se reaplica hasta 0 cambios; `ci-apply` sigue intacto porque esta fase no lo toca.
- **Fase 6 falla (TS-W1 rojo):** se revierte la PR-W (vuelve a `role/ci-apply`, que existe); se corrige la inline de `ci-apply-<env>` por Fase 4/5.
- **Fase 8 hecha y los roles nuevos fallan:** revertir la PR-B2 y re-aplicar `bootstrap/` (owner) recrea `ci-apply` con la misma trust (el ARN no cambia); revertir después la PR-W. Entre ambos pasos se está en la ventana sin rol de apply.
  - El run de `terraform-apply.yml` que dispara el merge de la reversión de PR-B2 **se espera fallido**: el workflow aún asume `ci-apply-dev`/`-prod`, que fallan, y `ci-apply` no existe hasta el re-apply. No es una señal nueva de error; se relanza tras revertir la PR-W (A10).
  - Recrear `ci-apply` **reabre T17** (el rol acepta `environment:dev` y `environment:prod` y escribe el state de prod): la PR-M no se mergea hasta un nuevo destroy de `ci-apply` (nueva PR-B2 y nuevo re-apply). El runbook lo dice (S8, A10).
- **Fase 9 falla en `apply-dev`:** `apply-prod` no corre (`needs: apply-dev`, `terraform-apply.yml:55`); se corrige por PR. Para retirar todo, una PR que quite el `module` de `envs/*` (destroy por CI, Convention "IaC only"); el bucket debe estar vacío o llevar `force_destroy` (no previsto; lo decide el owner si llega el caso).

### Despliegue del workload
1. Desarrollo: Fases 1-2 en local.
2. Pruebas: TS-V*, TS-U*, TS-C3.
3. dev: `apply-dev` de PR-M, schedule DISABLED; TS-C4 con una invocación manual.
4. prod: `apply-prod` con aprobación; schedule ENABLED.
5. Seguimiento: backfill (Fase 10), TS-O1-O6 dentro de los 30 días.

## References
- `docs/design/generator-landing/working/research.md` (criterio C1-C6, Hechos (a)-(c), tensiones T1-T22, V1-V23).
- `docs/design/generator-landing/working/proposal.md` (Propuesta 1, § Comunes, § Skips de checkov, § Decision).
- `docs/design/generator-landing/context.md` § Rulings ("Research decisions", "Propose decisions").
- `docs/design/CONTEXT.md` § Conventions.
- `docs/runbooks/foundations-bootstrap.md`; `infra/terraform/bootstrap/ci_roles.tf`; `.github/workflows/terraform-plan.yml`, `terraform-apply.yml`.
- Tarea: brief del orquestador para la etapa Plan (2026-11-13). Siguiente etapa: `reppit-implement`, tras el visto bueno del owner.
