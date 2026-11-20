---
type: Plan
---

# bronze-silver: Bronze y Silver con Spark + Iceberg (Proposal 2) Design Document

> **Propuesta elegida:** Proposal 2, "por tabla de extremo a extremo, con PySpark de pip" (`working/proposal.md` § Decision, javiladino, 2026-11-20).
> **Restricciones vinculantes:** `context.md` § Rulings, "Research decisions" (con sus enmiendas de Propose), y las Conventions Table format, Medallion layers, Compute split, Region, No hourly-billed resources, IaC only, Apply gate, Idempotency, Git workflow y Bootstrap identity (`docs/design/CONTEXT.md` § Conventions).
> **Decisiones del Plan:** `context.md` § Rulings, "Plan decisions" (javiladino, 2026-11-20 19:00): el owner aceptó las 9 recomendaciones; ver § Decididas.
> **Revisión:** 1 ronda (adversarial-reviewer, NEEDS-REVISION), hallazgos aplicados 2026-11-20. Gate del precio de Glue Flex satisfecho (owner, 0,29 USD/DPU-h).
> **Alcance:** las 8 PRs de la Proposal 2. **Fuera de alcance:** Gold y dbt, Airflow (los jobs se lanzan a mano o por `make`), gasto publicitario y CRM, Lake Formation, paso a plan Paid, MoR en Silver.

## Current Context

- No existe código Spark ni ningún recurso Glue o Athena (research Summary, C4 "Glue/Athena"). El clickstream llega a `landing/clickstream/ingest_date=…/slot=NN/part.json.gz` (`generators/ota/keys.py:47-51`), determinista por `(run_date, slot)` (`keys.py:12-15`), con duplicados solo dentro del archivo (`clickstream.py:72-74`) y tardíos de hasta 72 h (`clickstream.py:15`, `36-41`).
- Las Reservas viven solo en Postgres local con una versión por reserva: `bookings` (`docker/postgres/init/001_bookings.sql:1-11`), sembrada con `INSERT … ON CONFLICT DO NOTHING` (`seed_postgres.py:36`); el estado se elige una vez (`model.py:70-74`). Cada evento de navegación tiene sesión y cliente propios (`clickstream.py:33`, `48`): hoy no hay sesiones de varios eventos ni historial para SCD2 (T2, T12). No hay fuente FX (C3).
- IAM: `workload-boundary-dev` solo permite `s3:PutObject` en `landing/*`, logs e invocar la Lambda (`workload_boundary_dev.tf:9-34`; prod igual); la ci-boundary no da Glue, Athena ni SSM (`ci_roles.tf:207-226`) y `pass_role_services` solo lista Lambda y Scheduler (`ci_roles.tf:63`), de modo que `DenyPassRoleWrongService` (`ci_apply_dev.tf:160-168`, `ci_apply_prod.tf:160-168`, `ci_roles.tf:285-293`, `552-560`) bloquea el PassRole a Glue (T4).
- El bucket de datos y su único `aws_s3_bucket_lifecycle_configuration` están en `modules/generator-landing/bucket.tf:76-102`; `landing/` expira a 30 días desde la creación del objeto (T1). dev tiene `schedule_enabled = false` (`envs/dev/main.tf:5`, T7).
- Tooling: `make test-generators` corre `pytest generators/tests -q` (`Makefile:7-8`); no hay dependencias Python declaradas ni CI de pytest (C5, T9). Proveedor `hashicorp/aws ~> 6.73` y Terraform `>= 1.11.0` (`modules/generator-landing/versions.tf:1-14`).

## Requirements

### Functional Requirements

Criterio de la fase (README § Fases): "Jobs PySpark con tests, MERGE, sesionización, SCD2, conversión de divisas. Hecho cuando relanzar un día da exactamente el mismo resultado." Desglose:

- **R1. Generador:** sesiones por cliente de varios eventos con compras enlazadas; Reservas con cambios de estado (`ON CONFLICT … DO UPDATE`), trigger que escribe cada cambio en `bookings_history` con `changed_at = NEW.updated_at`; export diario idempotente a `landing/bookings/ingest_date=D/part.json.gz` desde `bookings_history` del día lógico D; tarea FX del BCE a `landing/fx/` (Ruling "Generador", "Reservas a `landing/`", "Tipos de cambio").
- **R2. Bronze:** un job genérico `spark/jobs/bronze/ingest.py --source {clickstream,bookings,fx} --run-date D`, payload íntegro más `_ingested_at`, `_batch_id`, `_source_file`, `_ingest_date` derivados de la fecha lógica (Convention Medallion layers; Ruling "`_ingested_at`"); reemplazo de partición por `_ingest_date`; falla si no hay archivos de entrada para D.
- **R3. Silver:** `bookings_scd2`, `bookings_current`, `fx_daily`, `bookings_eur`, `events`, `sessions` con el modelo de la Proposal 2 § Modelo de Silver; email sustituido por HMAC-SHA256 (Ruling "PII"); copy-on-write; WAP con rama y `fast_forward` tras los checks YAML (Ruling "Checks WAP").
- **R4. Relanzar un día:** relanzar D en cualquier momento, incluso tras D+5, deja Silver idéntico a la ejecución en orden (Ruling "Relanzar un día"; Convention Idempotency).
- **R5. Mantenimiento:** `spark/jobs/maintenance/{expire_snapshots,rewrite_data_files}.py` (Ruling "Escritura Iceberg").
- **R6. Infra:** PR de `bootstrap/` primero; módulo `lakehouse` con bases `skyroute_{bronze,silver,ops}`, workgroup `skyroute-<env>`, roles `local-data` y `glue-job`, parámetro HMAC; Glue jobs de demo sin trigger (Ruling "Athena", "Permisos", "Credenciales en local").
- **R7. Histórico:** regeneración de 182 días con el generador nuevo e ingesta en Bronze antes de que pasen 30 días (Ruling "Histórico").

### Non-Functional Requirements

- **Coste:** demo Glue Flex de 7 jobs × 3 min × 2 DPU × 0,29 USD/DPU-h ≈ 0,20 USD (precio de eu-west-3 confirmado por el owner el 2026-11-20); Athena con corte de 100 MB por consulta; nada con cobro por hora (Convention No hourly-billed resources). Budget de 10 USD sin cambios (Ruling "Budget").
- **Paridad local/Glue:** `pyspark==3.5.4`, Python 3.11, `iceberg-spark-runtime-3.5_2.12:1.7.1` e `iceberg-aws-bundle:1.7.1` fijados a Glue 5.0 (AWS Big Data Blog y tabla de migración de Glue 5.0; un anuncio "What's New" dice Iceberg 1.6.1, así que la Fase 4 lo vuelve a comprobar en la doc oficial antes de fijar).
- **Seguridad:** mínimo privilegio por nombre (`skyroute_*`, `skyroute-<env>-*`); credenciales locales temporales de 1 h con MFA; la clave HMAC nunca en el state ni en el repo.
- **Región:** `AWS_REGION=eu-west-3` en Spark local y en todo recurso (Convention Region).
- **Volumen:** ~178 KB/día de clickstream y 120 reservas/día (C1, C2); no se optimiza para el volumen del blueprint.

## Design Decisions

### 1. Cortes verticales por tabla (8 PRs)
Se implementa la Proposal 2 porque cada PR cierra una capacidad del criterio (SCD2, FX, sesión) y se revisa entera, sin enmendar ninguna Convention (`proposal.md` § Decision). Alternativas: capa a capa (Proposal 1, SCD2 más complejo y sesión del generador) y recálculo completo (Proposal 3, requiere enmienda de Idempotency). Coste: más ciclos de gate del owner.

### 2. Un solo runtime local: `pyspark` de pip con versiones de Glue 5
Imagen ligera propia (`docker/spark/Dockerfile`) y `spark/requirements.txt` con las versiones fijadas; la demo de Glue (Fase 8) es la única prueba de paridad. Alternativa descartada: imagen de Glue 5 en local (lenta para pytest). Riesgo aceptado: deriva de versiones que solo detecta la demo.

### 3. Bronze genérico antes de Silver
`ingest.py --source` copia payload y columnas técnicas; asegura el histórico regenerado antes del lifecycle (T1). Escritura `INSERT OVERWRITE` dinámico por `_ingest_date`, que es reemplazo de partición (Convention Idempotency); el job falla sin archivos de entrada en lugar de dejar la partición antigua (Base común).

### 4. SCD2 por `(booking_id, history_id)` con cierre acotado
MERGE de inserción por la clave única `(booking_id, history_id)`; cierre separado de la versión previa solo si `valid_from < v0` y `valid_to IS NULL OR valid_to > v0`; la última versión del lote solo queda `is_current` si no hay en target una posterior por `(valid_from, history_id)` (Proposal 2 § Modelo de Silver). `bookings_current` con MERGE condicional por `(changed_at, history_id)`. Orden de versiones siempre `(changed_at, history_id)` (Base común "Clave de orden").

### 5. Sesionización por inactividad en Silver
30 min de inactividad por `customer_id`, orden `(event_ts, event_id)`; el día D recalcula leyendo `silver.events` con `event_ts` en `[D-3 00:00 − gap, D+1 24:00)` sin corte por `_ingest_date` (el margen `gap` captura la sesión que empezó antes de D-3 y cruza a D-3; esa sesión, con `session_start_date < D-3`, se recalcula pero no se reescribe: queda fuera del rango del MERGE y sus eventos no generan sesión nueva en D-3), y reemplaza las sesiones que empiezan en `[D-3, D]`. Se escribe con **MERGE con `WHEN NOT MATCHED BY SOURCE AND target.session_start_date BETWEEN D-3 AND D THEN DELETE`** (Ruling "Plan decisions") porque cuenta como MERGE para el criterio y no deja sesiones huérfanas cuando cambia `session_key = hash(customer_id, primer event_id)`. Una sesión que cruza medianoche pertenece al día de su primer evento. El `session_id` del generador solo sirve de oráculo en tests, y solo para eventos no tardíos (el generador desplaza los tardíos hasta 72 h, `clickstream.py:36-41`, pero conserva su `session_id`, `clickstream.py:48`). Umbral de 30 min, `--session-gap-minutes` (Ruling "Plan decisions").

### 6. FX
`fx_daily` por (día natural, divisa) arrastrando el último día hábil del BCE; reemplazo por fecha; si no hay tipo previo, el check WAP falla y no se publica. `bookings_eur` aplica el tipo del día de `created_at` y guarda `currency`, `fx_rate_applied` y `amount_eur decimal(12,2)` con `HALF_EVEN` (Ruling "Plan decisions") (Ruling "Tipo de cambio por reserva").

### 7. Lifecycle de `athena-results/` en `generator-landing`
Lo decide el código: un bucket admite un solo `aws_s3_bucket_lifecycle_configuration` y el de este bucket está en `modules/generator-landing/bucket.tf:76-102`. La regla de 7 días se añade allí, no en `lakehouse` (resuelve Proposal OQ compartida 5, segunda mitad).

### 8. Clave HMAC con `value_wo`
`aws_ssm_parameter` admite `value_wo` y `value_wo_version` en `hashicorp/aws` v6.73.0 (doc del recurso en la etiqueta `v6.73.0`: "Write-Only", fuera del state, exige `value_wo_version`); Terraform `>= 1.11` ya está fijado. El valor sale de un `ephemeral "random_password"` con `value_wo_version` para rotar (Ruling "Plan decisions").

### 9. Checks WAP propios en YAML
Reglas en `spark/checks/<tabla>.yaml` (ruta fijada aquí), motor en `spark/lib/checks.py`; tablas Silver con `write.wap.enabled=true`, escritura con `spark.wap.branch` y publicación con `CALL <catalog>.system.fast_forward('<tabla>', 'main', '<rama>')` (Base común "WAP").

Ciclo de rama por ejecución, para que relanzar D funcione siempre: (1) si existe `run_<D>`, se borra; (2) se crea `run_<D>` desde el snapshot actual de `main`; (3) se escribe en la rama; (4) checks; (5) `fast_forward` de `main` a `run_<D>`; (6) se borra la rama. Si un check falla, la rama se conserva para inspección y la borra el paso (1) de la siguiente ejecución. Así `main` nunca diverge de la rama y el `fast_forward` no falla al relanzar D tras D+1 (test U21).

### 10. `history_id` reproducible
El backfill recrea `bookings_history` desde vacío (`TRUNCATE bookings, bookings_history RESTART IDENTITY`) y aplica los cambios en orden determinista `(updated_at, booking_id, versión)`; el test de Validation 1 de la Proposal 2 lo garantiza (Ruling "Plan decisions"). Alternativa descartada: `change_seq` del generador.

### 11. Scripts de Glue como `aws_s3_object` en `scripts/`
Elegido por el owner (opción A). `ci-plan` necesita leer esos objetos para el refresh: `DenyDataObjectRead` (`ci_roles.tf:510-515`) pasa a usar `NotResource` que exime `arn:aws:s3:::skyroute-*-data-*/scripts/*`, y un Sid nuevo `PlanScriptsRead` da `s3:GetObject`, `s3:GetObjectTagging` (HeadObject va con GetObject) solo en `scripts/*`. `ci-apply-{dev,prod}` reciben un Sid `ApplyScriptsObjects` con `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:GetObjectTagging`, `s3:PutObjectTagging` en `arn:aws:s3:::skyroute-<env>-data-*/scripts/*`; hoy `ApplyS3` (`ci_apply_dev.tf:60-65`) y `AllowWorkloadServices` (`ci_roles.tf:207-226`) solo cubren el ARN del bucket, así que la ci-boundary también añade `arn:aws:s3:::skyroute-*-data-*/scripts/*`. Los demás prefijos de datos siguen denegados a ci-plan y sin acceso para ci-apply.

### 12. SSM y KMS para el parámetro HMAC
`ssm:DescribeParameters` no admite ARN de recurso: va con `Resource = "*"` en ci-plan y ci-apply. ci-plan añade un Deny explícito `DenyKmsDecrypt` (`kms:Decrypt`, `Resource "*"`): el refresh de un `value_wo` no lee el valor (los write-only no se devuelven ni se guardan; solo se compara `value_wo_version`), así que ci-plan usa `ssm:GetParameter` sin descifrado. ci-apply-{dev,prod} necesitan, para escribir un `SecureString` con la clave gestionada `aws/ssm`, `kms:Encrypt` y `kms:GenerateDataKey` con condición `kms:ViaService = ssm.eu-west-3.amazonaws.com`, más `kms:DescribeKey`; la ci-boundary añade `kms:Encrypt`, `kms:GenerateDataKey`, `kms:DescribeKey` con la misma condición. Ningún rol de CI recibe `kms:Decrypt`; solo `glue-job` y `local-data` (vía `workload-boundary-<env>`, con `kms:ViaService` de SSM) para leer la clave.

### 13. Tamaño de la ci-boundary
La ci-boundary (`aws_iam_policy.ci_boundary`, `ci_roles.tf:179-362`, `jsonencode` en `186-361`) renderiza hoy ~5.535 caracteres minificados frente al límite de 6.144 (medido por executor el 2026-11-20, ±50): quedan ~600. Una boundary es una sola política, así que no se puede partir. Las ARN nuevas se agrupan con comodines ya usados (`arn:aws:glue:eu-west-3:<acct>:*/skyroute*`, `arn:aws:athena:eu-west-3:<acct>:workgroup/skyroute-*`, `arn:aws:ssm:eu-west-3:<acct>:parameter/skyroute/*`, `arn:aws:s3:::skyroute-*-data-*/scripts/*`, `arn:aws:iam::<acct>:role/workload/skyroute-*-glue-job`) en un único Sid y se fusionan statements existentes si hace falta. Tamaño esperado tras la PR 1: ≤ 6.000 caracteres; lo mide un paso de verify de la Fase 1.

## Technical Design

### 1. Core Components

- `spark/lib/args.py`: `--run-date YYYY-MM-DD` obligatorio y `--catalog-name`, `--catalog-impl` (`glue` | `hadoop`), `--warehouse`; mismos argumentos en local y en Glue (Ruling "Dónde corre Spark").
- `spark/lib/session.py`: `build_spark(args)` configura el catálogo Iceberg por parámetro; ninguna lectura de reloj.
- `spark/lib/checks.py`: `run_checks(df, rules_yaml) -> list[Failure]`; si hay fallos, el job termina con código ≠ 0 y no llama a `fast_forward`.
- `spark/lib/wap.py`: ciclo de rama de Design Decision 9 (borrar `run_<D>` si existe, crearla desde `main`, escribir, checks, `fast_forward`, borrar; conservarla si falla un check).
- `spark/jobs/bronze/ingest.py --source {clickstream,bookings,fx}`: lee `landing/<source>/ingest_date=D/`, añade columnas técnicas, `INSERT OVERWRITE` por `_ingest_date` con `spark.sql.sources.partitionOverwriteMode=dynamic` (fijado en `session.py`, local y Glue); error si no hay archivos.
- Rol `skyroute-<env>-glue-job`: path `/workload/`, boundary `workload-boundary-<env>`, trust a `glue.amazonaws.com`. Los Glue jobs usan `--TempDir s3://skyroute-<env>-data-…/glue-temp/`; la boundary le da Get/Put/Delete en `glue-temp/*` y `bucket.tf` añade una regla de lifecycle de 1 día para `glue-temp/`.
- Rol `skyroute-<env>-local-data`: en dev, trust a `user/skyroute-dev` con MFA. En prod el rol no se crea hasta el cierre de la fase (Ruling "Plan decisions": fases 4–8 leen dev); el módulo lo condiciona con `create_local_data_role` (`false` en prod) y, al cerrar, la trust de prod también apunta a `user/skyroute-dev` con MFA.
- `spark/jobs/silver/{bookings_scd2,bookings_current,fx_daily,bookings_eur,events,sessions}.py`: Design Decisions 4-6; `events` hace MERGE `WHEN NOT MATCHED INSERT` por `event_id`, partición `days(event_ts)`, email → HMAC con la clave leída de SSM (en tests, clave fija por parámetro).
- `spark/jobs/maintenance/{expire_snapshots,rewrite_data_files}.py`: `--table`, `--older-than` derivado de `--run-date`, nunca de `now()`.
- `generators/ota/export_bookings.py --run-date D`: lee `bookings_history` de `[D 00:00, D+1 00:00)` UTC `ORDER BY history_id` y escribe `landing/bookings/ingest_date=D/part.json.gz` (gzip `mtime=0`, `sort_keys`, como `clickstream.py:77-80`).
- `generators/fx/ecb.py --run-date D` y `--from/--to`: descarga la referencia del BCE, escribe `landing/fx/ingest_date=D/part.json.gz`; si falla, error y reintento; nunca inventa un tipo.

### 2. Data Models

- `bookings_history` (Postgres): `history_id bigserial PRIMARY KEY`, `booking_id`, `status`, columnas de `bookings`, `changed_at timestamptz NOT NULL` (= `NEW.updated_at`). Trigger `AFTER INSERT OR UPDATE ON bookings FOR EACH ROW`.
- Bronze (`skyroute_bronze.{clickstream,bookings,fx}`): payload + `_ingested_at` (`run_date` 00:00 UTC + slot × 15 min; slot 0 en fuentes diarias), `_batch_id` = hash(`run_date`, `_source_file`), `_source_file`, `_ingest_date`; partición `_ingest_date`.
- `skyroute_silver.bookings_scd2`: columnas de reserva + `history_id`, `valid_from` (= `changed_at`), `valid_to`, `is_current`, `row_hash`. Clave `(booking_id, history_id)`.
- `skyroute_silver.bookings_current`: una fila por `booking_id`.
- `skyroute_silver.fx_daily`: `fx_date`, `currency`, `rate_to_eur`, `source_date` (día hábil de origen).
- `skyroute_silver.bookings_eur`: `booking_id`, `currency`, `amount`, `fx_rate_applied`, `amount_eur decimal(12,2)`.
- `skyroute_silver.events`: eventos tipados y deduplicados, `email_hmac` en lugar de `email`, consentimiento conservado.
- `skyroute_silver.sessions`: `session_key`, `customer_id`, `session_start`, `session_end`, `session_start_date`, `n_events`, `converted`, `booking_id`.
- Glue jobs: `skyroute-<env>-bronze-ingest` y `skyroute-<env>-silver-<tabla>` (nombre fijado aquí), Glue 5.0, `execution_class = "FLEX"`, 2 DPU, sin trigger.

### 3. Integration Points

```
generador (Lambda, prod schedule) -> landing/clickstream/
generador local -> Postgres bookings --trigger--> bookings_history -> export -> landing/bookings/
tarea FX local (BCE)                                                -> landing/fx/
landing/* --bronze/ingest.py--> skyroute_bronze.* --silver/*.py (WAP)--> skyroute_silver.*
Athena workgroup skyroute-<env> -> consultas de comprobación (resultados en athena-results/, 7 días)
```

Lo local (export, FX, Spark) usa credenciales temporales del perfil `skyroute-<env>-local-data`; la boundary ya permite `s3:PutObject` en `landing/*` (`workload_boundary_dev.tf:11-15`).

### 4. Files Changed

**PR 1 (bootstrap, Fase 1)**

- `infra/terraform/bootstrap/ci_roles.tf` (lines 16-27: añadir a `env_arns` los ARN de Glue `catalog`, `database/skyroute_*`, `table/skyroute_*/*`, `job/skyroute-<env>-*`, Athena `workgroup/skyroute-<env>`, SSM `parameter/skyroute/<env>/*` y el rol `role/workload/skyroute-<env>-glue-job`; line 63: añadir `"glue.amazonaws.com"` a `pass_role_services`; lines 79-170: nuevas listas `apply_glue_actions`, `apply_athena_actions`, `apply_ssm_actions`; lines 207-226: `AllowWorkloadServices` hoy solo cubre ARN de bucket; se añade un Sid de techo agrupado con comodines (`glue:*`, `athena:*`, `ssm:*`, `kms:Encrypt`/`GenerateDataKey`/`DescribeKey` con `kms:ViaService` de SSM, y `s3:*` en `arn:aws:s3:::skyroute-*-data-*/scripts/*`; Design Decisions 11-13); lines 393-600, ci-plan: nuevos Sids `PlanGlueRead` (`glue:Get*`), `PlanAthenaRead` (`athena:GetWorkGroup`, `athena:ListTagsForResource`), `PlanSsmRead` (`ssm:GetParameter`, `ssm:ListTagsForResource` en `parameter/skyroute/*`), `PlanSsmDescribe` (`ssm:DescribeParameters`, `Resource "*"`), `PlanKmsDescribe` (`kms:DescribeKey` de `alias/aws/ssm`), `PlanScriptsRead` (`s3:GetObject`, `s3:GetObjectTagging` en `scripts/*`), `DenyKmsDecrypt`; lines 510-515: `DenyDataObjectRead` pasa a `NotResource` que exime `scripts/*`).
- `infra/terraform/bootstrap/ci_apply_dev.tf` (insertar entre las lines 60-118 nuevos Sids `ApplyGlue`, `ApplyAthena`, `ApplySsm`, `ApplySsmDescribe` (`Resource "*"`), `ApplyKmsViaSsm` y `ApplyScriptsObjects` acotados a dev; lines 60-65: `ApplyS3` sin cambio, solo cubre el ARN del bucket; lines 84-94: el PassRole cubre `skyroute-dev-glue-job` vía `pass_role_services`; lines 160-168: `DenyPassRoleWrongService` sin cambio de texto, hereda la lista).
- `infra/terraform/bootstrap/ci_apply_prod.tf` (mismos rangos: inserción en 60-118, 84-94 y 160-168, con ARN de prod).
- `infra/terraform/bootstrap/workload_boundary_dev.tf` (lines 9-34: añadir `s3:GetObject`/`s3:PutObject` en `<bucket>/*`, `s3:ListBucket` en el bucket, `s3:DeleteObject` solo en `bronze/*`, `silver/*`, `athena-results/*`, `glue-temp/*`; Glue Catalog sobre `skyroute_*`; Athena sobre `skyroute-dev`; `ssm:GetParameter` del parámetro HMAC y `kms:Decrypt` con `kms:ViaService` de SSM; logs de `/aws-glue/*` para el rol `glue-job`; `DenyStateBucketAccess` intacto).
- `scripts/policy_size.py` (NEW: recibe la ruta de un plan guardado por el owner, obtiene su JSON con `terraform show -json` y escribe la longitud minificada de la política `ci-boundary`; falla si ≥ 6.144).
- `infra/terraform/bootstrap/workload_boundary_prod.tf` (lines 9-34: lo mismo para prod).

**PR 2 (módulo lakehouse, Fase 2)**

- `infra/terraform/modules/lakehouse/{versions,variables,glue_catalog,athena,iam,ssm,outputs}.tf` (NEW: bases `skyroute_{bronze,silver,ops}`; workgroup `skyroute-<env>` con `enforce_workgroup_configuration = true`, `bytes_scanned_cutoff_per_query = 104857600`, salida `s3://<bucket>/athena-results/`; rol `skyroute-<env>-local-data` en `/workload/` con boundary `workload-boundary-<env>`, trust a `user/skyroute-dev` con `Bool aws:MultiFactorAuthPresent = true`, `max_session_duration = 3600`; rol `skyroute-<env>-glue-job`; `aws_ssm_parameter` `SecureString` `/skyroute/<env>/hmac-email-key` con `value_wo`).
- `infra/terraform/modules/generator-landing/bucket.tf` (lines 76-102: nuevas reglas `expire-athena-results-7d`, prefijo `athena-results/`, 7 días, y `expire-glue-temp-1d`, prefijo `glue-temp/`, 1 día; Design Decision 7).
- `infra/terraform/envs/dev/main.tf` (lines 1-7: añadir `module "lakehouse"` con `env = "dev"` y `bucket_name = module.generator_landing.bucket_name`).
- `infra/terraform/envs/prod/main.tf` (lines 1-7: lo mismo con `env = "prod"`).
- `~/.aws/config` del owner (fuera del repo, no IaC: perfiles `skyroute-dev-login` y `skyroute-dev-local-data`).

**PR 3 (generador, Fase 3)**

- `generators/ota/model.py` (lines 59-88: `_bookings` emite versiones de estado por reserva con `updated_at` creciente; nueva función `customer_journeys(run_date)` con sesiones de varios eventos por cliente que acaban en `purchase` de su reserva).
- `generators/ota/clickstream.py` (lines 26-56: eventos de navegación agrupados por cliente/sesión desde `model`; lines 58-70: `purchase` en la sesión del recorrido; lines 15-17 y 36-41 sin cambio: tardíos ≤ 72 h y duplicados se conservan).
- `generators/ota/seed_postgres.py` (lines 15-22: columnas; lines 31-37: `INSERT … ON CONFLICT (booking_id) DO UPDATE` por versión en orden determinista; lines 40-51: modo `--rebuild` que antepone `TRUNCATE bookings, bookings_history RESTART IDENTITY`).
- `generators/ota/keys.py` (lines 8-9: añadir `BOOKINGS_PREFIX = "landing/bookings"` y `FX_PREFIX = "landing/fx"`; lines 47-51: `landing_key` sin cambio; nueva `daily_key(prefix, run_date)`).
- `docker/postgres/init/002_bookings_history.sql` (NEW: tabla `bookings_history` y trigger).
- `generators/ota/export_bookings.py` (NEW), `generators/fx/__init__.py`, `generators/fx/ecb.py` (NEW).
- `generators/tests/test_sessions.py`, `test_bookings_history.py`, `test_export_bookings.py`, `test_fx.py` (NEW).
- `requirements-dev.txt` (NEW: `pytest`, `ruff`, `pyyaml`, `psycopg` con versión fijada, para Python 3.11; lo usa el venv del paso 0 del Implementation Plan).
- `Makefile` (lines 1-14: targets `export-bookings`, `fx`, `test-spark`; `seed-postgres` admite `REBUILD=1`).

**PR 4 (Bronze genérico, Fase 4)**

- `spark/requirements.txt` (NEW: `pyspark==3.5.4` y lo demás de Glue 5), `docker/spark/Dockerfile`, `docker/spark/compose.yml` (NEW).
- `spark/lib/{__init__,args,session,checks,wap,technical_columns}.py` (NEW).
- `spark/jobs/bronze/ingest.py` (NEW).
- `spark/tests/conftest.py` (NEW: catálogo Iceberg `hadoop` en `tmp_path`), `spark/tests/test_bronze_ingest.py` (NEW).

**PR 5-7 (cortes Silver, Fases 5-7)**

- PR 5: `spark/jobs/silver/{bookings_scd2,bookings_current}.py`, `spark/checks/{bookings_scd2,bookings_current}.yaml`, `spark/tests/test_bookings_scd2.py`, `test_bookings_current.py` (NEW).
- PR 6: `spark/jobs/silver/{fx_daily,bookings_eur}.py`, `spark/checks/{fx_daily,bookings_eur}.yaml`, `spark/tests/test_fx.py` (NEW).
- PR 7: `spark/jobs/silver/{events,sessions}.py`, `spark/checks/{events,sessions}.yaml`, `spark/tests/test_events.py`, `test_sessions.py`, `test_rerun_order.py` (NEW).

**PR 8 (mantenimiento y demo, Fase 8)**

- `spark/jobs/maintenance/{expire_snapshots,rewrite_data_files}.py`, `spark/tests/test_maintenance.py` (NEW).
- `infra/terraform/modules/lakehouse/glue_jobs.tf` (NEW: 7 `aws_glue_job` Flex, 2 DPU, Glue 5.0, sin trigger; `aws_s3_object` de los scripts en `scripts/`).
- `AGENTS.md` (lines 101-102, § Comandos de build y test: sustituir los `TODO` de lint Python y tests Spark por `ruff check spark generators` y `pytest spark/tests -q`, dentro del AGENTS.md budget).
- `.github/workflows/spark-tests.yml` (NEW: aprobado en el Ruling "Plan decisions"; instala `requirements-dev.txt` y `spark/requirements.txt` en Python 3.11).

## Implementation Plan

Cada fase es una PR en su rama (Convention Git workflow: ningún agente hace commit ni push sin que el owner lo pida). Ningún agente ejecuta `terraform plan`, `terraform apply` ni comandos AWS (Convention Apply gate): esos pasos son del owner o de la CI, y su salida la aporta el owner como evidencia (Convention Verification ownership). Comandos para executor: uno simple por llamada (Convention Simple shell commands).

Antes de cualquier verify de Terraform, quien lo ejecute necesita una sesión `aws login` válida o el entorno sin `AWS_PROFILE`: el 2026-11-20 `terraform -chdir=infra/terraform/bootstrap init -backend=false` falló en local al intentar refrescar una sesión caducada (`validate` sí pasó).

0. **Entorno Python (antes del primer pytest, Fase 3).** pytest no está instalado en local (`python3` es Homebrew 3.15) y Glue 5 usa Python 3.11. El owner instala Python 3.11 si falta; después, un comando por llamada:
   - `python3.11 -m venv .venv`
   - `.venv/bin/python -m pip install -r requirements-dev.txt`
   - `.venv/bin/python -m pip install -r spark/requirements.txt` (desde la Fase 4)
   - Todos los verify de pytest y ruff de este plan se ejecutan como `.venv/bin/python -m pytest …` y `.venv/bin/python -m ruff …`. `.venv/` va en `.gitignore` si no está.

1. **Fase 1: PR de `bootstrap/` (permisos).**
   - executor cambia los archivos de la PR 1; security-reviewer la revisa.
   - Verify (executor): `terraform fmt -check -recursive infra/terraform`, `terraform -chdir=infra/terraform/bootstrap init -backend=false`, `terraform -chdir=infra/terraform/bootstrap validate`, `tflint --chdir=infra/terraform/bootstrap --config=$PWD/infra/terraform/.tflint.hcl`.
   - Verify de tamaño (owner, offline sobre su plan): `terraform -chdir=infra/terraform/bootstrap plan -out=bootstrap.tfplan` y después `python3 scripts/policy_size.py infra/terraform/bootstrap/bootstrap.tfplan` (el script llama a `terraform show -json` con `subprocess`, sin redirecciones ni pipes). Éxito: longitud minificada de `ci-boundary` ≤ 6.000 (esperado; límite 6.144, Design Decision 13).
   - Owner: aplica desde su máquina con el plan pegado como evidencia (Apply gate, excepción de bootstrap).
   - Éxito: el plan solo cambia `ci-boundary`, `ci-plan`, `ci-apply-{dev,prod}` y `workload-boundary-{dev,prod}`; ningún `destroy`; `pass_role_services` incluye `glue.amazonaws.com`.

2. **Fase 2: PR del módulo `lakehouse`.**
   - Precondición: Fase 1 aplicada por el owner.
   - executor crea el módulo, la regla de lifecycle y las instancias en `envs/`.
   - Verify (executor): `terraform fmt -check -recursive infra/terraform`, `terraform -chdir=infra/terraform/envs/dev init -backend=false`, `terraform -chdir=infra/terraform/envs/dev validate`, `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl` (y los mismos para `envs/prod`).
   - CI: `terraform-plan.yml` publica el plan en la PR (solo `create` de bases, workgroup, roles, parámetro y la regla de lifecycle como `update in-place`); `apply` desde CI al fusionar (dev) y con aprobación en prod.
   - **Gate del owner (MFA, Ruling "Credenciales en local"):** con `skyroute-dev-local-data` ya creado, el owner configura `~/.aws/config` y corre `aws sts get-caller-identity --profile skyroute-dev-local-data`. Éxito: devuelve `assumed-role/skyroute-dev-local-data/…`. Si falla, alternativa `aws sts get-session-token` con `--serial-number` y `--token-code` y asunción del rol con esas credenciales. Si las dos fallan, se para la fase y el orquestador pide al owner una enmienda del Ruling. Ninguna fase que use AWS desde local (4 en adelante) empieza sin este gate.

3. **Fase 3: PR del generador.**
   - executor cambia `generators/` y el DDL; tests nuevos.
   - Verify (executor): `.venv/bin/python -m pytest generators/tests -q`.
   - Éxito: pasan los tests existentes y los nuevos (sesión con ≥ 2 eventos que acaba en `purchase` de una reserva; reserva con ≥ 2 versiones y `updated_at` creciente; dos regeneraciones del mismo rango dan `bookings_history` idéntica, `history_id` incluido; export de D idéntico byte a byte en dos ejecuciones; FX sin publicación devuelve error, no un tipo inventado).
   - Owner: despliegue por CI solo en dev (la Lambda de dev pasa al generador nuevo; schedule sigue `DISABLED`). Prod conserva el generador actual hasta el cierre de la fase, cuando se despliega y se regenera su histórico (Ruling "Plan decisions").

4. **Fase 4: regeneración del histórico en dev + Bronze genérico.**
   - Precondiciones: Fases 2 y 3 desplegadas en dev; gate de MFA superado; entorno dev (Ruling "Plan decisions").
   - executor crea `spark/` base y `ingest.py` con tests.
   - Verify (executor): `.venv/bin/python -m pytest spark/tests -q`.
   - **Gate del owner (histórico en dev, Ruling "Histórico"):** el owner regenera 182 días en dev (backfill de la Lambda de dev, `make seed-postgres` con `REBUILD=1`, export de Reservas y FX del mismo rango con `generators/fx/ecb.py --from --to`) y anota la fecha R. Después corre la ingesta Bronze de las tres fuentes para los 182 días. Éxito: antes de R + 30 días, Athena devuelve 182 valores distintos de `_ingest_date` en `skyroute_bronze.clickstream`, `bookings` y `fx` (workgroup `skyroute-dev`). Si R + 30 se acerca sin ingesta, se regenera otra vez (determinista). Al cerrar la fase, el mismo gate se repite en prod con su propia fecha R.

5. **Fase 5: corte Reservas (`bookings_scd2`, `bookings_current`).**
   - Verify (executor): `.venv/bin/python -m pytest spark/tests -q`.
   - Éxito: tests SCD2 de Testing Strategy U5-U9 y U21 en verde.

6. **Fase 6: corte FX (`fx_daily`, `bookings_eur`).**
   - Verify (executor): `.venv/bin/python -m pytest spark/tests -q`.
   - Éxito: tests U10-U12.

7. **Fase 7: corte clickstream (`events`, `sessions`).**
   - Verify (executor): `.venv/bin/python -m pytest spark/tests -q`.
   - Éxito: tests U13-U19 y U21-U23, incluida la independencia del orden (U21 se escribe en la Fase 5 con `wap.py`).

8. **Fase 8: mantenimiento, demo Glue y comandos de AGENTS.md.**
   - **Gate del precio de Glue Flex: satisfecho** (el owner confirmó 0,29 USD/DPU-h en eu-west-3, 2026-11-20). Coste de la demo ≈ 0,20 USD.
   - executor añade `maintenance/`, `glue_jobs.tf` y actualiza `AGENTS.md`.
   - Verify (executor), un comando por llamada: `.venv/bin/python -m pytest spark/tests -q`, `.venv/bin/python -m ruff check spark generators`, `terraform fmt -check -recursive infra/terraform`, `terraform -chdir=infra/terraform/envs/dev init -backend=false`, `terraform -chdir=infra/terraform/envs/dev validate`, `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl`, `terraform -chdir=infra/terraform/envs/prod init -backend=false`, `terraform -chdir=infra/terraform/envs/prod validate`, `tflint --chdir=infra/terraform/envs/prod --config=$PWD/infra/terraform/.tflint.hcl`.
   - Owner: lanza a mano `skyroute-dev-silver-bookings_eur` (tras `skyroute-dev-bronze-ingest` y las dependencias) y compara en Athena `SELECT count(*), sum(amount_eur)` con el resultado local del mismo `run_date`. Éxito: valores idénticos; gasto de la demo visible en Cost Explorer < 0,50 USD.

## Testing Strategy

Contrato para `reppit-test`. Todos los tests Spark usan un catálogo Iceberg `hadoop` en `tmp_path` y ninguno toca AWS; las comparaciones "fila a fila" son `SELECT * ORDER BY <clave>` recogido en Python e igualado con `==`.

### Checks del proyecto

- C1. `.venv/bin/python -m pytest generators/tests -q` (venv Python 3.11, paso 0): todo en verde, incluidos los 23 tests existentes.
- C2. `.venv/bin/python -m pytest spark/tests -q`: todo en verde.
- C3. `.venv/bin/python -m ruff check spark generators`: sin errores.
- C4. `terraform fmt -check -recursive infra/terraform`: sin diferencias.
- C5. `terraform -chdir=infra/terraform/<root> validate` y `tflint --chdir=infra/terraform/<root> --config=$PWD/infra/terraform/.tflint.hcl` para `bootstrap`, `envs/dev`, `envs/prod` (tras `init -backend=false`): sin errores.
- C6. Los tests existentes no cambian salvo los que el nuevo modelo obliga: `git diff main -- generators/tests/test_determinism.py generators/tests/test_handler.py generators/tests/test_package.py generators/tests/test_verify_landing.py` vacío; cambios en `test_keys.py` solo si cambia `rows_for_day`, justificados en `test.md`.
- C7. checkov corre solo en CI (`static-checks`); el owner aporta su resultado.

### Unit Tests (generador)

- G1. Sesión con ≥ 2 eventos del mismo `customer_id` que acaba en `purchase` con el `booking_id` de una reserva del día.
- G2. Alguna reserva tiene ≥ 2 versiones con `updated_at` creciente.
- G3. Dos regeneraciones del mismo rango producen `bookings_history` idéntica, `history_id` incluido.
- G4. El export de D es idéntico byte a byte en dos ejecuciones y contiene varias versiones de una misma reserva si cambió dos veces en D.
- G5. Tardíos siguen ≤ 72 h y los duplicados no cruzan archivos (`clickstream.py:15`, `72-74`).
- G6. FX: respuesta vacía del BCE → error, ningún archivo escrito.

### Unit Tests (Spark)

- U1. Bronze: ejecutar D dos veces → tabla igual fila a fila; `_ingested_at` y `_batch_id` iguales.
- U2. Bronze: `--run-date` sin archivos → el job falla y la partición previa queda intacta.
- U3. Bronze: columnas técnicas derivadas de `run_date` y slot, nunca del reloj (test con dos ejecuciones en instantes distintos).
- U4. WAP: un check YAML que falla deja `main` sin cambios y la rama sin publicar.
- U5. SCD2: relanzar D → sin duplicados, una `is_current` por `booking_id`.
- U6. SCD2: ejecutar D, D+1 y relanzar D → la versión de D+1 sigue `is_current`; ninguna fila con `valid_to < valid_from`.
- U7. SCD2: dos versiones del mismo `booking_id` con el mismo `changed_at` → dos filas, desempate por `history_id`.
- U8. SCD2: D..D+5 y luego D → igual fila a fila que D..D+5 en orden.
- U9. `bookings_current`: D..D+5 y relanzar D → sigue la versión de D+5.
- U10. FX: sábado sin publicación → `fx_daily` del sábado = viernes.
- U11. FX: sin ningún tipo previo → check falla y no se publica.
- U12. `bookings_eur`: usa el tipo del día de `created_at`, guarda `fx_rate_applied` y `currency`; redondeo `HALF_EVEN` a 2 decimales.
- U13. `events`: duplicado exacto en un archivo → una fila; relanzar D+2 con un tardío de D no lo duplica y aparece en la partición de D.
- U14. `events`: `email` ausente, `email_hmac` = HMAC-SHA256 con la clave de test; consentimiento conservado.
- U15. Sesión: hueco de 31 min → 2 sesiones; de 29 min → 1.
- U16. Sesión: en un día generado, las sesiones derivadas de los eventos no tardíos coinciden con el `session_id` del generador (oráculo). Los tardíos se excluyen: el generador los desplaza hasta 72 h (`clickstream.py:36-41`) pero conserva su `session_id` (`clickstream.py:48`).
- U17. Idempotencia de sesiones: D, D+1, D otra vez → igual fila a fila que D, D+1; D, D+1, D, D+1 → igual que D, D+1.
- U18. Independencia del orden: D..D+5 y luego D → `events`, `sessions`, `bookings_scd2`, `bookings_current`, `fx_daily`, `bookings_eur` iguales fila a fila que D..D+5 en orden.
- U19. Sin sesiones huérfanas: un tardío que pasa a ser primer evento de una sesión → tras relanzar no queda la `session_key` antigua (`count` de sesiones por `customer_id` y ventana igual a la ejecución en orden).
- U20. Mantenimiento: `expire_snapshots` con `--run-date` fijo deja el mismo número de snapshots en dos ejecuciones y no cambia el contenido de la tabla.
- U21. WAP al relanzar: D, D+1 y relanzar D → el `fast_forward` del relanzamiento no falla, no queda rama `run_<D>` y Silver es igual fila a fila que D, D+1 en orden; con un check que falla, la rama queda y la siguiente ejecución de D la borra y publica.
- U22. Permutación de primera pasada: orden D+1, D, D+2 frente a D, D+1, D+2 → las seis tablas Silver iguales fila a fila.
- U23. Sesión que cruza medianoche hacia D-3: eventos a las 23:50 de D-4 y 00:10 de D-3 del mismo cliente; ejecutar D → una sola sesión con `session_start_date = D-4`, ninguna sesión nueva en D-3, igual a la ejecución en orden.

### Integration Tests (owner, Apply gate)

- I1. Plan de bootstrap pegado por el owner (Fase 1).
- I2. Plan de CI de la PR 2 sin `destroy` (Fase 2).
- I3. MFA: `aws sts get-caller-identity --profile skyroute-dev-local-data` devuelve el rol asumido (Fase 2).
- I4. Bronze: 182 `_ingest_date` por fuente antes de R + 30 (Fase 4).
- I5. Athena: una consulta que escanee > 100 MB se cancela por el corte del workgroup (o el owner muestra `bytes_scanned_cutoff_per_query` en `aws athena get-work-group`).
- I6. Demo Glue: `count(*)` y `sum(amount_eur)` iguales a local (Fase 8).

## Observability

### Logging
- Cada job registra `run_date`, fuente o tabla, filas leídas, filas escritas, snapshot publicado y resultado de checks; nunca payload ni email.

### Metrics
- Not applicable for this change (sin alarmas nuevas: las de `alarm.tf` cobran con carga mínima, T14).

## Security Considerations

- Rol `local-data` con MFA y sesión de 1 h; credenciales `AWS_*` temporales en el contenedor, nunca en archivos del repo.
- `s3:DeleteObject` del workload solo en `bronze/`, `silver/`, `athena-results/`, `glue-temp/`; nunca en `landing/`. ci-apply solo toca objetos en `scripts/`.
- PassRole solo a `skyroute-<env>-glue-job` con `iam:PassedToService = glue.amazonaws.com`.
- Clave HMAC con `value_wo` (fuera del state); `ci-plan` conserva `DenyDataObjectRead` salvo `scripts/*` y tiene Deny de `kms:Decrypt`; ningún rol de CI descifra (Design Decisions 11-12).
- Bronze conserva el email (Ruling "PII"); Silver solo el HMAC. Lake Formation aplazado.
- Bootstrap identity: el owner sigue siendo `skyroute-dev`; `local-data` es identidad no humana de mínimo privilegio.

## Rollout Strategy

1. Fases 1-2 en dev y prod por la CI (prod con aprobación).
2. Fase 3 desplegada solo en dev; el owner regenera el histórico de dev en la Fase 4.
3. Fases 4-8 contra dev (Ruling "Plan decisions").
4. Cierre de la fase: generador nuevo en prod, rol `local-data` de prod, regeneración de 182 días e ingesta Bronze antes de su R + 30.
5. Fase 8: demo Glue a mano en dev; sin schedule.
6. Cierre del ciclo: el orquestador mueve el plan a `current/` según `design-memory`.

## Owner gates (resumen)

| Gate | Momento | Evidencia | Estado |
|------|---------|-----------|--------|
| Re-aplicar bootstrap | Fin de Fase 1 | Plan del owner con state remoto | Pendiente |
| MFA con `aws login` | Fin de Fase 2, antes de Fase 4 | `aws sts get-caller-identity --profile skyroute-dev-local-data`; si falla, `aws sts get-session-token` con MFA; si las dos fallan, enmienda del Ruling | Pendiente |
| Precio Glue Flex eu-west-3 | Antes de Fase 8 | Confirmación del owner: 0,29 USD/DPU-h | **Satisfecho** (owner, 2026-11-20) |
| Tamaño de `ci-boundary` | Fase 1, antes del apply | `scripts/policy_size.py` ≤ 6.000 | Pendiente |
| Regeneración + Bronze de 182 días (dev) | Fase 4 | Fecha R y 182 `_ingest_date` por fuente antes de R + 30 | Pendiente |
| Regeneración + Bronze de 182 días (prod) | Cierre de la fase | Igual, con su R | Pendiente |
| Demo Glue | Fase 8 | Consulta Athena del owner | Pendiente |

## Decididas

Las 9 preguntas abiertas del primer borrador las cerró el owner aceptando cada recomendación (`context.md` § Rulings, "Plan decisions", javiladino, 2026-11-20 19:00):

1. `history_id`: `TRUNCATE … RESTART IDENTITY` y replay en orden determinista (Design Decision 10, test G3).
2. Clave HMAC: `ephemeral "random_password"` hacia `value_wo`, rotación con `value_wo_version` (Design Decision 8). Sigue sin comprobar la versión mínima de `hashicorp/random` con recursos efímeros; la Fase 2 la fija.
3. Histórico FX: `generators/fx/ecb.py --from --to` sobre la serie del BCE. Sin comprobar: URL y formato exactos de la serie.
4. Entorno: fases 4-8 en dev; prod al cerrar la fase (Fase 3, Fase 4, Rollout).
5. Lifecycle de `athena-results/` (y `glue-temp/`) en `modules/generator-landing/bucket.tf`.
6. Sesión: 30 min, `--session-gap-minutes`.
7. pytest en CI: `.github/workflows/spark-tests.yml`, Python 3.11, `permissions: {}`.
8. Sesiones con MERGE y `NOT MATCHED BY SOURCE DELETE` (Design Decision 5).
9. `amount_eur` con `HALF_EVEN` a 2 decimales.

## Open questions for the owner

1. **Python 3.11 en local.** El paso 0 necesita `python3.11`; hoy solo hay Homebrew 3.15. ¿Cómo se instala (Homebrew `python@3.11`, `uv`, pyenv)? Recomendación: `python@3.11` de Homebrew, sin herramienta nueva.
2. **Retención de `glue-temp/`.** Recomendación: 1 día (Technical Design); confirmar.

## Future Considerations

### Potential Enhancements
- MoR en `bookings_scd2` si crece el volumen; Lake Formation para PII; orquestación con Airflow (fase posterior).

### Known Limitations
- La igualdad con la ejecución en orden de `sessions` depende de que los tardíos no pasen de 72 h (`clickstream.py:15`).
- Paridad local/Glue media: solo la demo detecta deriva de versiones.
- Bronze genérico puede necesitar reescritura por fuente si cambian los esquemas (T5).

## Dependencies

### Development Dependencies
- `pyspark==3.5.4`, jars Iceberg 1.7.1 (`iceberg-spark-runtime-3.5_2.12`, `iceberg-aws-bundle`), Java 17, Python 3.11, `pytest`, `ruff`, `pyyaml`, `psycopg` (export). Versiones a reconfirmar contra la doc de Glue 5.0 en la Fase 4.

## References

- `docs/design/bronze-silver/working/research.md` (C1-C6, T1-T14).
- `docs/design/bronze-silver/working/proposal.md` (Base común, Proposal 2, Decision).
- `docs/design/bronze-silver/context.md` § Rulings, "Research decisions" y "Plan decisions".
- `docs/design/CONTEXT.md` § Conventions.
- Terraform AWS provider v6.73.0, `website/docs/r/ssm_parameter.html.markdown` (`value_wo`, `value_wo_version`): https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/website/docs/r/ssm_parameter.html.markdown
- AWS Glue 5.0 (Spark 3.5.4, Python 3.11, Iceberg 1.7.1): https://aws.amazon.com/blogs/big-data/introducing-aws-glue-5-0-for-apache-spark y https://docs.aws.amazon.com/glue/latest/dg/migrating-version-50.html
- Tarea: brief del orquestador para el Plan de la Proposal 2 (2026-11-20).
