---
type: Plan
---

# gold-dbt: Silver ampliado y Gold con dbt sobre Athena Design Document

> **Propuesta elegida:** Proposal 1 de `working/proposal.md` § Decision (owner javiladino, 2026-11-23): recrear Bronze y Silver con `rebuild_tables`, bloque A completo y después bloque B, con spike 0b de dbt-athena.
> **Rulings vinculantes:** `gold-dbt/context.md` § Rulings, "Research decisions" (con "Identidad de dbt" enmendada), "Bronze rebuild exception (2026-11-23)" (enmendada) y "Plan decisions (2026-11-23)".
> **Conventions citadas:** Compute split, Table format, Medallion layers, Idempotency, Apply gate, IaC only, No hourly-billed resources, Region, Git workflow, Simple shell commands, Bootstrap identity (`docs/design/CONTEXT.md` § Conventions).
> **Revisión:** corregido tras adversarial-reviewer (NEEDS-REVISION), security-reviewer y cost-guard (2026-11-23); segunda ronda adversarial (NEEDS-REVISION), hallazgos H1-H8 aplicados (2026-11-23).

## Current Context

- Silver tiene seis tablas Iceberg creadas por Spark con `CREATE TABLE IF NOT EXISTS` y sin `ALTER` (`bookings_scd2.py:45`, `bookings_current.py:30`, `bookings_eur.py:43`, `events.py:51`, `sessions.py:63`, `fx_daily.py:38`); ninguna está en Terraform (proposal, C4).
- El generador no emite gasto ni canal, cada reserva tiene una sola campaña heredada por su recorrido (`model.py:80`, `:94`, `:154`), la ruta existe pero no se exporta (`model.py:107`; `export_bookings.py:28-31`) y no hay `travel_date`, `product_view` ni `begin_checkout` (`model.py:35`).
- Los `event_id` son deterministas por (`run_date`, slot, `n`) (`keys.py:40`): regenerar con contenido distinto aborta `silver.events` (`events.py:185-190`), de ahí la Ruling "Bronze rebuild exception".
- No existe base `skyroute_<env>_gold` (`glue_catalog.tf:2`, `:9`), ni `gold/` en las boundaries (`workload_boundary_dev.tf:13-54`, ídem prod), ni dbt en el repo o en CI (`requirements-dev.txt:1-5`, `.github/workflows/`).
- La boundary y los roles de CI fijan Athena a un único workgroup `skyroute-<env>` (`ci_roles.tf:34`; `workload_boundary_dev.tf:81`; `ci_apply_dev.tf:122`; `ci_apply_prod.tf:122`; `ci_roles.tf:632`): un workgroup propio de dbt también exige cambio de `bootstrap/`. En `ci_apply_*.tf:122` el recurso es un string único; `ci_roles.tf:21` y `:311` ya cubren el workgroup `-dbt` y el rol nuevo para CI (verificado por adversarial-reviewer).
- `glue_catalog_resources` (`iam.tf:52-56`) es un comodín `skyroute_<env>_*` compartido por `glue-job` y `local-data`, y `common_statements` (`iam.tf:60-106`) incluye `ssm:GetParameter` y `kms:Decrypt` del parámetro `hmac-email-key`; `envs/prod/main.tf:17` fija `create_local_data_role = false`.

## Requirements

### Functional Requirements

- F1. El glosario de KPIs coincide con el SQL: ROAS, CAC, funnel de cinco pasos, RFM y atribución last-click, linear y 40/20/40 (`context.md:8`).
- F2. Gasto diario por campaña de `landing/ad_spend/` a Bronze y a Silver `ad_spend_daily` con Spark, como `fx` (Ruling "Gasto publicitario y canal"; Compute split). Canal y `start_date` en el seed dbt `campaigns.csv`.
- F3. Recorridos de 1 a 4 touchpoints con campaña propia, la última igual a la de la reserva, emitidos en el día lógico de su sesión (D-6..D) (Ruling "Recorridos multi-campaña").
- F4. `origin`, `destination`, `travel_date` en Postgres, `bookings_history`, `landing/`, Bronze y las tres tablas Silver de reservas (Ruling "Ruta y fecha de viaje").
- F5. Eventos `product_view` y `begin_checkout`, secuencia `search` → `product_view` → `add_to_cart` → `begin_checkout` → `purchase` con abandono determinista (Ruling "Funnel").
- F6. Cada job Silver falla con `schema_mismatch` si su tabla existe sin una columna del DDL.
- F7. `rebuild_tables` borra solo la lista cerrada de tablas Bronze y Silver del `--env` dado; comprueba con `sts:GetCallerIdentity` que el rol es `skyroute-<env>-local-data` del mismo `--env`, imprime la lista, exige escribir el nombre del entorno, tiene `--dry-run` y rechaza `--env prod` sin `--confirm-prod` (Rulings "Bronze rebuild exception" y "Plan decisions").
- F8. Un único backfill del histórico desde `run_date` = inicio-6, con un solo commit del generador, ejecutado en Spark local (Ruling "un único cambio y un único backfill"; Ruling "Plan decisions"; Compute split).
- F9. Proyecto dbt: staging, `dim_*`, `fct_*`, `mart_attribution`, `mart_roas_daily`, `mart_cac_monthly`, `mart_funnel`, `mart_customer_rfm`, tests, contratos ODCS, exposures y docs; sesión = `sessions.session_key`, ventana D-4..D en sesión y D-7..D en atribución (Ruling "Sesión en Gold"; Idempotency).
- F10. CI `dbt-ci.yml` con solo `dbt deps`, `dbt parse`, `dbt ls` y lint, sin AWS (Ruling "dbt en CI").
- F11. Infra de Gold en dev y prod; `dbt build` en prod solo al cierre (Ruling "Prod").

### Non-Functional Requirements

- Idempotency: relanzar la misma fecha lógica da los mismos bytes en el generador y las mismas filas en Silver y Gold; nada usa `now()`, la fecha llega por `--run-date` o `var("run_date")`.
- Coste: cada consulta por debajo del corte de 100 MB (`athena.tf:14`), forzado en el workgroup de dbt con `enforce_workgroup_configuration = true`; el gasto total dentro del budget de 10 USD (`bootstrap/budget.tf:4`), medido por el owner en Cost Explorer. Estimación de cost-guard: backfill en Glue 20-60 USD (unas 2.070 ejecuciones con mínimo de 1 min a 0,29 USD/DPU-h), por eso el backfill va en Spark local (0 USD de cómputo); `dbt build` por debajo de 0,2 USD en total. Tope de alarma de 1 USD para dev.
- No hourly-billed resources: dbt corre en la máquina del owner contra Athena serverless; los Glue jobs nuevos son Flex sin trigger, como los de `glue_jobs.tf:1-5`, y solo se lanzan para un día de demo.
- Region: todo en `eu-west-3`.
- Seguridad: rol `skyroute-<env>-local-dbt` con la misma trust con MFA de `local-data` y sesión de 1 h, dentro de la boundary del entorno, con política propia sin `common_statements` (Security Considerations).

## Design Decisions

### 1. Recrear Bronze y Silver, no versionar ni `ALTER`
Se implementa `rebuild_tables` (DROP ... PURGE de lista cerrada) seguido de un único reproceso, porque:
- Los ids deterministas (`keys.py:40`) hacen que `ALTER TABLE ADD COLUMNS` no resuelva los conflictos (`events.py:185-190`) ni las versiones espurias de `bookings_scd2`.
- La excepción está aprobada una vez en dev y una en prod (Ruling "Bronze rebuild exception"); Medallion layers e Idempotency siguen en vigor para todo lo demás.
- Alternativa descartada por el owner: Silver `_v2` (Proposal 2).

### 2. `rebuild_tables` en local con `skyroute-<env>-local-data`
En dev, sin cambios de IAM: la boundary ya concede `glue:DeleteTable` (`workload_boundary_dev.tf:63`) y `s3:DeleteObject` en `bronze/*`, `silver/*` (`:45-53`), y `local-data` ya lleva `GlueCatalogDeleteTable` (`iam.tf:110-116`); el rol `glue-job` no borra tablas por diseño. En prod sí hay cambio de IAM, temporal (Ruling "Plan decisions"): `envs/prod/main.tf:17` fija `create_local_data_role = false`, así que la fase 7 abre una PR que lo pone a `true` y, tras el rebuild, otra que lo devuelve a `false`; las dos las aplica CI (IaC only, Apply gate) y la segunda deja evidencia de que el rol `skyroute-prod-local-data` ya no existe. IaC only no choca con el DROP: ninguna tabla está en Terraform (proposal C4). Salvaguardas de `rebuild_tables` (Idempotency, Ruling "Bronze rebuild exception"): `sts:GetCallerIdentity` debe devolver `skyroute-<env>-local-data` del mismo `--env`, imprime la lista cerrada, exige teclear el nombre del entorno, `--dry-run` no borra nada y `--confirm-prod` sigue siendo obligatorio en prod. Alternativa descartada: dar `DeleteTable` a `ci-apply-prod` o a `glue-job`.

### 3. Guard `schema_mismatch` en un helper común
Un helper nuevo en `spark/lib/` compara las columnas de la tabla existente con las del DDL y falla antes de escribir. Se llama desde los siete jobs Silver tras su `CREATE TABLE IF NOT EXISTS`. Alternativa: lógica en cada job (duplicada).

### 4. Gasto: módulo del generador, publicado como fuente diaria
`ad_spend` es una fuente diaria como `bookings` y `fx` (`keys.py:10-11`, `daily_key` en `keys.py:56`): un módulo `ota/ad_spend.py` determinista por fecha lógica que escribe `landing/ad_spend/ingest_date=D/part.json.gz`, subido por el owner con `local-data` (que ya tiene `LandingWrite`, `iam.tf:227-232`). La Key Changes de P1 menciona "+ Lambda"; por Ruling "Plan decisions" el gasto es fuente diaria local y no se toca `lambda_handler.py` (`:67-106` solo escribe clickstream por slot). Bronze lo ingiere con `SOURCES` ampliado (`ingest.py:27`) y Silver `ad_spend_daily` con clave (`spend_date`, `campaign_id`), partición por día, como `fx_daily` (Compute split, Table format).

### 5. Touchpoints emitidos en el día lógico de su sesión
El generador del día X emite las sesiones de reservas de X..X+6 cuya sesión cae en X, derivadas de la semilla de la fecha de la reserva; `event_id` sigue siendo (`run_date`=X, slot, `n`) con un rango de `n` reservado para touchpoints, así que no cambia `keys.py`. Rango reservado (H8): hoy es `2000 + j*10 + n` (`clickstream.py:78`), y con 1-4 sesiones de hasta 5 pasos `n` llega a 20 y colisiona con el recorrido `j+1`. Pasa a `2000 + j*100 + n` con `0 <= n < 100`; el generador falla (`ValueError`) si un recorrido supera 99 pasos. Fondo usa `0..total-1` (< 1000 porque `total <= 45`) y purchase `1000 + j`; se fija que `bookings_for_slot` da menos de 1000 reservas por slot. La última sesión (día D) lleva la campaña de la reserva; las anteriores, campaña propia. Se recomienda un umbral de multi-campaña de 30 % (Open question 1).

Navegación de fondo (A6, corregido por H1): hoy `clickstream.py:50` emite eventos de fondo con tipos de `EVENT_TYPES` (`model.py:35`: `page_view`, `search`, `add_to_cart`, `consent`), incluido `add_to_cart` suelto, y solo los `consent` de fondo llevan `email` (`clickstream.py:69-70`). De ese `email` salen `email_hmac` y `consent_ts` de `silver.events` (`events.py:61`, `:140-141`), de los que dependen el RFM y la Ruling "CRM y bajas". Se fija una lista nueva y explícita `BACKGROUND_EVENT_TYPES = ["page_view", "search", "product_view", "consent"]` (con sus pesos `BACKGROUND_EVENT_WEIGHTS`) que usa solo la navegación de fondo; excluye `add_to_cart`, `begin_checkout` y `purchase`, que solo salen de sesiones de recorrido, en orden y con abandono determinista. `EVENT_TYPES` pasa a ser el catálogo completo de tipos admitidos (los de fondo más los del recorrido) y ya no lo usa `clickstream.py:50`, así que ampliarlo no reintroduce pasos de funnel en el fondo. Los `consent` de fondo siguen llevando `email`. Así el funnel no se infla con pasos sueltos. El test 2d se evalúa en dos niveles: sobre las sesiones del generador (unit test, agrupando por la sesión que emite el generador) y, en Gold, sobre `sessions.session_key` de Silver (test singular dbt `funnel_order_per_session`), que es la sesión de la Ruling "Sesión en Gold".

### 6. Backfill desde inicio-6 y recuento esperado desde el generador
Recomendación de la proposal (P1-5): arrancar en inicio-6 para que ninguna reserva desde inicio tenga recorrido truncado. El total esperado de eventos de la Validation 4b sale de un recuento local del generador con el mismo commit (un test o CLI de recuento, sin `aws s3 cp` ni `wc -l`), porque es un solo comando y no depende de que `landing/` siga vivo (Simple shell commands).

### 7. Materialización dbt: pre_hook `DELETE` + `merge`
Todo incremental fija `table_type='iceberg'` e `incremental_strategy='merge'` (el default `insert_overwrite` no vale con Iceberg), con `unique_key`, `incremental_predicates` y un pre_hook `DELETE` de la ventana dentro de `{% if is_incremental() %}` (proposal, "Borrado de la ventana"). `mart_cac_monthly` y `mart_customer_rfm` se materializan como `table` completa (resuelve el "a fijar en Plan" de la proposal: son pequeñas y así no hay ventana que borrar). Staging como `view`; `dim_campaign` y `dim_date` como `table`. Lo valida el spike 0b; `microbatch` solo si el spike demuestra que reemplaza el lote entero.

### 8. Workgroup propio `skyroute-<env>-dbt` con el mismo corte (C1)
Cerrada por Ruling "Plan decisions" (enmienda "Identidad de dbt"): workgroup `skyroute-<env>-dbt` con `bytes_scanned_cutoff_per_query` de 100 MB y `enforce_workgroup_configuration = true` copiados de `athena.tf`, y `local-dbt` solo con Athena sobre ese ARN. Separa `ProcessedBytes` de dbt. Consecuencia: la boundary y los roles de CI fijan el ARN del workgroup `skyroute-<env>` (`ci_roles.tf:34`), así que la PR 0a añade el ARN del workgroup de dbt en las boundaries, convierte en lista el string único de `ci_apply_dev.tf:122` y `ci_apply_prod.tf:122`, y amplía `ci_roles.tf:632` (Bootstrap identity: `bootstrap/` lo aplica el owner).

### 9. Lint SQL de CI: sqlfluff con dialecto athena y templater jinja
Pregunta abierta en la proposal; se elige sqlfluff porque tiene dialecto `athena`. Para no necesitar AWS en CI se usa el templater `jinja` (no el `dbt`, que compila contra el adapter), en `.sqlfluff` y en `dbt-ci.yml`. Alternativa: sin lint SQL, solo `dbt parse`.

### 10. Una PR por fase (Git workflow)
Rama por PR desde `main`; ningún agente hace commit ni push sin que el owner lo pida. 0a se aplica por el owner antes de fusionar 0b (Apply gate, Bootstrap identity); 0b la aplica CI y su apply es gate de 0c. El spike 0c vive en una rama y no se fusiona hasta la fase 5. Solo la PR de la fase 5 toca `requirements-dev.txt`; las versiones de dbt se fijan en un único sitio (Dependencies).

### 11. Backfill en Spark local, Glue solo para un día de demo
Ruling "Plan decisions" y Ruling de la Fase 3 (local a diario, Glue en demos); Compute split y No hourly-billed resources. cost-guard estimó el backfill en Glue en 20-60 USD frente a un budget de 10 USD; en local el cómputo cuesta 0 USD y en AWS solo quedan S3 y Glue Catalog. Glue se lanza para un único día de demo, y dev tiene un tope de alarma de 1 USD (O12). Alternativa descartada: backfill en Glue Flex.

### 12. `local-dbt` con política mínima propia
Hallazgos S1-S3 de security-reviewer. La inline de `local-dbt` no usa `common_statements` ni `glue_catalog_resources` (que no se tocan) y solo lleva: `BucketList`; S3 de `s3_prefixes.local_dbt`; Glue `Get*` sobre `catalog`, `database/skyroute_<env>_silver` y `table/skyroute_<env>_silver/*`; Glue `Get*`, `CreateTable`, `UpdateTable` y `DeleteTable` sobre `database/skyroute_<env>_gold` y `table/skyroute_<env>_gold/*` (dbt-athena borra y recrea en `table` y `--full-refresh`); Athena sobre el ARN `-dbt`; y un `Deny` explícito de `s3:PutObject` y `s3:DeleteObject` en `landing/*`, `bronze/*`, `silver/*` y de `glue:Create*`, `glue:Update*`, `glue:Delete*` sobre las bases y tablas bronze y silver, porque la boundary no lo impide (`workload_boundary_dev.tf:45-70`). Así no hereda `ssm:GetParameter` ni `kms:Decrypt` de `hmac-email-key`. Trust: la misma con MFA de `local-data`, sin relajarla (S6). Las acciones que falten las documenta el spike 0c (S5).

## Technical Design

### 1. Core Components

- `ota/ad_spend.py`: gasto diario por campaña, `generate(run_date) -> bytes` (JSON lines gzip, `mtime=0`), y CLI `--run-date`, `--out-dir` como `export_bookings.py`.
- `ota/model.py`: recorridos multi-campaña, `origin`/`destination`/`travel_date` en la reserva, funnel ordenado con abandono determinista.
- `spark/jobs/silver/ad_spend_daily.py`: Silver de gasto, WAP con `spark/checks/ad_spend_daily.yaml`.
- `spark/lib/schema_guard.py`: `require_columns(spark, table, ddl_columns)`; lanza `SchemaMismatch` (mensaje con `schema_mismatch` y las columnas que faltan).
- `spark/jobs/maintenance/rebuild_tables.py`: `--env` obligatorio, `--confirm-prod`, `--dry-run`, comprobación `sts:GetCallerIdentity` (rol `skyroute-<env>-local-data` del mismo `--env`), confirmación tecleando el nombre del entorno, lista cerrada `bronze.{clickstream,bookings,fx,ad_spend}` y `silver.{bookings_scd2,bookings_current,fx_daily,bookings_eur,events,sessions,ad_spend_daily}`; sale con error si `--env prod` sin `--confirm-prod`; registra cada DROP.
- `dbt/`: proyecto `skyroute` con perfil `athena` (`profiles.yml.example` y perfil ficticio de CI), sources sobre `skyroute_<env>_silver`, salida en `skyroute_<env>_gold`, workgroup `skyroute-<env>-dbt`, `s3_data_dir` en `gold/`.

### 2. Data Models

- Landing `ad_spend`: `spend_date` (date), `campaign_id` (string), `spend` (decimal 10,2), `currency` (string, EUR), `impressions` (int), `clicks` (int).
- Silver `ad_spend_daily`: las columnas de landing más las técnicas (`spark/lib/technical_columns.py:15`); clave (`spend_date`, `campaign_id`); `PARTITIONED BY (spend_date)` como `fx_daily`.
- Reservas: `origin` string, `destination` string, `travel_date` date, en `bookings` y `bookings_history` de Postgres, en `FIELDS` del export, en `BOOKINGS_SCHEMA` de Bronze y en los DDL de `bookings_scd2`, `bookings_current`, `bookings_eur` (y en `HASH_COLUMNS` de `bookings_scd2.py:39-42`).
- `events.event_type`: valores nuevos `product_view` y `begin_checkout`; sin columna nueva.
- Seed `dbt/seeds/campaigns.csv`: `campaign_id`, `campaign_name`, `channel`, `start_date` (ocho campañas, `model.py:29-32`).
- `dim_customer` (S9, H3): Silver no tiene tabla de clientes ni columnas `marketing_consent` o `country`; solo `consent_ts` y `email_hmac` en `events` (`events.py:60-61`). Columnas exactas: `customer_id` (string, clave), `first_booking_date` (date, mínimo `created_at` de `stg_bookings_current`), `first_seen_date` (date, mínimo `event_ts` de `stg_events`), `consent_ts` (timestamp, el del último evento `consent` del cliente con `event_ts` hasta el final de `var("run_date")`, desempate por `event_id`), `marketing_consent` (boolean, `consent_ts IS NOT NULL AND consent_ts <= var("run_date")` sobre ese último evento `consent`; `false` si el cliente no tiene ningún `consent` hasta la fecha lógica). Sin `country` ni ninguna columna derivada del email. Determinista por `var("run_date")` (Idempotency); Compute split: es modelado sobre Silver, sin lógica nueva en Spark.
- `stg_events` (H3): lista explícita de columnas, sin `select *`, que excluye `email_hmac`; ningún modelo Gold lee `email_hmac`. Test singular `no_email_columns_in_gold`: `SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = '{{ target.schema }}' AND lower(column_name) LIKE '%email%'`; falla con una fila o más.
- Gold: `dim_customer`, `dim_campaign`, `dim_date`, `fct_bookings`, `fct_sessions` (`session_key`, `session_start_date`), `fct_touchpoints` (`session_key`, `booking_id`, `touch_seq`, `campaign_id`), `mart_attribution` (`booking_id`, `model`, `touch_seq`, `campaign_id`, `attributed_revenue`, `booking_date`), `mart_roas_daily` (`campaign_id`, `spend_date`, `spend`, `attributed_revenue`, `roas`), `mart_cac_monthly`, `mart_funnel`, `mart_customer_rfm`.

### 3. Integration Points

```
generador (model, clickstream, export_bookings, ad_spend)
   -> landing/{clickstream,bookings,fx,ad_spend}/
   -> Bronze ingest (Spark)  -> skyroute_<env>_bronze.*
   -> Silver jobs (Spark, WAP, schema_guard) -> skyroute_<env>_silver.*
   -> dbt-athena (owner en local, rol local-dbt, workgroup skyroute-<env>-dbt)
   -> skyroute_<env>_gold.* (Iceberg en gold/)
```

Compute split: gasto, ruta y funnel se calculan en Spark; dbt solo modela sobre Silver.

### 4. Files Changed

Líneas verificadas contra el código el 2026-11-23 (inicio de cada bloque verificado con Grep o Read; el final de los bloques DDL de Silver y de selección de columnas es aproximado y lo fija el executor al leer el archivo). Agrupadas por fase.

**Fase 0a, PR `bootstrap/` (owner aplica, Apply gate)**
- `infra/terraform/bootstrap/workload_boundary_dev.tf` (lines 13-23: `gold/*` en `AllowLakehouseWrite`; lines 26-37: `gold/*` en `AllowLakehouseRead`; lines 45-54: `gold/*` en `AllowLakehouseDelete`; lines 72-82: ARN del workgroup `skyroute-dev-dbt` junto al de `skyroute-dev`). `AllowGlueCatalog` (lines 56-70) ya cubre `skyroute_dev_*`: sin cambio.
- `infra/terraform/bootstrap/workload_boundary_prod.tf` (mismas líneas 13-23, 26-37, 45-54, 72-82 para prod).
- `infra/terraform/bootstrap/ci_roles.tf` (line 34: añadir `athena_workgroup_dbt` a `env_arns`; line 632: incluir los workgroups de dbt de dev y prod). Las líneas 31-32 ya cubren `skyroute_<env>_gold` en Glue: sin cambio.
- `infra/terraform/bootstrap/ci_apply_dev.tf` (line 122: el string único pasa a lista con el ARN de `skyroute-dev` y el de `skyroute-dev-dbt`).
- `infra/terraform/bootstrap/ci_apply_prod.tf` (line 122: ídem con `skyroute-prod-dbt`).
- Sin cambio: `ci_roles.tf:21` y `:311` ya cubren el workgroup `-dbt` y el rol nuevo para CI.

**Fase 0b, PR módulo `lakehouse` (CI aplica, IaC only)**
- `infra/terraform/modules/lakehouse/glue_catalog.tf` (lines 1-2: quitar el comentario "gold queda fuera"; line 9: añadir `gold` a `databases`).
- `infra/terraform/modules/lakehouse/athena.tf` (lines 1-24: nuevo `aws_athena_workgroup` `dbt` con nombre `${local.name_prefix}-dbt`, mismo `bytes_scanned_cutoff_per_query` de 100 MB, `enforce_workgroup_configuration = true`, métricas en CloudWatch y resultados en `athena-results/`).
- `infra/terraform/modules/lakehouse/iam.tf` (lines 14-27: entrada `local_dbt` en `s3_prefixes` con read `silver`, `gold`, `athena-results`; write y delete `gold`, `athena-results`; lines 52-56 (`glue_catalog_resources`) y 60-106 (`common_statements`): sin cambio; nuevo local `local_dbt_statements` con los statements de la Design Decision 12 (BucketList, S3, `GlueSilverRead`, `GlueGoldWrite`, `AthenaDbtWorkgroup`, `DenyUpstreamWrite`); lines 185-236: nuevos `aws_iam_role` y `aws_iam_role_policy` `local_dbt`, con la misma trust con MFA de `local_data`). Sin `glue:CreateDatabase` (la base la crea Terraform).
- `infra/terraform/modules/lakehouse/variables.tf` (line 16: nueva variable `create_local_dbt_role`, junto a `create_local_data_role`).
- `infra/terraform/modules/lakehouse/outputs.tf` (lines 1-27: outputs del workgroup de dbt y del ARN de `local-dbt`).
- `infra/terraform/envs/dev/main.tf` (line 14: `create_local_dbt_role = true`).
- `infra/terraform/envs/prod/main.tf` (line 17: `create_local_dbt_role = true`, Ruling "Prod": infra en los dos entornos).

**Fase 0c, spike dbt-athena (rama, no se fusiona hasta la fase 5)**
- `dbt/dbt_project.yml` (NEW: proyecto mínimo).
- `dbt/profiles.yml.example` (NEW: perfil `athena`, `eu-west-3`, sin credenciales; target `dev` con workgroup `skyroute-dev-dbt` y schema `skyroute_dev_gold`; target `prod` con workgroup `skyroute-prod-dbt` y schema `skyroute_prod_gold`, H5).
- `dbt/ci/profiles.yml` (NEW: perfil ficticio sin credenciales; aquí porque el Verify de 0c es su primer uso, H7).
- `dbt/models/staging/_sources.yml` (NEW: source `silver.sessions`).
- `dbt/models/spike/spike_sessions_window.sql` (NEW: incremental `merge` con pre_hook `DELETE` D-4..D e `incremental_predicates`).
- `dbt/tests/window_matches_silver.sql` (NEW: test singular de la Validation 6b).
- `dbt/SPIKE.md` (NEW, solo en la rama: lista exacta de acciones de Athena y Glue que falten, p. ej. `athena:ListDataCatalogs`, `athena:GetDataCatalog`, `athena:ListWorkGroups`, `glue:BatchCreatePartition`, `glue:BatchDeleteTable`, cada una con su recurso acotado; nunca `athena:*` ni `Resource="*"`. Si alguna hace falta en la boundary, va en una PR nueva de `bootstrap/`, Bootstrap identity; si solo falta en la inline, en una PR del módulo). Se borra al limpiar el spike en la fase 5.
- `requirements-dev.txt` (lines 1-5: `dbt-core` y `dbt-athena==1.11.2`, único sitio donde se fijan). El cambio vive en la rama del spike y entra en `main` solo con la PR de la fase 5, que absorbe el spike; ninguna otra PR toca este archivo (A10).

**Fase 1, PR generador**
- `docker/postgres/init/001_bookings.sql` (lines 1-11: `origin`, `destination`, `travel_date`).
- `docker/postgres/init/002_bookings_history.sql` (lines 5-20: columnas nuevas; lines 22-28 en adelante: el trigger las copia).
- `generators/ota/model.py` (line 35-36: `EVENT_TYPES` pasa a catálogo completo con `product_view` y `begin_checkout`; nuevas `BACKGROUND_EVENT_TYPES = ["page_view", "search", "product_view", "consent"]` y `BACKGROUND_EVENT_WEIGHTS`, Design Decision 5, H1; lines 71-111: `origin`, `destination` y `travel_date` deterministas en la reserva, `route` deja de ser el único campo; lines 126-162: `customer_journeys` pasa a 1-4 touchpoints en sesiones de días D-6..D, cada uno con campaña propia y el último con la de la reserva, funnel ordenado con abandono; lines 173-174: `journeys_for_slot` devuelve las sesiones cuyo día lógico de emisión es `run_date`, de reservas de `run_date`..`run_date`+6).
- `generators/ota/clickstream.py` (line 50: la navegación de fondo elige de `BACKGROUND_EVENT_TYPES`, no de `EVENT_TYPES`; lines 69-70 sin cambio: los `consent` de fondo siguen con `email`; Design Decision 5, H1; line 78: `event_id` de touchpoints `2000 + j*100 + n` con `n < 100`, H8).
- `generators/ota/export_bookings.py` (lines 28-31: `origin`, `destination`, `travel_date` en `FIELDS`).
- `generators/ota/seed_postgres.py` (lines 19-22: columnas nuevas en `COLUMNS`).
- `generators/ota/keys.py` (lines 9-11: `AD_SPEND_PREFIX = "landing/ad_spend"`).
- `generators/ota/ad_spend.py` (NEW: gasto diario por campaña y CLI).
- `generators/tests/test_determinism.py`, `generators/tests/test_sessions.py`, `generators/tests/test_export_bookings.py` (ampliar con los tests 2a-2e de Testing Strategy).
- `generators/tests/test_ad_spend.py` (NEW).
- `generators/tests/test_backfill_counts.py` (NEW: recuento esperado de eventos por rango, Validation 4b).

**Fase 2, PR Spark (jobs, DDL, guard) + Glue jobs**
- `spark/lib/schemas.py` (lines 37-50: `BOOKINGS_SCHEMA` con las tres columnas; lines 51-62: nuevo `AD_SPEND_SCHEMA` y entrada en `SCHEMAS`).
- `spark/jobs/bronze/ingest.py` (line 27: `ad_spend` en `SOURCES`).
- `spark/lib/schema_guard.py` (NEW: guard `schema_mismatch`).
- `spark/jobs/silver/bookings_scd2.py` (lines 39-42: `HASH_COLUMNS`; lines 45-60: DDL; lines 85-140: selección de columnas; line 202 en adelante: llamada al guard).
- `spark/jobs/silver/bookings_current.py` (lines 30-45: DDL; lines 60-70: selección; line 100 en adelante: guard).
- `spark/jobs/silver/bookings_eur.py` (lines 43-58: DDL; line 115 en adelante: selección y guard).
- `spark/jobs/silver/events.py` (lines 51-65: DDL sin columnas nuevas; lines 130-140: los tipos nuevos pasan; line 202 en adelante: guard).
- `spark/jobs/silver/sessions.py` (line 63: DDL; line 280 en adelante: guard). `fx_daily.py` (line 38; line 90 en adelante: guard).
- `spark/jobs/silver/ad_spend_daily.py` (NEW).
- `spark/checks/ad_spend_daily.yaml` (NEW: reglas WAP: clave única, `spend >= 0`, campaña conocida).
- `spark/checks/bookings_*.yaml`, `spark/checks/events.yaml` (reglas de no nulos y `travel_date >= created_at`; `event_type` admitido).
- `spark/tests/test_silver_ad_spend.py`, `spark/tests/test_schema_guard.py` (NEW), y `spark/tests/test_bronze_ingest.py`, `test_bookings_scd2.py`, `test_bookings_current.py`, `test_silver_events.py` (ampliar).
- `infra/terraform/modules/lakehouse/glue_jobs.tf` (line 21: `ad_spend_daily` en `silver_tables`; el job Bronze ya acepta `--source`).

**Fase 3, PR `rebuild_tables` y runbook**
- `spark/jobs/maintenance/rebuild_tables.py` (NEW).
- `spark/tests/test_rebuild_tables.py` (NEW).
- `docs/runbooks/gold-dbt-backfill.md` (NEW: orden del backfill en Spark local, commit único, plazo de 30 días de `landing/`, día de demo en Glue, tope de 1 USD, Cost Explorer; antes de la fase 7, confirmación de que el histórico de prod se puede regenerar desde el generador; PRs de alta y baja de `local-data` en prod; paso de la fase 7 sobre la Lambda de prod, H6: `envs/prod/main.tf:5` fija `schedule_enabled = true`, así que la Lambda sigue escribiendo `landing/clickstream` durante la regeneración, y el módulo del generador es compartido, así que cualquier apply despliega el código nuevo en la Lambda de prod (caso PR #28, Ruling de `bronze-silver`); el merge de la fase 1 ya desplegará el generador nuevo en prod. El runbook pide una de dos: (a) pausar el schedule por IaC con una PR `schedule_enabled = false` aplicada por CI antes de regenerar y otra que lo devuelve a `true` al terminar (IaC only, Apply gate; nunca desde la consola), o (b) confirmar que el código desplegado es el del commit del backfill comparando `aws lambda get-function --function-name <lambda-prod> --query Configuration.CodeSha256 --region eu-west-3` con el `CodeSha256` del plan o apply de CI de ese commit, un comando por paso (Simple shell commands). Recomendación: (a), porque además evita que la Lambda escriba slots mientras se regenera).

**Fase 5, PR proyecto dbt**
- `dbt/` completo (NEW): `models/staging/stg_*.sql` (siete sources), `models/intermediate/int_touchpoints.sql`, `models/marts/{dim_customer,dim_campaign,dim_date,fct_bookings,fct_sessions,fct_touchpoints,mart_attribution,mart_roas_daily,mart_cac_monthly,mart_funnel,mart_customer_rfm}.sql`, `models/**/_*.yml` (tests genéricos, contratos `enforced`, docs), `models/exposures.yml` (una exposure por KPI del glosario: `kpi_roas`, `kpi_cac`, `kpi_funnel`, `kpi_rfm`, `kpi_attribution_last_click`, `kpi_attribution_linear`, `kpi_attribution_40_20_40`), `seeds/campaigns.csv`, `tests/` (singulares, incluidos `kpi_roas_formula`, `kpi_cac_formula`, `funnel_order_per_session`, `no_email_columns_in_gold`), `.sqlfluff` (dialecto `athena`, templater `jinja`), `analyses/gold_fingerprint.sql`, `macros/window_bounds.sql`, `packages.yml`.
- `contracts/*.yaml` (NEW: ODCS de los marts).

**Fase 6, PR CI**
- `.github/workflows/dbt-ci.yml` (NEW: `pip install`, `dbt deps`, `dbt parse`, `dbt ls`, `sqlfluff lint --dialect athena --templater jinja dbt/models` con perfil ficticio, sin OIDC).

**Fase 7, PRs de prod (CI aplica, IaC only)**
- 7a: `infra/terraform/envs/prod/main.tf` (line 17: `create_local_data_role = true`).
- 7b: `infra/terraform/envs/prod/main.tf` (line 17: vuelve a `create_local_data_role = false`).
- 7-pausa y 7-reanudación (H6), solo si se elige pausar: `infra/terraform/envs/prod/main.tf` (line 5: `schedule_enabled = false` antes de regenerar y `true` al terminar), cada una en su PR aplicada por CI.
- `.github/workflows/spark-tests.yml`: sin cambio (ya corre `pytest generators spark`, lines 54-58).

## Implementation Plan

Orden por dependencias. Cada fase es una PR (Git workflow) salvo 0c (rama de spike) y 4 (operación del owner). Los comandos son simples, uno por paso (Simple shell commands). **[owner]** marca los pasos que solo ejecuta el owner (Apply gate).

0a. **PR `bootstrap/`: boundaries y CI con `gold/` y el workgroup de dbt.**
   - Cambios de Files Changed, fase 0a.
   - Verify, un comando por paso:
     1. `terraform fmt -check -recursive infra/terraform`
     2. `terraform -chdir=infra/terraform/bootstrap init -backend=false`
     3. `terraform -chdir=infra/terraform/bootstrap validate`
     4. `tflint --init --config=infra/terraform/.tflint.hcl`
     5. `tflint --chdir=infra/terraform/bootstrap --config=$PWD/infra/terraform/.tflint.hcl`
   - **[owner]** `terraform -chdir=infra/terraform/bootstrap plan` y después `terraform -chdir=infra/terraform/bootstrap apply`; la salida se adjunta a la PR como evidencia (Apply gate, Bootstrap identity). Va primero porque los roles de 0b se crean con `permissions_boundary` y CI no puede crear el workgroup de dbt sin el permiso nuevo.

0b. **PR módulo `lakehouse`: base gold, workgroup y rol `local-dbt`.**
   - Cambios de Files Changed, fase 0b. **Gate:** no se fusiona sin la evidencia del apply de 0a.
   - Verify, un comando por paso:
     1. `terraform fmt -check -recursive infra/terraform`
     2. `terraform -chdir=infra/terraform/envs/dev init -backend=false`
     3. `terraform -chdir=infra/terraform/envs/dev validate`
     4. `terraform -chdir=infra/terraform/envs/prod init -backend=false`
     5. `terraform -chdir=infra/terraform/envs/prod validate`
     6. `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl`
     7. `tflint --chdir=infra/terraform/envs/prod --config=$PWD/infra/terraform/.tflint.hcl`
   - **[owner]** revisa el plan de CI de la PR: sin cambios fuera de `gold`, el workgroup de dbt y `local-dbt` (O2). El apply lo hace CI al fusionar (IaC only); checkov corre solo en CI.

0c. **Spike dbt-athena (paralelo a la fase 1, rama propia).** **Gate:** 0b aplicada por CI (rol, workgroup y base existen).
   - Verify local: `.venv/bin/dbt parse --project-dir dbt --profiles-dir dbt/ci`.
   - **[owner]** `dbt build --select spike_sessions_window` dos veces con el mismo `run_date` contra dev con `local-dbt`; después con `run_date` D+1; test `window_matches_silver` verde; `ProcessedBytes` en CloudWatch. Resultado: confirma `merge`, pre_hook `DELETE`, `incremental_predicates` y `partitioned_by` con `day(...)`; si algo falla, se reabre la Design Decision 7 antes de la fase 5.
   - **[owner]** `dbt build --full-refresh --select spike_sessions_window`: confirma que `GlueGoldWrite` basta para borrar y recrear. Cada `AccessDenied` se anota en `dbt/SPIKE.md` con la acción y el recurso acotado (S5); la corrección va en PR de `bootstrap/` o del módulo, nunca con `athena:*` ni `Resource="*"`.

1. **PR generador.** Independiente de 0.
   - Cambios de Files Changed, fase 1.
   - Verify, un comando por paso:
     1. `.venv/bin/python -m pytest generators/tests -q` (base 52 passed, más los nuevos)
     2. `.venv/bin/python -m ruff check spark generators`

2. **PR Spark: `ad_spend`, DDL, guard y Glue job de `ad_spend_daily`.** Depende de 1 (esquema de landing).
   - Cambios de Files Changed, fase 2. La línea de `glue_jobs.tf` la aplica CI (IaC only).
   - Verify, un comando por paso:
     1. `.venv/bin/python -m pytest spark/tests -q` (base 90 passed, más los nuevos)
     2. `.venv/bin/python -m ruff check spark generators`
     3. `terraform fmt -check -recursive infra/terraform`
     4. `terraform -chdir=infra/terraform/envs/dev init -backend=false`
     5. `terraform -chdir=infra/terraform/envs/dev validate`
     6. `tflint --chdir=infra/terraform/envs/dev --config=$PWD/infra/terraform/.tflint.hcl`

3. **PR `rebuild_tables` y runbook del backfill.** Depende de 2 (lista cerrada incluye `ad_spend` y `ad_spend_daily`).
   - Verify, un comando por paso:
     1. `.venv/bin/python -m pytest spark/tests/test_rebuild_tables.py -q`
     2. `.venv/bin/python -m ruff check spark generators`

4. **Backfill de dev en Spark local [owner].** Depende de 1, 2 y 3 fusionadas y de un único commit del generador.
   - El backfill completo corre en Spark local con `local-data` (Design Decision 11; Compute split, No hourly-billed resources); ningún día del rango se lanza en Glue. Glue se usa solo para un único día de demo, después del backfill.
   - Según el runbook: (1) regenerar `landing/` desde `run_date` = inicio-6; (2) `rebuild_tables --env dev --dry-run` y después `rebuild_tables --env dev`; (3) Bronze en local por día ascendente, las cuatro fuentes; (4) Silver en local por día ascendente tras su Bronze (WAP); (5) Validations 4 y 4b; (6) un día de demo en Glue Flex; todo dentro de los 30 días de `landing/` (`bucket.tf:79-89`).
   - Verify: Validations 4, 4b y 8 (Testing Strategy, checks del owner). Parada si el coste de dev supera el tope de alarma de 1 USD (O12).

5. **PR proyecto dbt.** Depende de 4 (Silver definitivo) y del resultado de 0c.
   - Cambios de Files Changed, fase 5; incluye el spike limpiado.
   - Verify: `.venv/bin/dbt parse --project-dir dbt --profiles-dir dbt/ci`.
   - **[owner]** `dbt build` contra dev dos veces con el mismo `run_date`, huella `gold_fingerprint.sql`, `ProcessedBytes` y Cost Explorer (Validations 5, 7, 8).

6. **PR CI `dbt-ci.yml`.** Depende de 5 (proyecto que parsear). Puede ir en la misma PR que 5 si el owner lo prefiere.
   - Verify: el job `dbt-ci` verde en la PR; local: `.venv/bin/dbt ls --project-dir dbt --profiles-dir dbt/ci`.

7. **Prod al cierre [owner].** Depende de 5 validado en dev y de que el runbook confirme que el histórico de prod se puede regenerar (S8).
   - 7a. **PR alta de `local-data` en prod** (Files Changed, fase 7a; Ruling "Plan decisions"). Verify: `terraform fmt -check -recursive infra/terraform`, `terraform -chdir=infra/terraform/envs/prod init -backend=false`, `terraform -chdir=infra/terraform/envs/prod validate`, `tflint --chdir=infra/terraform/envs/prod --config=$PWD/infra/terraform/.tflint.hcl`, uno por paso. **[owner]** revisa el plan de CI (solo el rol y su inline); el apply lo hace CI (IaC only, Apply gate).
   - 7-pausa (H6). **[owner]** antes de regenerar: PR `schedule_enabled = false` en `envs/prod/main.tf:5` aplicada por CI, o confirmación del `CodeSha256` de la Lambda de prod frente al commit del backfill, según el runbook. Al terminar 7b, PR de reanudación si se pausó.
   - 7b. **[owner]** con `skyroute-prod-local-data`: regenerar el histórico de prod, `rebuild_tables --env prod --confirm-prod --dry-run`, después `rebuild_tables --env prod --confirm-prod` tecleando `prod`, reproceso en Spark local y, con `local-dbt` de prod, `.venv/bin/dbt build --project-dir dbt --profiles-dir <dir del profiles.yml del owner> --target prod --vars '{run_date: <D>}'` (H5; Ruling "Prod"; segundo y último uso de la Ruling "Bronze rebuild exception").
   - 7c. **PR baja de `local-data` en prod** (Files Changed, fase 7b), mismos Verify que 7a; apply por CI. **[owner]** adjunta como evidencia la salida del apply de CI de 7c con el `destroy` de `aws_iam_role.local_data` y de su `aws_iam_role_policy`, y `aws iam get-role --role-name skyroute-prod-local-data` con `NoSuchEntity` (O15, H4; sin `--region`, IAM es global).
   - Verify: Validations 4, 4b, 5 y 8 sobre prod; O15.

## Testing Strategy

Contrato para `reppit-test`. Los checks de agente son comandos locales; los de owner (Apply gate) los ejecuta el owner y `reppit-test` comprueba su evidencia adjunta.

### Verify commands del proyecto (AGENTS.md)

| # | Comando | Esperado |
|---|---------|----------|
| V1 | `.venv/bin/python -m ruff check spark generators` | sin errores |
| V2 | `.venv/bin/python -m pytest generators/tests -q` | todo verde; más de 52 passed |
| V3 | `.venv/bin/python -m pytest spark/tests -q` | todo verde; más de 90 passed |
| V4 | `terraform fmt -check -recursive infra/terraform` | salida 0 |
| V5 | `terraform -chdir=infra/terraform/bootstrap validate`, `envs/dev`, `envs/prod` (tras `init -backend=false`) | `Success!` |
| V6 | `tflint --chdir=infra/terraform/<root-module> --config=$PWD/infra/terraform/.tflint.hcl` para `bootstrap`, `envs/dev`, `envs/prod` | sin issues |
| V7 | `.venv/bin/dbt parse --project-dir dbt --profiles-dir dbt/ci` | sin errores, sin credenciales AWS |
| V8 | `.venv/bin/dbt ls --project-dir dbt --profiles-dir dbt/ci` | lista todos los modelos, seeds, tests y exposures de Files Changed fase 5 |
| V9 | `git diff main -- generators/tests/test_keys.py` | vacío (los ids no cambian de formato) |
| V10 | `.venv/bin/dbt ls --project-dir dbt --profiles-dir dbt/ci --resource-type exposure` | exactamente las siete exposures `kpi_*` de Files Changed fase 5, una por KPI del glosario (criterio 1, A5) |
| V11 | `.venv/bin/python -m sqlfluff lint --dialect athena --templater jinja dbt/models` | sin errores (Design Decision 9) |
| V12 | `git diff main -- generators/lambda_handler.py` | vacío (Ruling "Plan decisions") |

### Unit tests nuevos (generador)

- 2a `test_same_run_date_same_bytes`: `clickstream.generate` y `ad_spend.generate` dos veces con la misma fecha dan bytes idénticos.
- 2b `test_multi_campaign_share`: sobre un rango de 30 días desde inicio, al menos un 30 % de reservas tienen ≥ 2 campañas distintas en su recorrido (umbral: Open question 1).
- 2c `test_last_touch_is_booking_campaign`: la campaña del último touchpoint es la `campaign_id` de la reserva.
- 2d `test_funnel_never_inverted`: en cada sesión emitida por el generador (agrupada por la sesión del generador), el orden de los tipos respeta `search` → `product_view` → `add_to_cart` → `begin_checkout` → `purchase`. En Gold, el mismo orden se comprueba sobre `sessions.session_key` con el test singular `funnel_order_per_session` (O16).
- `test_background_has_no_late_funnel_steps`: los eventos de fondo solo tienen tipos de `BACKGROUND_EVENT_TYPES`; ninguno es `add_to_cart`, `begin_checkout` ni `purchase` (Design Decision 5).
- `test_background_still_emits_consent_with_email` (H1): sobre un rango de días, el fondo emite al menos un `consent`, todo `consent` de fondo lleva `email` no vacío y ningún otro tipo de fondo lo lleva; también emite `page_view`.
- `test_journey_event_ids_reserved_range` (H8): todo `event_id` de recorrido sale de `n = 2000 + j*100 + k` con `0 <= k < 100`; con el máximo de 4 sesiones de 5 pasos no hay colisión entre recorridos `j` y `j+1`, y un recorrido de 100 pasos lanza `ValueError`.
- 2e `test_touchpoints_in_window`: todo touchpoint de una reserva de D cae en D-6..D y aparece en el output del `run_date` de su sesión.
- `test_event_ids_unique_per_run_date`: sin colisión de `event_id` en un día (fondo, touchpoints, purchase).
- `test_export_has_route_and_travel_date`: el export incluye `origin`, `destination`, `travel_date` y `travel_date >= created_at`.
- `test_backfill_counts`: el recuento esperado de eventos por rango coincide con la suma de líneas generadas (fuente de la Validation 4b).

### Unit tests nuevos (Spark)

- `test_ad_spend_daily_rerun`: relanzar el mismo día no cambia filas ni conteo.
- `test_schema_mismatch_<job>` (uno por cada job Silver con DDL cambiado): crea la tabla con el DDL viejo, ejecuta el job nuevo y espera el error `schema_mismatch` sin escribir.
- `test_schema_mismatch_ad_spend_daily`: como no hay DDL viejo, crea la tabla con el DDL nuevo sin una columna (p. ej. sin `clicks`), ejecuta el job y espera `schema_mismatch` con esa columna en el mensaje y sin escribir (A11).
- `test_bronze_ingest_ad_spend`: `--source ad_spend` ingiere el día; la ingesta de un día con columnas nuevas no declaradas falla como hoy (`ingest.py:63-68`).
- `test_rebuild_tables_closed_list`: en un catálogo local, borra solo las tablas de la lista y deja otra tabla presente.
- `test_rebuild_tables_prod_guard`: `--env prod` sin `--confirm-prod` sale con error y no borra nada; sin `--env` falla el parser.
- `test_rebuild_tables_identity_mismatch`: con `sts:GetCallerIdentity` simulado que devuelve otro rol o `skyroute-prod-local-data` con `--env dev`, sale con error y no borra nada (S8).
- `test_rebuild_tables_typed_confirmation`: si el texto tecleado no es el nombre del entorno, sale con error y no borra nada; imprime la lista cerrada antes de pedirlo (S8).
- `test_rebuild_tables_dry_run`: `--dry-run` imprime la lista y no borra ninguna tabla ni pide confirmación de borrado (S8).

### Integration checks (owner, evidencia adjunta)

| # | Check | Esperado | De |
|---|-------|----------|----|
| O1 | Salida de `terraform apply` de `bootstrap/` adjunta a la PR 0a antes de fusionar 0b | presente | Criterio 4, Apply gate |
| O2 | Plan de CI de 0b | cambios solo en `gold`, workgroup de dbt y `local-dbt` | Validation 1 |
| O3 | Por tabla sin partición: `aws s3 ls s3://<bucket-dev>/silver/<tabla>/data/ --recursive --summarize --region eu-west-3` | < 100 MB cada una | Validation 4 |
| O4 | Athena: `SELECT count(*), count(DISTINCT event_id) FROM skyroute_dev_silver.events` | los dos iguales al total de `test_backfill_counts` para el rango | Validation 4b |
| O5 | Logs de Silver del backfill | ningún `events_conflicting_published` ni `schema_mismatch` | Validation 4b |
| O6 | Athena: versiones abiertas por `booking_id` en `bookings_scd2` | exactamente una por reserva | Validation 4b |
| O7 | `dbt build --vars '{run_date: <D>}'` dos veces y `analyses/gold_fingerprint.sql` tras cada una | huellas idénticas | Validation 5, Idempotency |
| O8 | Test singular `attribution_totals_match` | los tres modelos reparten el total de `amount_eur` `confirmed` de la ventana | Validation 6, criterio 1 |
| O9 | Test singular `attribution_models_differ` | falla si los tres repartos por campaña son iguales; pasa | Validation 6 |
| O10 | Test singular `window_matches_silver` (0c y fase 5) | 0 filas | Validation 6b |
| O11 | `ProcessedBytes` del workgroup `skyroute-dev-dbt` en CloudWatch; `target/run_results.json` | cada consulta < 100 MB; ninguna cancelada | Validation 7, criterio 6 |
| O12 | Cost Explorer (Glue, Athena y S3, `eu-west-3`) tras el backfill de dev, el día de demo en Glue y el primer `dbt build` | cifra adjunta; acumulado de dev por debajo del tope de alarma de 1 USD | Validation 8, criterio 6 |
| O13 | Tests singulares `kpi_roas_formula` y `kpi_cac_formula` en `dbt build` de dev, más V10 | verdes: ROAS y CAC recalculados desde staging con la fórmula literal del glosario coinciden con `mart_roas_daily` y `mart_cac_monthly`; exposures = KPIs del glosario | Criterio 1 |
| O14 | Job `dbt-ci` de la PR 6 | verde, sin pasos de OIDC ni AWS | Criterio 5 |
| O15 | Salida del apply de CI de 7c con `destroy` de `aws_iam_role.local_data` y su `aws_iam_role_policy`; después `aws iam get-role --role-name skyroute-prod-local-data` (sin `--region`: IAM es global) | los dos `destroy` presentes; `NoSuchEntity` | Ruling "Plan decisions", H4 |
| O16 | Test singular `funnel_order_per_session` sobre `sessions.session_key` | 0 filas | Ruling "Funnel", test 2d |
| O17 | Tras 0b, el owner simula, nunca con un modelo dbt (H2), un comando por paso: (1) `aws iam simulate-principal-policy --policy-source-arn <ARN de skyroute-dev-local-dbt> --action-names s3:PutObject s3:DeleteObject --resource-arns arn:aws:s3:::<bucket-dev>/silver/__o17_probe__/x`; (2) `aws iam simulate-principal-policy --policy-source-arn <ARN de skyroute-dev-local-dbt> --action-names glue:CreateTable glue:DeleteTable glue:UpdateTable --resource-arns arn:aws:glue:eu-west-3:<account>:table/skyroute_dev_silver/__o17_probe__`; (3)-(4) lo mismo con `landing/__o17_probe__/x` para S3 y (5)-(6) con `bronze/__o17_probe__/x` y `table/skyroute_dev_bronze/__o17_probe__` | `EvalDecision` = `explicitDeny` en cada acción y recurso | Security Considerations, S2 |
| O18 | Test singular `no_email_columns_in_gold` (H3) en `dbt build` de dev | 0 filas: ninguna columna `%email%` en `information_schema.columns` del schema gold | S9, Ruling "CRM y bajas" |

## Observability

### Metrics
- `ProcessedBytes` en `AWS/Athena`, dimensión `WorkGroup` = `skyroute-<env>-dbt` (métricas activadas como en `athena.tf:13`); referencia: 100 MB por consulta.
- Cost Explorer por servicio (Glue, Athena) tras el backfill y tras cada build relevante.

### Logging
- `rebuild_tables` registra cada tabla borrada y el entorno; los jobs Silver registran `schema_mismatch` con las columnas que faltan.

## Security Considerations
- `local-dbt` (S1-S3, S6): solo el usuario del owner, la misma trust con MFA de `local-data` sin relajarla, sesión de 1 h, `permissions_boundary` del entorno. Política propia sin `common_statements`: no tiene `ssm:GetParameter` ni `kms:Decrypt` de `hmac-email-key`. Glue con statements propios (Get* en silver; Get*, Create/Update/DeleteTable solo en gold), sin tocar el comodín `glue_catalog_resources`; sin `glue:CreateDatabase`. Athena solo sobre el ARN `skyroute-<env>-dbt` con `enforce_workgroup_configuration = true`. `Deny` explícito de escritura y borrado en `landing/*`, `bronze/*`, `silver/*` y de `glue:Create*`/`Update*`/`Delete*` en bronze y silver, porque la boundary sí los concede (`workload_boundary_dev.tf:45-70`); O17 lo comprueba con `aws iam simulate-principal-policy` y no con escrituras reales, porque si el Deny fallara la boundary las permitiría y una materialización `table` de dbt-athena haría drop o rename en Silver (H2).
- Acciones extra que pida dbt-athena (S5): las lista el spike 0c, acotadas a recurso; nunca `athena:*` ni `Resource="*"`.
- `rebuild_tables` es destructivo (S8): lista cerrada, `--env` obligatorio, identidad comprobada con `sts`, confirmación tecleada, `--dry-run`, `--confirm-prod`; en dev el histórico se regenera desde el generador y en prod el runbook lo confirma antes de la fase 7.
- `local-data` en prod existe solo entre las PRs 7a y 7c; O15 prueba que se retiró.
- Radio de error (S13): la fase 0a añade `gold/*` a `AllowLakehouseDelete` de la boundary de prod, así que un `--env` equivocado con un rol de prod puede borrar también Gold de prod. Mitigan la comprobación de identidad de `rebuild_tables` y que `local-dbt` se asuma por entorno.
- PII (S9, H3): Gold no propaga el hash del email; `stg_events` excluye `email_hmac` con lista explícita de columnas, `dim_customer` tiene las columnas fijadas en Data Models y O18 falla si aparece una columna `%email%` en el schema gold.
- CI de dbt sin credenciales ni OIDC.

## Rollout Strategy
1. Infra en dev y prod (0a, 0b).
2. Generador y Spark fusionados (1-3); backfill de dev (4).
3. Gold en dev (5, 6) con evidencias del owner.
4. Prod al cierre (7): alta temporal de `local-data` (7a), rebuild y `dbt build` (7b), baja de `local-data` (7c).

## Future Considerations

### Known Limitations
- Slim CI contra dev, deuda (Ruling "dbt en CI"); CRM fuera hasta la Fase 7 (Ruling "CRM y bajas").
- Si O3 da tablas cerca de 100 MB, hace falta partición en Silver (cambio de Spark, Compute split), fuera de este plan.
- El pre_hook `DELETE` y el `merge` no son atómicos; un fallo entre los dos deja la ventana vacía hasta relanzar el mismo `run_date`.

## Dependencies

### Development Dependencies
- Único sitio de fijación: `requirements-dev.txt`, tocado solo por la PR de la fase 5. `dbt-athena==1.11.2` (verificado en PyPI el 2026-11-17 por aws-researcher, compatible con `dbt-core>=1.8,<2.0`) y `dbt-core` fijado a una versión exacta de ese rango que elige el executor al instalar; `sqlfluff` con dialecto athena. `dbt-ci.yml` instala desde ese archivo y no repite versiones.

## Open questions

Cerradas por Ruling "Plan decisions" (2026-11-23): C1 workgroup propio `skyroute-<env>-dbt` (Design Decision 8); fracción del budget del backfill, sustituida por backfill en Spark local y tope de alarma de 1 USD en dev (antigua 4; Design Decision 11); `ad_spend` como fuente diaria local sin tocar la Lambda (antigua 6; Design Decision 4); `local-data` temporal en prod (antigua 7; Design Decision 2, fase 7).

Resueltas con la recomendación de `proposal.md` (el owner puede cambiarlas): P1-2 reintentar el backfill desde (1) cuenta como el mismo backfill; P1-5 backfill desde inicio-6 (Design Decision 6); recuento de 4b desde el generador (Design Decision 6); `mart_cac_monthly` y `mart_customer_rfm` como `table` (Design Decision 7); lint con sqlfluff (Design Decision 9).

Siguen siendo decisión del owner:
1. **Umbral multi-campaña del test 2b.** Recomendación: 30 %, el de la proposal; con menos los tres modelos difieren poco en la demo.
2. **C2, precios de Athena y Glue 5.0 Flex en `eu-west-3`.** cost-guard usó 0,29 USD/DPU-h con mínimo de 1 min. Recomendación: confirmarlos en el Pricing Calculator antes del día de demo en Glue (fase 4).
3. **C3, tamaño real de Silver.** Se mide en O3; no bloquea hasta la fase 4.
4. **Fecha de inicio del histórico.** El plan usa "inicio-6"; el owner fija la fecha de inicio y el rango de 182 días del runbook.
5. **Versión exacta de `dbt-core`.** Dentro de `>=1.8,<2.0`; recomendación: la última 1.x compatible con `dbt-athena==1.11.2` el día de la fase 5.

## References
- `docs/design/gold-dbt/working/research.md`
- `docs/design/gold-dbt/working/proposal.md` (Proposal 1, Validation, § Decision)
- `docs/design/gold-dbt/context.md` § Rulings
- `docs/design/CONTEXT.md` § Conventions
- `AGENTS.md` (comandos de build y test)
- docs.getdbt.com/reference/resource-configs/athena-configs (citado por la proposal, 2026-11-23)
