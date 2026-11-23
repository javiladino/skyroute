---
type: Proposal
---

# gold-dbt: Solution Proposals

> **Task:** construir Gold con dbt sobre Athena (staging, dimensional, atribución en tres modelos, ROAS, funnel, RFM, tests, contratos, exposures, docs) a partir de un Silver ampliado.
> **Date:** 2026-11-23
> **Research source:** `docs/design/gold-dbt/working/research.md`; §1 (tablas Silver), §2 (generador), §3 (catálogo, Athena, IAM), §4 (CI), §5 (KPI frente a Silver), §7 (riesgos). Decisiones del owner: `docs/design/gold-dbt/context.md` § Rulings, "Research decisions" (vinculantes).
> **Review:** 2 rondas adversariales: NEEDS-REVISION → GO-WITH-FIXES, hallazgos aplicados (2026-11-23), junto con los hechos de aws-researcher (docs de dbt-athena consultadas el 2026-11-23).

## Context

**Request:** partir y secuenciar el trabajo de la Fase 4 en dos bloques, (A) generador + Spark y (B) proyecto dbt, de forma que Gold cumpla "hecho cuando el glosario de KPIs coincide con el SQL" (`gold-dbt/context.md:8`) sin contradecir ningún Ruling.

**Success criteria** (de `gold-dbt/context.md:8` y del brief del orquestador):
1. El glosario de KPIs coincide con el SQL (ROAS, CAC, funnel, RFM, atribución last-click / linear / 40/20/40).
2. Respeta todas las Rulings de "Research decisions" (gasto y canal, multi-campaña, ventana 7 días, ruta y fecha de viaje, funnel de cinco pasos, `session_key`, CRM fuera, rol `local-dbt`, CI sin AWS, Gold solo en dev, un único cambio y backfill del generador).
3. Materialización Iceberg idempotente para las ventanas D-4..D (sesión) y D-7..D (atribución).
4. Identidad `skyroute-<env>-local-dbt` con la PR de `bootstrap/` antes de la del módulo.
5. CI de dbt con solo `dbt parse`/`dbt ls` (y lint), sin AWS.
6. Coste de Athena dentro del corte de 100 MB por consulta y del budget de 10 USD.

**Bloques:**
- **(A)** generador y Spark: `ad_spend` (landing, Bronze, Silver, como `fx`), recorridos de 1–4 touchpoints con campaña propia, `origin`/`destination`/`travel_date`, eventos `product_view` y `begin_checkout`, DDL nuevos o ampliados en Silver y un único backfill.
- **(B)** proyecto dbt: staging, `dim_*`/`fct_*`, `mart_attribution` (tres modelos), `mart_roas_daily`, `mart_cac_monthly`, `mart_funnel`, `mart_customer_rfm`, tests, contratos, exposures y docs.

**Key constraints from the research:**
- Gasto y canal no existen en ninguna capa; ROAS y CAC no son calculables con Silver actual (research §5, §7). La Ruling los trae por Spark como `fx`, así que (B) depende de (A) para esos marts (Compute split).
- Hoy cada reserva tiene una sola `campaign_id` heredada por todo su recorrido, así que los tres modelos de atribución coinciden (research §5, fila `mart_attribution`). Un Gold de atribución sobre el Silver actual no puede demostrar que el SQL distingue los modelos.
- `route` existe en el generador pero no se exporta (`export_bookings.py:28-31`, research §2); `travel_date` no existe. Funnel: no hay `product_view` ni `begin_checkout` (research §2, `model.py:35-36`).
- `sessions.session_key` es inestable hasta D+4 (`sessions.py:25-27`, `:58`, research §1); `sessions` no lleva `campaign_id` (research §1). La Ruling fija touchpoint = sesión con la campaña de su primer evento, unida en Gold desde `events`.
- `sessions`, `bookings_scd2`, `bookings_current` y `bookings_eur` no tienen partición; `events` va por `days(event_ts)` y `fx_daily` por `fx_date` (research §1). Con el corte de 100 MB (`athena.tf:12-14`) las lecturas completas de tablas sin partición son el riesgo de coste (research §7). Tamaño real en S3: no comprobado (research §7).
- No existe base `skyroute_<env>_gold` (`glue_catalog.tf:2`, `:9`), ni `gold/` en boundaries (`workload_boundary_dev.tf:13-54`) ni en roles (research §3). Cambiar boundaries exige que el owner aplique `bootstrap/` (Apply gate).
- No hay dbt en CI ni en `requirements-dev.txt` (research §4).
- Volumen: unos 3.900 eventos/día, 120 reservas/día (research §7). El cambio de (A) añade eventos (dos tipos nuevos y más touchpoints), así que el volumen crecerá; cuánto no está medido.
- **Silver no admite reprocesar contenido distinto con los mismos ids.** `event_id` es determinista por (`run_date`, slot, `n`) (`keys.py:40`); el generador nuevo produce contenido distinto con los mismos ids, y `events.py:185-190` aborta con `events_conflicting_published`; su MERGE solo tiene `WHEN NOT MATCHED THEN INSERT` (`events.py:192-197`). En `bookings_scd2` las filas regeneradas se abrirían como versiones nuevas en lugar de sustituir el histórico. Conclusión: el backfill exige reconstruir Bronze y Silver, no solo relanzar los jobs (Idempotency, Medallion layers).
- **Sin evolución de esquema.** Los seis jobs Silver crean su tabla con `CREATE TABLE IF NOT EXISTS` y ninguno ejecuta `ALTER TABLE` (verificado por el executor): sobre una tabla ya existente, las columnas nuevas no aparecerían.
- **`landing/` caduca a los 30 días por edad del objeto** (`modules/generator-landing/bucket.tf:79-89`), no por fecha lógica: un objeto regenerado hoy para un día de hace 182 días caduca 30 días después de escribirse.
- **Budget de cuenta de 10 USD** en `bootstrap/budget.tf:4`: cubre todo el gasto (Glue, Athena, S3), y cambiarlo es Apply gate (lo aplica el owner), no IaC only.
- **Workgroup de Athena.** `skyroute-<env>` tiene `enforce_workgroup_configuration = true` y `bytes_scanned_cutoff_per_query = 104857600` (`athena.tf:12-14`); el corte vale para toda consulta del workgroup, así que se infiere que también para los CTAS y MERGE de dbt. Las consultas canceladas por el corte se facturan. La descripción del workgroup es "de consultas de comprobación" (`athena.tf:7`). Métrica disponible: `ProcessedBytes` en `AWS/Athena`, dimensión `WorkGroup` (`publish_cloudwatch_metrics_enabled = true`, `athena.tf:13`).
- **dbt-athena con Iceberg** (docs.getdbt.com/reference/resource-configs/athena-configs, consultado el 2026-11-23): estrategias `append`, `merge` (engine v3, `unique_key` obligatoria) y `microbatch`; `insert_overwrite` **no** está soportado con Iceberg y es el valor por defecto, así que cada modelo incremental fija `incremental_strategy` explícitamente. `merge` admite `incremental_predicates` (sobre `target.`), `delete_condition`, `update_condition` e `insert_condition`, con columnas prefijadas `src.` o `target.`. Versión: dbt-athena 1.11.2 (PyPI, 17-nov-2026), dbt-core `>=1.8,<2.0`; el código vive en `dbt-labs/dbt-adapters` (el repo `dbt-athena` está archivado).
- **Tests de hoy:** `generators/tests` 52 passed, `spark/tests` 90 passed (línea base para las Validations).

**Conventions aplicables:** Compute split, Table format, Medallion layers, Idempotency, Apply gate, IaC only, No hourly-billed resources, Region, Git workflow (`docs/design/CONTEXT.md` § Conventions).

**Lo que la research no cubre (vale para las tres propuestas):**
- El comportamiento real de `dbt-athena` 1.11.2 sobre las tablas Silver actuales: las estrategias están documentadas (Context), pero no probadas en esta cuenta; tampoco `partitioned_by` con transformaciones ni la semántica de borrado de `microbatch`.
- El precio de Athena en `eu-west-3`: el JSON oficial de precios da "7.0" sin unidad; la referencia es 5 USD/TB con un mínimo probable de 10 MB por consulta. **A confirmar por el owner en el Pricing Calculator.** Igual para el precio de DPU-hora de Glue 5.0 Flex en `eu-west-3`.
- El tamaño real de Silver en S3 (research §7, lo aporta el owner).
- Si las tablas Bronze/Silver están en el estado de Terraform: cerrado. `grep aws_glue_catalog_table infra/terraform` no devuelve nada, así que ninguna tabla Bronze ni Silver está en Terraform (las crea Spark con `CREATE TABLE IF NOT EXISTS`) e IaC only no choca con el DROP. `terraform state list` queda solo como confirmación del owner.
- El bucket de datos no tiene versionado (`modules/generator-landing/bucket.tf:14`, skip de CKV_AWS_21): `DROP TABLE ... PURGE` no deja versiones no actuales en S3.

**Comunes a las tres propuestas (no son eje de diferencia):**
- **Materialización.** Staging como `view` (sin coste de almacenamiento; coste al consultar). Todo modelo incremental fija `table_type='iceberg'` e `incremental_strategy='merge'` de forma explícita, porque el valor por defecto (`insert_overwrite`) no está soportado con Iceberg (Context, docs de dbt-athena). Nada usa `now()`; la fecha lógica llega por `var("run_date")` (Idempotency). Dimensiones pequeñas (`dim_campaign` del seed, `dim_date`) como `table` Iceberg completa. Partición de los `fct_` grandes por día (`partitioned_by=['day(...)']`, a confirmar en el spike).
- **Borrado de la ventana (mecanismo concreto).** `delete_condition` de `merge` solo actúa sobre filas que casan con la fuente, así que no borra las `session_key` que Silver ya eliminó (`sessions.py:238-253`, `WHEN NOT MATCHED BY SOURCE ... DELETE`). Por eso cada modelo con ventana usa:
  1. `pre_hook` envuelto en `{% if is_incremental() %}`: `DELETE FROM {{ this }} WHERE <predicado> BETWEEN date '{{ inicio }}' AND date '{{ D }}'`, con el predicado de cada modelo:
     - `fct_sessions`, `fct_touchpoints`, base de `mart_funnel`: `session_start_date`, D-4..D.
     - `mart_attribution`: `booking_date`, D-7..D.
     - `mart_roas_daily`: `spend_date`, D-7..D (el ingreso atribuido de D-7..D puede cambiar con la atribución).
     - `mart_funnel` agregado: `session_start_date`, D-4..D.
     - `mart_cac_monthly` y `mart_customer_rfm`: sin pre_hook; `table` completa o merge por mes/cliente, a fijar en Plan.
  2. `merge` con `unique_key` (`session_key` en `fct_sessions`, `fct_touchpoints` y la base de `mart_funnel`; compuesta `booking_id`, `model`, `touch_seq` en `mart_attribution`; `campaign_id`, `spend_date` en `mart_roas_daily`) e `incremental_predicates` `["target.session_start_date >= date '{{ D-4 }}'"]` para que el MERGE solo explore la ventana.
  Tras el `DELETE` el `merge` inserta toda la ventana; el `unique_key` protege contra duplicados si el pre_hook no corriera. El pre_hook `DELETE` y el `merge` no son atómicos: si el modelo falla entre los dos, la ventana queda vacía hasta que se relanza el mismo `run_date`, que la rehace entera (Idempotency). `microbatch` queda como alternativa solo si el spike demuestra que reemplaza el lote entero (no verificado).
- **Workgroup de dbt.** Las tres propuestas comparten la pregunta de si dbt usa `skyroute-<env>` (corte de 100 MB, descrito como "de comprobación") o un workgroup propio `skyroute-<env>-dbt` en `modules/lakehouse/athena.tf` (IaC only) con su propio corte. Recomendación del autor: workgroup propio con el mismo corte, para separar `ProcessedBytes` de dbt del resto; decide el owner (Open Question común C1).
- **Identidad.** Rol `skyroute-<env>-local-dbt` (MFA, 1 h): S3 lectura `silver/`, lectura/escritura/borrado `gold/` y `athena-results/`; Glue lectura sobre `skyroute_<env>_silver` y escritura de tablas sobre `skyroute_<env>_gold`; Athena sobre el workgroup `skyroute-<env>`. Orden: PR 1 `bootstrap/` (boundaries de workload dev y prod con `gold/` en S3, y lo que necesite el rol `local-dbt`; aplicada por el owner, Apply gate) → PR 2 módulo `lakehouse` (base `skyroute_<env>_gold`, rol, en dev y prod, aplicado por CI, IaC only). **Gate:** la PR 2 no se fusiona sin la evidencia del apply de `bootstrap/` hecho por el owner (salida de `terraform apply` adjunta a la PR 1). Hecho verificado: `ci-apply-{dev,prod}` ya puede crear `skyroute_<env>_gold`, porque el comodín `database/skyroute_${env}_*` está en `ci_roles.tf:31` y `glue:CreateDatabase` en `ci_roles.tf:202`; la base no necesita cambios de bootstrap para CI. La base la crea Terraform, no dbt, así que el rol `local-dbt` no necesita `glue:CreateDatabase`.
- **CI.** Workflow nuevo `dbt-ci.yml`: `dbt deps`, `dbt parse`, `dbt ls` con un `profiles.yml` ficticio y sin credenciales; lint SQL (sqlfluff u otro, pregunta abierta). Sin OIDC ni AWS. `dbt build` en dev lo corre el owner en local y su salida es la evidencia (Ruling "dbt en CI").
- **Sin recursos por hora.** dbt corre en la máquina del owner contra Athena serverless; nada nuevo cobra inactivo (No hourly-billed resources). Todo en `eu-west-3` (Region).
- **Git.** Una rama por PR desde `main`; ningún agente hace commit ni push sin que el owner lo pida (Git workflow).
- **Prod.** Infraestructura en los dos entornos; `dbt build` en prod solo al cierre, tras regenerar el histórico de prod (Ruling "Prod").
- **Coste.** Las lecturas de `sessions` y de las tres tablas de bookings son completas (sin partición, research §1); el incremental de `fct_sessions` filtra por `session_start_date`, pero Athena escanea la tabla igual. Con unos 3.900 eventos/día (research §7) se espera que cada tabla quede muy por debajo de 100 MB, pero no está medido; la medida del owner tras el backfill decide si hace falta pedir partición en Silver (cambio de Spark, Compute split). Mitigación común: `dbt build --select` por capas y nada de `dbt build` en CI.
- **Coste frente al budget de 10 USD (cuenta entera, `bootstrap/budget.tf:4`).** Partidas: (a) backfill de Glue: 182 días × jobs Bronze y Silver (seis Silver más `ad_spend_daily`) en dev, y otra vez en prod al cierre (Ruling "Prod"); coste = ejecuciones × DPU × minutos facturados con el precio Flex de `eu-west-3` (a confirmar por el owner); (b) Athena: bytes de cada `dbt build` × precio a confirmar, con el mínimo por consulta multiplicado por el número de modelos. Paso común: el owner consulta Cost Explorer (servicio Glue y Athena, `eu-west-3`) **tras el backfill** y **tras el primer `dbt build`**, y adjunta la cifra como evidencia antes de seguir. Si el backfill de dev por sí solo pasa de una fracción que fije el owner, se para antes del de prod.
- **Determinismo de los touchpoints (día lógico de emisión).** Cada touchpoint se emite en el día lógico de su propia sesión: una reserva del día D con k touchpoints genera sesiones en días D-j (0 ≤ j ≤ 6, el último touch en D). El generador del día X emite, por tanto, sesiones de reservas de X..X+6, derivadas de la semilla de esas fechas; el `event_id` sigue siendo (`run_date` = X, slot, `n`), así que dos ejecuciones del día X producen los mismos ids y contenidos. Como j ≤ 6, todo el recorrido cabe en la ventana D-7..D de la atribución.
  - **Lo que importa es la fecha lógica de emisión, no que la sesión no cruce medianoche.** Una sesión no cae entera en un día: en el generador los eventos de recorrido pueden caer hasta 80 min antes de `created_at`, en D-1 (`clickstream.py:41-43`), y los eventos tardíos se desplazan (`:55-57`). Silver no usa el `session_id` del generador: corta la sesión por un hueco de 30 min o un tope de 24 h, no a medianoche; la sesión pertenece al día de su primer evento y la lectura es `[D-5 00:00 - gap, D+2)` (`sessions.py:3-8`, `:10`, `:20`, `:176`). El determinismo se sostiene porque cada evento tiene un único `run_date` de emisión fijado por la semilla: reprocesar los mismos días lógicos da los mismos eventos y, por tanto, las mismas sesiones de Silver.
  - **Borde del histórico.** Una reserva del primer día del histórico (inicio) tendría touchpoints en días anteriores que nadie emite. Elección del autor: el backfill arranca en `run_date` = inicio-6, de modo que toda reserva desde inicio tiene su recorrido completo; los tests 2b y 2e se aplican a reservas desde inicio. Se prefiere a excluir los 6 primeros días en los tests porque así Gold no contiene reservas con recorridos truncados (que sesgarían la atribución), a cambio de 6 días más de Glue. La alternativa queda abierta al owner (Open Question 5 de P1).
  - **Runbook.** Si el código del generador cambia entre los `run_date` X y X+6 del backfill, una reserva tendría touchpoints de dos versiones; el runbook exige el mismo commit del generador para todo el regenerado.

## Proposal 1: Recrear Bronze y Silver, A completo y después B, con spike temprano de dbt-athena

### Overview
Todo queda en `gold-dbt`, con un único `plan.md` en fases: primero la infraestructura (PR `bootstrap/`, PR módulo), un spike de dbt-athena sobre Silver actual en paralelo, luego (A) entero con un backfill que recrea Bronze y Silver (Idempotency, Medallion layers), y solo cuando Silver ampliado pasa sus checks WAP arranca (B). dbt se escribe una sola vez contra el Silver definitivo, lo que encaja con la Ruling "un único cambio y un único backfill".

### Key Changes
| Fase | Component | Change |
|------|-----------|--------|
| 0 | `infra/terraform/bootstrap/workload_boundary_{dev,prod}.tf` | Modified: `gold/` en S3 y Glue de `skyroute_<env>_gold` (owner aplica, Apply gate) |
| 0 | `infra/terraform/modules/lakehouse/glue_catalog.tf`, `iam.tf` | Modified: base `skyroute_<env>_gold`; rol `local-dbt` (IaC only, apply por CI) |
| 1 | `generators/ota/model.py`, `clickstream.py`, `export_bookings.py` | Modified: recorridos 1–4 touchpoints con campaña propia y última = campaña de la reserva; `product_view`, `begin_checkout` con abandono determinista; `origin`/`destination`/`travel_date` exportados |
| 1 | `generators/ota/` (módulo nuevo de gasto) + Lambda | New: gasto diario por campaña a `landing/ad_spend/` |
| 1 | `spark/jobs/bronze/ingest.py` | Modified: `SOURCES` + `ad_spend` (`ingest.py:27`) |
| 1 | `spark/jobs/silver/ad_spend_daily.py` + `spark/checks/` | New: Silver de gasto, clave (`spend_date`, `campaign_id`), partición por día, como `fx_daily` |
| 1 | `spark/jobs/silver/bookings_*.py`, `events.py` | Modified: DDL con `origin`, `destination`, `travel_date` (reservas); `events` admite los dos tipos nuevos |
| 0b | `dbt/` mínimo (profile, una `source`, un modelo de prueba) | New, spike temprano en paralelo con la fase 1: contra una tabla Silver actual (`sessions`) prueba `merge` con `unique_key`, el pre_hook `DELETE` de la ventana y `incremental_predicates`; mide `ProcessedBytes`. Solo el owner en local; no se fusiona hasta la fase 2 |
| 1 | Evolución de esquema | Recrear, no `ALTER`: como el backfill reescribe todo el contenido (Context, `keys.py:40`), `ALTER TABLE ADD COLUMNS` no resolvería los conflictos de ids. Cada job Silver añade una comprobación al arrancar: si la tabla existe y le falta una columna del DDL, falla con un error explícito (`schema_mismatch`) en vez de escribir sin ella |
| 1 | `spark/jobs/maintenance/rebuild_tables.py` | New: job Spark que hace `DROP TABLE ... PURGE` de las tablas Bronze y Silver del entorno, con lista cerrada de tablas y argumento `--env` obligatorio; se niega si `--env prod` sin `--confirm-prod`. Vía Spark y no IaC porque las tablas las crea Spark y ninguna está en Terraform (C4). Rompe Bronze append-only (Medallion layers, Idempotency) solo bajo la Ruling "Bronze rebuild exception (2026-11-23)" de `gold-dbt/context.md`, de un solo uso. Corre en local con `skyroute-<env>-local-data`, sin cambios de IAM (Open Question 3) |
| 1 | Backfill (runbook en `docs/runbooks/`) | Lo ejecuta el owner, en dev, en este orden: (1) regenerar `landing/` de los 182 días, desde `run_date` = inicio-6 (borde del histórico, Context), con el generador nuevo y un único commit para todo el rango; (2) `rebuild_tables` en dev; (3) Bronze por día lógico ascendente; (4) Silver por día ascendente, cada job tras su Bronze (WAP); (5) validaciones 4 y 4b; todo antes de que pasen 30 días desde el paso 1. Si se supera, se repite desde (1): el generador es la fuente reproducible (test 2a de bytes idénticos), no `landing/` |
| 2 | `dbt/` (proyecto completo), `dbt/seeds/campaigns.csv` | New: staging, dims, facts, marts, tests, exposures, docs |
| 2 | `contracts/` | New: contratos ODCS de los marts |
| 2 | `.github/workflows/dbt-ci.yml`, `requirements-dev.txt` | New / Modified: `dbt-athena` y `dbt parse`/`dbt ls` |

### Trade-offs
| Benefit | Risk |
|---------|------|
| dbt nace sobre el Silver final: no hay staging que reescribir tras el backfill (las columnas nuevas de research §5 ya existen) | (B) no empieza hasta que (A) termina; el camino crítico es la suma de los dos bloques |
| Un solo backfill, como fija la Ruling; los tres modelos de atribución se distinguen desde el primer `dbt build` (research §5) | Si el backfill revela un fallo de (A), el arreglo exige repetir regenerado + `rebuild_tables` + reproceso: otro coste de Glue de 182 días × jobs (Context, coste) y una discusión sobre la Ruling "un único backfill" |
| Un solo topic, un solo `plan.md`: las dependencias (gasto → ROAS, `session_key` → touchpoints) quedan en un documento | `plan.md` muy grande (generador, Bronze, Silver, mantenimiento, IAM, dbt, CI); más difícil de revisar en una ronda adversarial |
| La medida de volumen (research §7) se toma ya con los eventos nuevos, así que el cálculo de coste de Athena es sobre el tamaño real | La infra de Gold (fase 0) queda aplicada semanas antes de usarse (sin coste: base Glue y rol no cobran) |
| Recrear las tablas hace el backfill determinista: sin filas viejas, ningún `events_conflicting_published` (`events.py:185-190`) ni versiones espurias en `bookings_scd2` | `DROP TABLE ... PURGE` es destructivo; un `--env` equivocado con credenciales de prod borra prod (la boundary de prod concede `glue:DeleteTable` y `s3:DeleteObject`). Defensa: `--confirm-prod` obligatorio y la sesión MFA de 1 h de `local-data` de prod, que hay que abrir a propósito; además, lista cerrada, y en dev el histórico es regenerable desde el generador |
| El spike 0b valida `merge` + pre_hook `DELETE` sobre Silver real antes de que dependan de ello la atribución y el funnel | El spike consume consultas de Athena contra el budget (Glue no interviene); pequeño, pero sin medir |

### Validation
1. Fase 0: `terraform fmt -check -recursive infra/terraform`; `terraform -chdir=infra/terraform/envs/dev validate`; `tflint` según AGENTS.md; salida del apply de `bootstrap/` del owner adjunta a la PR 1 antes de fusionar la PR 2 (gate); plan de CI en la PR del módulo sin cambios fuera de `gold` y `local-dbt`.
2. Fase 1: `.venv/bin/python -m pytest generators/tests -q` (línea base 52 passed) con tests nuevos: (a) misma fecha lógica → mismo archivo byte a byte; (b) al menos un 30 % de reservas con ≥ 2 campañas distintas en su recorrido (umbral a fijar en Plan); (c) la `campaign_id` de la reserva es la del último touch; (d) secuencia de funnel nunca invertida; (e) todo touchpoint de una reserva del día D cae en D-6..D y se emite en el `run_date` de su sesión.
3. Fase 1: `.venv/bin/python -m pytest spark/tests -q` (línea base 90 passed) con: un test de `ad_spend_daily` (relanzar el día no cambia filas); un test por job Silver que crea la tabla con el DDL **viejo**, ejecuta el job nuevo y comprueba que falla con `schema_mismatch` (tabla ya existente); un test de `rebuild_tables` que, sobre un catálogo local, borra solo las tablas de la lista y rechaza `--env prod` sin `--confirm-prod`.
4. Fase 1, owner, por tabla tras el backfill: `aws s3 ls s3://<bucket-dev>/silver/<tabla>/data/ --recursive --summarize --region eu-west-3` para cada una de `sessions`, `bookings_scd2`, `bookings_current`, `bookings_eur` (o `SELECT sum(file_size_in_bytes) FROM "<tabla>$files"` en Athena); cada tabla sin partición debe quedar por debajo de 100 MB.
4b. Fase 1, owner: tras el reproceso, `SELECT count(*), count(DISTINCT event_id)` de `events` coincide con el total esperado de eventos de los días procesados, que sale de la suma de líneas de `landing/` por día (`aws s3 cp` + `wc -l` por objeto, o un recuento local del generador con el mismo commit y las mismas fechas; el Plan fija cuál); ninguna ejecución Silver terminó con `events_conflicting_published`; `bookings_scd2` tiene exactamente una versión abierta por `booking_id`.
5. Fase 2: `dbt parse` y `dbt ls` en CI verdes; owner en local: `dbt build --vars '{run_date: 2026-xx-xx}'` dos veces seguidas con el mismo `run_date`, y tras cada una `SELECT count(*), sum(<métrica>), checksum(...)` por tabla Gold (consulta guardada en `dbt/analyses/gold_fingerprint.sql`); las dos salidas son idénticas (Idempotency).
6. Fase 2: test singular dbt que falla si `sum(attributed_revenue)` por modelo difiere de `sum(amount_eur)` de reservas `confirmed` en la ventana (los tres modelos reparten el mismo total) y test que falla si los tres modelos dan el mismo reparto por campaña.
6b. Fase 0b y fase 2: test singular `window_matches_silver` que, para D-4..D, hace anti-join en los dos sentidos entre `fct_sessions.session_key` y `silver.sessions.session_key` y falla si devuelve filas (detecta `session_key` desaparecidas en Silver que siguen en Gold).
7. Fase 2, owner: `ProcessedBytes` (`AWS/Athena`, dimensión `WorkGroup` del workgroup que use dbt) en CloudWatch muestra cada consulta del `dbt build` por debajo de 100 MB; ninguna consulta cancelada por el corte en `target/run_results.json`.
8. Owner: Cost Explorer (Glue y Athena, `eu-west-3`) tras el backfill de dev y tras el primer `dbt build`; cifra adjunta como evidencia.

### Open Questions
1. ¿Qué umbral de reservas multi-campaña exige el test del generador? Si es bajo, los tres modelos difieren poco y la demo no lo muestra.
2. ~~Si el backfill falla a mitad, ¿cuenta reintentarlo como "el mismo" backfill?~~ Respuesta propuesta (a confirmar por el owner): sí, porque el generador es determinista (test 2a) y la secuencia empieza por `rebuild_tables`: reintentar desde (1) produce el mismo Silver. Si pasan 30 días desde el regenerado, `landing/` caduca por edad del objeto (`bucket.tf:79-89`) y se regenera, no se reutiliza.
3. ~~¿`rebuild_tables` como Glue job o en local?~~ Cerrada: en local con `skyroute-<env>-local-data`, sin cambios de IAM. La boundary ya concede `glue:DeleteTable` (`workload_boundary_dev.tf:63`, `workload_boundary_prod.tf:63`) y `s3:DeleteObject` sobre `bronze/*` y `silver/*` (`:45-53`). El rol `glue-job` no tiene `DeleteTable` por diseño (`iam.tf:58-59`, `:108-116`: "Ni los Glue jobs ni el mantenimiento borran tablas"), así que no se lanza como Glue job.
4. ¿Qué fracción del budget de 10 USD acepta el owner para el backfill de dev antes de lanzar el de prod?
5. Borde del histórico: ¿confirma el owner arrancar el backfill en `run_date` = inicio-6 (recomendado) o prefiere no ampliar el rango y que los tests 2b y 2e excluyan los 6 primeros días?

**Variante de proceso de la Propuesta 1 (antes Propuesta 2).** Sacar (A) a un topic propio con su ciclo RePPIT no cambia ninguna pieza técnica; solo reparte la Propuesta 1 en dos `plan.md`. Exige que el owner diga dónde viven las Rulings de (A), hoy en `gold-dbt/context.md` (AGENTS.md: si dos archivos no coinciden, se pregunta), y si se reabre `bronze-silver`, que espera su cierre por coste (`gold-dbt/context.md:8`). Se puede elegir como "Propuesta 1, en dos topics" sin cambiar su contenido.

## Proposal 2: Silver versionado en paralelo (sin borrar las tablas actuales)

### Overview
En lugar de recrear Bronze y Silver, el generador nuevo escribe una versión de esquema y los jobs publican en tablas nuevas con sufijo `_v2` (`events_v2`, `sessions_v2`, `bookings_scd2_v2`, …, más `ad_spend_daily`) dentro de las mismas bases `skyroute_<env>_bronze`/`_silver`. Los ids incluyen la versión (`event_id` = (`gen_version`, `run_date`, slot, `n`)), así que no chocan con los publicados (`keys.py:40`, `events.py:185-190`). dbt lee las `_v2` vía `var("silver_suffix")`; cuando Gold se valida, un job de mantenimiento borra las tablas v1.

### Key Changes
| Fase | Component | Change |
|------|-----------|--------|
| 0 | `bootstrap/`, `modules/lakehouse/` | Igual que la Propuesta 1, fase 0 (con el mismo gate) |
| 0b | spike dbt-athena | Igual que la Propuesta 1 |
| 1 | `generators/ota/keys.py` y resto del generador | Modified: `gen_version` en los ids y en la ruta de `landing/` (`landing/v2/<source>/…`) además de los cambios de la Propuesta 1 |
| 1 | `spark/jobs/bronze/ingest.py`, `spark/jobs/silver/*.py` | Modified: nombre de tabla y prefijo de `landing/` parametrizados por versión; DDL nuevo con `CREATE TABLE IF NOT EXISTS` sobre tablas que no existen, así que no hace falta `ALTER` ni recrear |
| 1 | Backfill | Owner: regenerar `landing/v2/`, Bronze v2 y Silver v2 por día ascendente; las tablas v1 siguen sirviendo |
| 2 | `dbt/` | Igual que la Propuesta 1, con `sources` sobre `*{{ var('silver_suffix') }}` |
| 3 | `spark/jobs/maintenance/drop_v1.py` | New: `DROP TABLE ... PURGE` de las v1 tras el primer `dbt build` válido |

### Trade-offs
| Benefit | Risk |
|---------|------|
| Ningún borrado antes de tener el reemplazo: si el backfill falla, v1 sigue intacto y no hay riesgo de `--env` equivocado sobre datos vivos | El sufijo `_v2` es compatible con Medallion layers (solo fija nombres para Gold y las bases); queda una preferencia de nombres: renombrar o no tras `drop_v1` (Open Question 1) |
| No necesita la Ruling "Bronze rebuild exception": las tablas Bronze `_v2` son nuevas y siguen siendo append-only | (el borrado de v1 en `drop_v1` sí es un DROP de Bronze; ocurre tras validar Gold y el owner decide si lo cubre la misma excepción) |
| Repetir el backfill es barato en riesgo: se borra solo `_v2` y se rehace | Mismo coste de Glue que la Propuesta 1 y, mientras conviven, doble almacenamiento en S3 (pequeño, research §7, no medido) |
| Evita la evolución de esquema por completo: las tablas v2 nacen con el DDL nuevo | Cambia `keys.py` y la ruta de `landing/`: más superficie de cambio en generador, Lambda y Bronze que la Propuesta 1, y más tests que tocar (52 y 90 de base) |
| Los tests de Spark sobre tablas existentes no hacen falta para v2 | Los jobs de Airflow y la Lambda deben apuntar a v2 al mismo tiempo; una ventana de doble escritura o un día perdido si no se coordina (Idempotency) |

### Validation
1. Pasos 1, 2, 4, 4b (sobre `_v2`), 5, 6, 6b, 7 y 8 de la Propuesta 1.
2. `.venv/bin/python -m pytest generators/tests -q`: test nuevo que dos versiones distintas producen `event_id` disjuntos para el mismo `run_date` y slot.
3. `.venv/bin/python -m pytest spark/tests -q`: test que, con una tabla v1 existente de esquema viejo, el job con sufijo `_v2` crea su tabla nueva y no modifica la v1 (conteo y snapshot de v1 iguales antes y después).
4. Owner, tras `drop_v1`: `aws glue get-tables --database-name skyroute_dev_silver --region eu-west-3 --query 'TableList[].Name'` no devuelve ninguna tabla sin sufijo.

### Open Questions
1. Preferencia de nombres: ¿se mantiene el sufijo `_v2` para siempre o hay un rename tras `drop_v1`? Cambia los `sources` de dbt y los contratos. Iceberg en Glue admite `ALTER TABLE RENAME` según el motor; no verificado en esta cuenta.
2. ¿Cubre la Ruling "Bronze rebuild exception" el DROP de las Bronze v1 en `drop_v1`, o hace falta otra aprobación?

## Proposal 3: Un topic, B mínimo sobre el Silver actual en paralelo a A

### Overview
Dentro de `gold-dbt`, tras la infraestructura, dos líneas en paralelo: (A) como en la Propuesta 1, y un (B) mínimo que monta el esqueleto dbt (profiles, sources, staging de las seis tablas Silver, `dim_customer`, `dim_date`, `fct_bookings`, `fct_sessions`, `mart_customer_rfm` sin destino ni booking window, CI, tests genéricos). Tras el backfill, (B) completo añade lo que depende de (A): `stg_ad_spend`, `dim_campaign` con el seed, `fct_touchpoints`, atribución, ROAS, CAC, funnel de cinco pasos y RFM completo.

### Key Changes
| Línea | Component | Change |
|-------|-----------|--------|
| 0 | `bootstrap/`, `modules/lakehouse/` | Igual que la Propuesta 1, fase 0 (bloquea a B mínimo, que necesita el rol y la base) |
| A | generador, Bronze, Silver, backfill | Igual que la Propuesta 1, fase 1 |
| B mínimo | `dbt/dbt_project.yml`, `profiles` de ejemplo, `models/staging/`, `dim_customer`, `dim_date`, `fct_bookings`, `fct_sessions`, `mart_customer_rfm` (R, F, M y consentimiento) | New, sobre las columnas de research §1 |
| B mínimo | `dbt-ci.yml`, `requirements-dev.txt` | New / Modified, como las demás propuestas |
| B completo | staging de columnas y tablas nuevas, `dim_campaign`, `fct_touchpoints`, `mart_attribution`, `mart_roas_daily`, `mart_cac_monthly`, `mart_funnel`, RFM con destino y booking window, `contracts/`, exposures, docs | New / Modified tras el backfill |

### Trade-offs
| Benefit | Risk |
|---------|------|
| Acorta el camino crítico: CI, staging, materialización incremental de D-4..D y el rol `local-dbt` se prueban antes del backfill | Staging y `mart_customer_rfm` se reescriben tras el backfill (columnas nuevas de `bookings_*`, `events`, research §5); trabajo hecho dos veces |
| Mide el coste real de Athena del patrón incremental pronto (research §7: tamaño no comprobado), antes de comprometer el diseño de los marts grandes | Un `dbt build` sobre el Silver actual y otro tras el backfill (`--full-refresh`): el doble de consultas de Athena en dev contra el budget de cuenta de 10 USD (`bootstrap/budget.tf:4`, Apply gate), sumadas al mismo backfill de Glue que la Propuesta 1; la cifra exacta depende del precio no verificado |
| Si el backfill hay que repetirlo, B mínimo sigue en pie y solo se rehace `--full-refresh` | El riesgo de repetir el backfill es el mismo que en la Propuesta 1 (mismo `rebuild_tables` y reproceso), y cada repetición añade un tercer build de Gold |
| La materialización Iceberg de `dbt-athena` (merge, `unique_key`, borrado en ventana) se valida antes de que la atribución dependa de ella | Hasta el backfill, Gold no puede cumplir el criterio "glosario = SQL": atribución, ROAS, CAC y funnel no existen (research §5) |
| Dos PRs de dbt más pequeñas, más fáciles de revisar | El backfill reemplaza Silver bajo un Gold ya materializado; Gold debe reconstruirse entero (`--full-refresh`), y un fallo de orden deja Gold incoherente con Silver |

### Validation
1. Infra y (A): pasos 1–4b de la Propuesta 1 (incluido `rebuild_tables` y los tests de esquema sobre tabla existente).
2. B mínimo: `dbt parse`/`dbt ls` en CI; owner: `dbt build` dos veces con el mismo `run_date` sobre el Silver actual y huella `gold_fingerprint.sql` idéntica; test `window_matches_silver` (paso 6b de la Propuesta 1); `fct_sessions` tras cambiar `run_date` a D+1 solo toca `session_key` con `session_start_date` en D-3..D+1.
3. Tras el backfill: `dbt build --full-refresh` y después incremental; pasos 5–8 de la Propuesta 1, con Cost Explorer también tras el build de B mínimo.
4. Test de regresión: el conteo de `fct_bookings` tras el backfill coincide con `bookings_current` en Silver (test dbt `equal_rowcount` o singular).

### Open Questions
1. ¿Acepta el owner gastar consultas de Athena en un Gold que se reconstruye tras el backfill? Depende del tamaño de Silver (research §7, no medido).
2. ¿B mínimo se fusiona en `main` antes del backfill, o vive en una rama hasta entonces? Fusionarlo deja en `main` modelos que dejarán de compilar si cambia el DDL.

## Recommendation

| Criteria | Proposal 1: recrear Bronze/Silver, A → B, spike dbt | Proposal 2: Silver versionado `_v2` | Proposal 3: B mínimo en paralelo |
|----------|------------------------------|------------------------|----------------------------------|
| 1. Glosario = SQL al cierre | Sí, en un único `dbt build` sobre Silver final | Sí, igual que P1 | Sí, solo tras el backfill; antes, parcial |
| 2. Respeta las Rulings | Sí, con la excepción aprobada (Ruling "Bronze rebuild exception (2026-11-23)") | Sí, sin excepción en el backfill (Bronze `_v2` nuevas, append-only); `drop_v1` borra v1 al final | Sí; "un único backfill" se cumple, aunque Gold se reconstruye |
| 3. Materialización D-4..D / D-7..D | Pre_hook `DELETE` + `merge`; validada pronto por el spike 0b | Igual que P1 | Igual; validada sobre B mínimo |
| 4. Rol `local-dbt`, PR `bootstrap/` antes | Común (fase 0, con gate) | Común | Común; además se ejercita pronto |
| 5. CI solo `parse`/`ls` | Común | Común | Común; llega antes a `main` |
| 6. Coste (100 MB, budget de cuenta 10 USD) | Un backfill de Glue por entorno + un build de Gold; Cost Explorer tras cada uno | Mismo Glue + doble almacenamiento temporal | Mismo Glue + dos builds de Gold (tres si se repite el backfill) |
| Reproceso de Silver (ids, esquema) | Recrear con `rebuild_tables`; destructivo, mitigado con lista cerrada | Sin borrado previo; cambia `keys.py` y rutas | Igual que P1 |
| Riesgo de repetir el backfill | Repetir Glue completo; Gold aún no existe | Repetir Glue sobre `_v2`; v1 intacto | Repetir Glue completo y un build extra de Gold |
| Camino crítico | A + B en serie (spike en paralelo) | Igual que P1 | El más corto |
| Retrabajo | Ninguno previsto | Ninguno; un `drop_v1` final | Staging y RFM se reescriben |
| Coste de proceso (docs, reviews) | Un ciclo; `plan.md` grande (variante: dos topics) | Un ciclo; más superficie de cambio | Un ciclo; plan con dos líneas |

**Cuándo elegir cada una.** P1 si se prioriza el menor número de builds y de cambios en el generador, y se acepta un borrado controlado de Bronze/Silver en dev (regenerable). P1 en dos topics (variante de proceso) si el owner quiere un ciclo propio para Silver y decide el hogar de las Rulings de (A). P2 si se prioriza no borrar nada antes de tener el reemplazo ni usar la excepción a Bronze append-only, a costa de tocar ids y rutas. P3 si se prioriza ver dbt sobre datos reales cuanto antes y se acepta reescribir staging y RFM y pagar dos builds.

**Huecos comunes y Open Questions comunes:**
- C1. ¿dbt usa el workgroup `skyroute-<env>` (corte de 100 MB, "de comprobación") o uno propio `skyroute-<env>-dbt` en `modules/lakehouse/athena.tf`? Recomendación del autor: propio, mismo corte. Decide el owner.
- C2. Precio de Athena y de Glue 5.0 Flex en `eu-west-3`: a confirmar por el owner en el Pricing Calculator antes del Plan.
- C3. Tamaño real de Silver (research §7), que se mide por tabla (Validation 4).
- C4. Cerrada: `grep aws_glue_catalog_table infra/terraform` no devuelve nada; ninguna tabla Bronze ni Silver está en Terraform e IaC only no choca con el DROP. `terraform state list` queda solo como confirmación del owner. El ARN `glue_table` de CI (`ci_roles.tf:32`, `table/skyroute_${env}_*/*`) ya cubre gold.
- Ninguna aborda la CRM (fuera, Ruling "CRM y bajas") ni el slim CI (deuda, Ruling "dbt en CI").

**Recomendación (reevaluada tras escribir el plan del backfill): Proposal 1, con el spike 0b.** Escrito el backfill, las tres propuestas pagan el mismo coste de Glue y el mismo riesgo de repetirlo; lo que las separa es qué más se paga. P1 añade un borrado controlado en dev (regenerable desde el generador determinista) y un solo build de Gold; P3 añade un segundo build y retrabajo de staging y RFM; P2 evita el borrado previo y la excepción pero cambia `keys.py`, las rutas de `landing/` y la Lambda. El argumento más fuerte de P3, validar pronto `merge` y el borrado de la ventana, lo recoge el spike 0b de P1 sobre `sessions` actual sin construir Gold dos veces. Condición: P1 depende de la Ruling "Bronze rebuild exception (2026-11-23)", de un solo uso; si el backfill hubiera que repetirlo tras consumirla, o si el owner prefiere no ejercerla, P2 pasa a ser la opción.

## Decision

**Elegida: Proposal 1** (recrear Bronze y Silver con `rebuild_tables`, A completo y después B, con spike 0b de dbt-athena). Owner javiladino, 2026-11-23. Se apoya en la Ruling "Bronze rebuild exception (2026-11-23)" de `context.md`. Las Open Questions abiertas (C1–C3, P1-1, P1-2, P1-4, P1-5) pasan al Plan con las recomendaciones de este documento salvo que el owner diga otra cosa.
