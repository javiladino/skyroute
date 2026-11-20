---
type: Proposal
topic: bronze-silver
date: 2026-11-20
---

# bronze-silver: Propuestas de solución

> **Tarea:** implementar la Fase 3 (Bronze y Silver con Spark + Iceberg) dentro del Ruling Research decisions.
> **Fecha:** 2026-11-20
> **Research source:** `docs/design/bronze-silver/working/research.md`; C1, C2, C3, C4, C5, T1–T14. Restricciones vinculantes: `docs/design/bronze-silver/context.md` § Rulings, "Research decisions".
> **Revisión:** 1 ronda (adversarial-reviewer, NEEDS-REVISION) más una comprobación de coherencia con el Ruling (NEEDS-REVISION), hallazgos aplicados 2026-11-20.

## Context

**Request:** construir los jobs PySpark de Bronze, Silver y mantenimiento, con tests, sobre Iceberg en Glue Catalog, más los cambios de generador, permisos e infra que necesitan, de forma que relanzar un día dé exactamente el mismo resultado.

**Success criteria** (README § Fases, verbatim): "Jobs PySpark con tests, MERGE, sesionización, SCD2, conversión de divisas. Hecho cuando relanzar un día da exactamente el mismo resultado."

Desglosado en filas de la tabla de recomendación: (1) jobs PySpark con tests, (2) MERGE, (3) sesionización, (4) SCD2, (5) conversión de divisas, (6) relanzar un día da exactamente el mismo resultado.

**Restricciones fijas (todas las propuestas las cumplen; no varían entre ellas):**

- Conventions Table format, Medallion layers, Compute split, Region, No hourly-billed resources, IaC only, Apply gate, Idempotency y Bootstrap identity (`docs/design/CONTEXT.md` § Conventions), citadas por nombre.
- Ruling Research decisions, en bloque: generador cambiado dentro de la fase y backfill posterior; Spark local a diario y Glue 5 Flex solo en demos, con `--run-date` y catálogo por parámetro; rol `skyroute-<env>-local-data` con MFA; Bronze con reemplazo de partición por `_ingest_date` y Silver CoW; checks WAP propios con reglas en YAML; `_ingested_at` y `_batch_id` derivados de la fecha lógica; export de Reservas a `landing/bookings/` leyendo `bookings_history` (trigger de Postgres, varias versiones por reserva y día); relanzar un día es independiente del orden (relanzar D tras D+5 deja Silver idéntico a una ejecución en orden); FX por reserva con el tipo del día de `created_at`, guardando tipo aplicado y divisa original; workgroup Athena `skyroute-<env>` con corte de 100 MB; PR de `bootstrap/` primero; histórico ingerido en Bronze antes de 30 días; FX del BCE a `landing/fx/`; HMAC del email en Silver con clave en SSM estándar; budget en 10 USD y demos Glue a mano.
- Hoy no hay ningún recurso Glue ni Athena ni código Spark (research Summary, C4 "Glue/Athena").
- Ninguna boundary ni rol de CI permite Glue, Athena, `s3:GetObject` en el bucket de datos ni `PassRole` a Glue (T4, C4 "Boundary de workload", "ci-boundary", "ci-apply-dev/prod"). De ahí la PR de `bootstrap/` primero.
- El clickstream no tiene sesiones de varios eventos (C1 "Sesiones y clientes", T12) y las Reservas tienen una sola versión hasta el trigger de `bookings_history` (C2 "Estados y `updated_at`", T2): sesionización y SCD2 dependen del cambio de generador.
- Duplicados exactos solo dentro del mismo archivo (C1 "Duplicados"); tardíos de hasta 72 h con `event_ts` anterior al slot de llegada (C1 "Tardíos"). Silver debe tolerar eventos de un día lógico repartidos en hasta 4 `_ingest_date`.
- El lifecycle de `landing/` cuenta desde la creación del objeto (C4 "Bucket", T1): un backfill regenerado caduca entero unos 30 días después de escribirse.
- Volumen mínimo: unos 178 KB/día en prod (C1 "Volumen", T6). Cualquier consulta Athena paga el mínimo de 10 MB (aws-researcher, 2026-11-20).
- dev tiene el schedule `DISABLED` (T7); no consta si dev tiene datos.
- Versiones de Python dispersas y sin dependencias declaradas (T9, C5).

**Hechos de aws-researcher (2026-11-20):**

- MFA con `aws login`: **no confirmado** en la documentación de AWS. **Acción del Ruling pendiente que Plan no puede saltar** (Ruling "Credenciales en local"): el owner corre `aws sts get-caller-identity --profile skyroute-dev-local-data` antes de Plan. Patrón documentado: perfil CLI con `role_arn` + `source_profile` + `mfa_serial` y trust policy con `Bool aws:MultiFactorAuthPresent = true`. Configuración propuesta, sin verificar: perfil `skyroute-dev-login` con `login_session` y perfil hijo `skyroute-dev-local-data` con `role_arn`, `source_profile = skyroute-dev-login`, `mfa_serial` y `region = eu-west-3`. El owner lo prueba una vez con `aws sts get-caller-identity --profile skyroute-dev-local-data`; alternativa: `aws sts get-session-token` con MFA. `~/.aws/config` es configuración local del cliente, no IaC.
- Glue Flex: 0,29 USD/DPU-h (tarifa de ejemplo; **eu-west-3 sin confirmar**), por segundo con mínimo de 1 min (Glue 2.0+, inferido para 5.0). Cada job de demo cuesta 3 min × 2 DPU × 0,29 ≈ 0,029 USD; el número de jobs depende de la propuesta (Coste de cada una). **Acción del Ruling pendiente antes de Plan** (Ruling "Budget" pedía a Propose confirmar el precio): Propose no lo confirmó; el owner lo comprueba con el AWS Pricing Calculator (o el `aws pricing get-products` del research § No comprobado).

**Supuestos explícitos (añadidos en la revisión):**

- Regenerar el histórico reescribe los objetos de `landing/` y reinicia su reloj de 30 días (C4 "Bucket", T1). El histórico actual probablemente caduca antes de la regeneración; es aceptable porque el generador es determinista.
- El rol `skyroute-<env>-local-data` vive bajo el path `/workload/` y lleva la boundary `workload-boundary-<env>`, como el resto de roles de workload.
- Spark local fija `AWS_REGION=eu-west-3` (Convention Region).

**Estado de IAM verificado en el repo (2026-11-20):**

- Ningún archivo de `infra/terraform/bootstrap/*.tf` contiene acciones `glue:`, `athena:`, `ssm:` ni `kms:` (Grep sin coincidencias).
- `infra/terraform/bootstrap/ci_roles.tf:63`: `pass_role_services = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]`.
- `infra/terraform/bootstrap/ci_apply_dev.tf:160-168` (y `ci_apply_prod.tf:166`): `DenyPassRoleWrongService` deniega `iam:PassRole` con `StringNotEquals iam:PassedToService = local.pass_role_services`; sin añadir `glue.amazonaws.com` a esa lista, el PassRole al rol de Glue queda denegado. La misma lista se usa en `ci_roles.tf:251`, `:291`, `:558`.
- Proveedor: `hashicorp/aws ~> 6.73` en `bootstrap/versions.tf:7`, `modules/generator-landing/versions.tf:7`, `envs/{dev,prod}/backend.tf:7`; lock en 6.73.0.
- Athena: mínimo de 10 MB por consulta verificado; 5 USD/TB (París sin confirmar); las consultas canceladas se cobran.
- SSM SecureString estándar: gratis; clave por defecto `aws/ssm` (no admite key policy propia; una CMK tiene coste mensual). Precio de peticiones KMS sin confirmar.

**Lo que el research no cubre** (va a Open Questions de cada propuesta): versión exacta de Spark/Iceberg de Glue 5, forma del esquema de Reservas con historial de estados, definición de sesión que espera Gold, y si la Fase 3 lee dev o prod (T7).

## Base común

Lo que cualquier propuesta hace igual, porque lo fija el Ruling. No se puntúa en la tabla.

| Componente | Cambio |
|------------|--------|
| PR 1, `infra/terraform/bootstrap/` | Modified, con todo lo que necesitan las PRs del módulo `lakehouse` y del Glue job (C4 "ci-apply-dev/prod", T4; estado verificado arriba). **Boundary de workload** (`workload_boundary_{dev,prod}.tf`): `s3:GetObject`/`ListBucket`/`PutObject` en el bucket de datos; `s3:DeleteObject` acotado por prefijo a `bronze/`, `silver/` y `athena-results/` (no `landing/`); `s3:GetObject` en `scripts/` para el rol `glue-job`; Glue Catalog sobre `skyroute_*`; Athena sobre `skyroute-<env>`; `ssm:GetParameter` del parámetro HMAC. **ci-plan** (`ci_roles.tf`): lectura de Glue (`glue:Get*`), Athena (`athena:GetWorkGroup`, `ListTagsForResource`), SSM (`ssm:DescribeParameters`, `GetParameter`, `ListTagsForResource`) y KMS (`kms:DescribeKey` de `aws/ssm`) para que `plan` refresque los recursos nuevos. **ci-apply** (`ci_apply_{dev,prod}.tf`): `glue:*Database*`/`*Table*`/`*Job*`, `athena:*WorkGroup*`, `ssm:PutParameter`/`GetParameter`/`DeleteParameter`/`AddTagsToResource`/`ListTagsForResource` acotadas por nombre, `s3:PutObject` en `scripts/` para subir el script del Glue job, y `iam:PassRole` a `skyroute-<env>-glue-job`; añadir `glue.amazonaws.com` a `pass_role_services` (`ci_roles.tf:63`), porque si no `DenyPassRoleWrongService` (`ci_apply_dev.tf:160`) lo deniega. La revisa security-reviewer y la aplica el owner (Apply gate). |
| PR 2, módulo nuevo `infra/terraform/modules/lakehouse/` (nombre por confirmar) | New: bases Glue `skyroute_{bronze,silver,ops}` (Gold queda para su fase), workgroup `skyroute-<env>` con `enforce_workgroup_configuration`, `bytes_scanned_cutoff_per_query = 100 MB` y salida en `athena-results/`; regla de lifecycle de 7 días en `athena-results/` (en `bucket.tf` del módulo actual o en el nuevo; ver Open Questions); rol `skyroute-<env>-local-data` (trust a `skyroute-dev` con `aws:MultiFactorAuthPresent`, `max_session_duration = 3600`); rol `skyroute-<env>-glue-job`; parámetro SSM `SecureString` con la clave HMAC (valor fuera del state: ver Open Questions). |
| `~/.aws/config` del owner | Local, no IaC: perfiles `skyroute-dev-login` y `skyroute-dev-local-data` según aws-researcher. |
| `spark/jobs/{bronze,silver,maintenance}/`, `spark/tests/` | New: jobs con `--run-date` y `--catalog-*` por parámetro; checks WAP con reglas en `spark/checks/*.yaml` (ruta por confirmar); `expire_snapshots` y `rewrite_data_files` en `maintenance/`. |
| `generators/` | Modified: sesiones por cliente con compras enlazadas, Reservas con cambios de estado (`ON CONFLICT … DO UPDATE` en `bookings`), export diario `landing/bookings/ingest_date=…/part.json.gz`, tarea FX a `landing/fx/`. |
| Postgres local (DDL en `generators/`, ruta por confirmar en Plan) | New (Ruling "Reservas a `landing/`", enmienda de Propose): tabla `bookings_history (history_id bigserial PRIMARY KEY, booking_id, status, …columnas de bookings…, changed_at timestamptz NOT NULL)` y trigger `AFTER INSERT OR UPDATE ON bookings FOR EACH ROW` que inserta una fila por cambio, con `changed_at = NEW.updated_at` (fecha lógica del generador, nunca `now()`, Convention Idempotency). El export de D selecciona `bookings_history WHERE changed_at` dentro del día lógico D (`[D 00:00, D+1 00:00)` UTC) `ORDER BY history_id`; caben varias versiones por reserva y día. Que `history_id` sea reproducible al regenerar exige que el backfill recree `bookings_history` desde vacío y en orden determinista (Open Question compartida 3). |
| `AGENTS.md` § Comandos | Modified: lint Python y tests Spark dejan de ser `TODO` (respetando AGENTS.md budget). |

Columnas técnicas de Bronze en todas: `_ingest_date` = `run_date`; `_ingested_at` = `run_date` 00:00 UTC + slot × 15 min (para fuentes diarias, slot 0); `_batch_id` = hash(`run_date`, `_source_file`); `_source_file` = clave S3. Ninguna sale del reloj (T13).

Clave de orden de las Reservas en todas: Bronze conserva `history_id` (secuencia de `bookings_history`) y `changed_at`. Toda ordenación de versiones usa `(changed_at, history_id)`, con `history_id` como desempate; la clave de versión SCD2 es `(booking_id, history_id)`, única por construcción. Ni `(booking_id, valid_from)` ni `_batch_id` son únicos con varias versiones por día (un lote tiene un solo `_batch_id`; dos cambios pueden compartir `updated_at`).

Relanzar en todas (Ruling "Relanzar un día", independiente del orden): ningún job Silver corta su entrada por `_ingest_date ≤ run_date`; relanzar D en cualquier momento, incluso después de D+5, debe dejar Silver idéntico a una ejecución en orden.

Escritura de Bronze en todas: el `INSERT OVERWRITE` dinámico no vacía una partición si el relanzamiento no trae archivos. Por eso el job falla si no encuentra archivos de entrada para `run_date` (en vez de terminar sin escribir); el borrado explicito de la partición queda solo como alternativa si el owner quiere admitir días vacíos.

WAP en todas: las tablas Silver llevan la propiedad `write.wap.enabled=true`; el job escribe en la rama con `spark.wap.branch`, pasa los checks YAML y publica con `CALL <catalog>.system.fast_forward('<tabla>', 'main', '<rama>')`.

## Proposal 1: Capa a capa, con la imagen de Glue 5 en local

### Overview

Primero el generador y la regeneración del histórico, luego todo Bronze (las tres fuentes) con su backfill, y después Silver. Spark local corre en la imagen pública de Glue 5 (`public.ecr.aws/glue/aws-glue-libs`, etiqueta de 5.0), así que local y demo usan el mismo Spark, Iceberg y Python. La sesión la asigna el generador y Silver la valida; SCD2 se hace con un único MERGE sobre una staging "unión" (filas que cierran la versión vigente y filas que la abren).

Motivación: el reloj de 30 días (T1, Ruling "Histórico") presiona más que Silver; tener Bronze completo pronto quita ese riesgo. La paridad de motores responde a "iguales en los dos motores" del Ruling "Dónde corre Spark".

### Orden de PRs

1. `bootstrap/` (fijo).
2. Módulo `lakehouse` (bases, workgroup, roles, SSM).
3. Generador: sesiones, estados, export de Reservas, FX; tests en `generators/tests`.
4. Regeneración del histórico (backfill de 182 días con el generador nuevo) + export de Reservas + FX del mismo rango. Operación del owner.
5. Bronze: `spark/jobs/bronze/{clickstream,bookings,fx}.py` + backfill de Bronze, dentro de los 30 días desde el paso 4.
6. Silver: `events`, `sessions`, `bookings_scd2`, `fx_daily`, `bookings_eur`.
7. Mantenimiento y demo Glue (Glue job definido en Terraform, lanzado a mano).

### Modelo de Silver

- `silver.events`: dedup por `event_id` (MERGE `WHEN NOT MATCHED INSERT`), tipado, email → HMAC. Partición por `days(event_ts)`; un run de `run_date` lee la partición `_ingest_date = run_date` y hace MERGE por `event_id`, de modo que un tardío entra en el día de `event_ts` (C1 "Tardíos").
- `silver.sessions`: agrupa por `session_id` del generador; métricas (inicio, fin, nº eventos, `converted`, `booking_id`). Se recalculan las sesiones tocadas por el lote leyendo **todo** `silver.events` de esos `session_id`, sin corte por `_ingest_date` (Ruling "Relanzar un día"), y se escriben con MERGE por `session_id`. Check WAP: una sesión = un `customer_id`.
- `silver.bookings_scd2`: columnas `history_id`, `valid_from`, `valid_to`, `is_current`, `row_hash`. Como el export trae varias versiones por reserva y día (Ruling, `bookings_history`), la staging **pre-expande** el lote: ordena las versiones de cada `booking_id` por `(changed_at, history_id)` y calcula su `valid_to` interno con `lead()`; solo la última del lote queda candidata a `is_current`. Staging = (una fila por `booking_id` con `merge_key = booking_id` y `t0` = `changed_at` de su primera versión del lote, para cerrar) ∪ (todas las versiones del lote con `merge_key = NULL`, para insertar). Condición: `ON target.booking_id = s.merge_key AND target.is_current AND target.valid_from < s.t0`; `WHEN MATCHED THEN UPDATE SET valid_to = s.t0, is_current = false`; `WHEN NOT MATCHED THEN INSERT`. Con una sola fila de cierre por `booking_id` el MERGE no tiene coincidencias múltiples. La guarda `target.valid_from < s.t0` impide que relanzar D tras D+1 cierre la versión de D+1 con `valid_to < valid_from`. La guarda de inserción se materializa en la staging (anti-join contra target por `(booking_id, history_id)` antes del MERGE), porque la mitad con `merge_key = NULL` nunca coincide. Tras el MERGE, un paso acotado a los `booking_id` del lote deja `is_current` solo en la versión con mayor `(valid_from, history_id)` y fija `valid_to` de cada versión al `valid_from` de la siguiente, de modo que relanzar D tras D+5 da la misma tabla que en orden. `valid_from = changed_at`, nunca la hora del run.
- `silver.fx_daily`: una fila por (día natural, divisa), arrastrando el último día hábil del BCE (Ruling "Tipos de cambio"); reemplazo por fecha. Si falta el tipo del día y no hay día hábil anterior en Bronze, el check WAP falla y no se publica.
- `silver.bookings_eur`: join de la versión vigente con `fx_daily` por `date(created_at)` (Ruling "Tipo de cambio por reserva"); guarda `currency` original, `fx_rate_applied` y `amount_eur` en `decimal(12,2)` con redondeo `HALF_EVEN` (redondeo por confirmar).

### Key Changes

| Component | Change |
|-----------|--------|
| `docker/spark/compose.yml` | New: servicio sobre la imagen de Glue 5; monta `spark/` y pasa `AWS_*` temporales del perfil `skyroute-dev-local-data` |
| `spark/jobs/bronze/*.py` | New: 3 jobs, `INSERT OVERWRITE` dinámico por `_ingest_date` |
| `spark/jobs/silver/*.py` | New: 5 jobs, CoW, MERGE en `events`, `sessions`, `bookings_scd2` |
| `spark/jobs/maintenance/*.py` | New: `expire_snapshots`, `rewrite_data_files` |
| `spark/lib/` | New: parseo de argumentos, sesión Spark con el catálogo por parámetro, motor de checks YAML, WAP con ramas Iceberg (`spark.wap.branch`) |
| `spark/tests/` | New: pytest con catálogo Iceberg `hadoop` en un directorio temporal dentro del contenedor; ningún test toca AWS |
| `generators/ota/{model,clickstream}.py`, `seed_postgres.py` | Modified: sesiones por cliente, estados, `ON CONFLICT … DO UPDATE` |
| `generators/ota/export_bookings.py`, `generators/fx/` | New |
| `infra/terraform/modules/lakehouse/glue_job.tf` | New (PR 7): definiciones de Glue job sin trigger |

### Trade-offs

| Benefit | Risk |
|---------|------|
| Bronze completo al cerrar la PR 5: el histórico regenerado queda a salvo antes del lifecycle (T1, Ruling "Histórico") | Silver llega tarde; los errores de modelo (sesión, SCD2) aparecen cuando el histórico ya está en Bronze y obligan a reprocesar Silver entero (barato: unos 5 MB, T6) |
| Misma imagen en local y en Glue: un único juego de versiones de Spark/Iceberg/Python (Ruling "Dónde corre Spark"; resuelve T9 para Spark) | La imagen de Glue es grande y su arranque es lento para pytest; la versión exacta de Spark e Iceberg de Glue 5 no está en el research (Open Question) |
| Sesión del generador: Silver es simple y el check "una sesión, un cliente" es directo | Silver depende de que el generador asigne bien la sesión; no se demuestra sesionización "de verdad" por inactividad, que es lo que un revisor de portfolio espera ver (criterio 3, parcial) |
| MERGE de SCD2 con staging unión: un solo MERGE por run | Varias versiones por reserva y día son el caso normal (`bookings_history`): sin la pre-expansión y una fila de cierre por `booking_id`, el MERGE falla por coincidencias múltiples (defecto real, no hipotético); además necesita las guardas `valid_from < t0` y anti-join por `history_id`, y un paso de recálculo de `valid_to`/`is_current` acotado, que deja dos snapshots por run (Validation 4) |

### Coste

- Spark local: 0 USD. Glue Catalog: sin confirmar para el volumen del proyecto (decenas de tablas y particiones; en el research no hay precio).
- Demo Glue: unos 0,23 USD (8 jobs: 3 Bronze + 5 Silver; 8 × 3 min × 2 DPU × 0,29 USD/DPU-h, tarifa de ejemplo de aws-researcher, eu-west-3 sin confirmar).
- Athena: cada consulta paga 10 MB mínimo (≈ 0,00005 USD a 5 USD/TB, tarifa sin confirmar en París).
- SSM estándar: 0 USD con `aws/ssm`. S3: del orden de MB.

### Risks

- La regeneración (PR 4) cambia en prod los bytes de claves ya escritas: el schedule de prod sigue escribiendo días nuevos con el generador vigente hasta que se despliega la PR 3 (C4 "OIDC", `schedule_enabled = true` en prod).
- El backfill de Bronze tiene que correr antes de ~30 días desde la regeneración; si la PR 5 se retrasa, se regenera otra vez (determinista, así que el coste es solo de tiempo).

### Validation

1. `pytest generators/tests -q`: nuevo test que, para un `run_date` fijo, comprueba que existe al menos una sesión con ≥ 2 eventos que acaba en `purchase` con el `booking_id` de una reserva, y que alguna reserva tiene ≥ 2 versiones con `updated_at` creciente.
2. `docker compose -f docker/spark/compose.yml run --rm spark pytest spark/tests -q`.
3. Test de idempotencia por job: ejecutar el job dos veces con el mismo `--run-date` sobre el catálogo temporal y comparar `SELECT * ORDER BY` de la tabla destino y el `count` de filas; deben ser iguales (criterio 6).
4. Test SCD2: (a) relanzar D dos veces y asertar el mismo número de filas por `booking_id` y una sola `is_current = true`; (b) lote con dos versiones del mismo `booking_id` en un día (también con el mismo `changed_at`, desempate por `history_id`): el MERGE no falla, una sola `is_current = true` y `valid_to` de la anterior = `valid_from` de la nueva; (c) ejecutar D..D+5, relanzar D y asertar igualdad fila a fila con la ejecución en orden y ninguna fila con `valid_to < valid_from`.
5. Test FX: sábado sin publicación → `fx_daily` del sábado = viernes; día sin ningún tipo previo → el check falla y la rama WAP no se publica.
6. Test de tardío: evento con `_ingest_date = D+2` y `event_ts` en D aparece en la partición D de `silver.events` y relanzar D+2 no lo duplica; relanzar D después de D+5 deja `silver.sessions` igual fila a fila que en orden.
7. Owner: `aws sts get-caller-identity --profile skyroute-dev-local-data` devuelve el ARN del rol asumido.

### Open Questions

1. Versión de Spark, Iceberg y Python de la imagen de Glue 5 y si incluye `iceberg-aws-bundle`: si no coincide con lo que se publica en Glue 5, la paridad se pierde.
2. ¿La sesión la asigna el generador o la deriva Silver? Afecta a lo que Gold entiende por sesión.
3. ¿Qué entorno lee la Fase 3, dev o prod (T7)? Si es dev, el histórico hay que generarlo en dev con un backfill de la Lambda.

## Proposal 2: Por tabla de extremo a extremo, con PySpark de pip

### Overview

Cortes verticales: cada PR lleva una fuente de landing hasta Silver, con sus tests. Orden: Reservas (SCD2, la más pequeña: 120 filas/día, C2), luego FX, luego clickstream (eventos y sesiones). Spark local es `pyspark` de pip con los jars `iceberg-spark-runtime` e `iceberg-aws-bundle` fijados en un `requirements` y una imagen ligera propia; Glue 5 se usa solo para la demo. La sesión la deriva Silver por inactividad (30 min por `customer_id`, ordenado por `event_ts`, desempate por `event_id`), sin usar el `session_id` del generador salvo como check.

Motivación: el criterio de la fase es por capacidades (MERGE, sesionización, SCD2, divisas); cada corte cierra una de ellas y se puede revisar entera. La sesionización por ventana es la que el criterio 3 pide de verdad (T12).

### Orden de PRs y del histórico

1. `bootstrap/` (fijo). 2. Módulo `lakehouse`.
3. Generador completo (sesiones, estados, export, FX), en una sola PR para que el modelo común `ota.model._bookings` (research "Merge points") cambie una vez.
4. Regeneración del histórico por el owner, y en la misma semana un job Bronze **genérico** (`spark/jobs/bronze/ingest.py --source {clickstream,bookings,fx}`) que solo copia payload + columnas técnicas, para asegurar el histórico (Ruling "Histórico") antes de que exista Silver.
5. Corte Reservas: `silver.bookings_scd2` + `bookings_current`.
6. Corte FX: `silver.fx_daily` + `bookings_eur`.
7. Corte clickstream: `silver.events` + `silver.sessions`.
8. Mantenimiento y demo Glue.

### Modelo de Silver

- `bookings_scd2`: ordena las versiones del lote por `booking_id` y `(changed_at, history_id)`, construye los intervalos `[valid_from, valid_to)` con `lead()`, y aplica un MERGE por `(booking_id, history_id)` (única; Base común "Clave de orden") que inserta las versiones del lote que no existen. El cierre de la versión previa es un paso separado y acotado: sea `v0` el `valid_from` de la primera versión del lote para ese `booking_id`; se cierran (`valid_to = v0`, `is_current = false`) solo las filas con `valid_from < v0` y `valid_to IS NULL OR valid_to > v0`. Así relanzar D tras D+1 no cierra la versión de D+1 (su `valid_from` es mayor que `v0`) ni deja `valid_to < valid_from`; la última versión del lote solo queda `is_current` si no hay en target una versión posterior por `(valid_from, history_id)`, y su `valid_to` toma el `valid_from` de esa versión posterior si existe.
- `bookings_current`: una fila por `booking_id` con la última versión, MERGE `WHEN MATCHED AND (s.changed_at, s.history_id) > (t.changed_at, t.history_id) THEN UPDATE`, `WHEN NOT MATCHED THEN INSERT`; relanzar D tras D+5 no la retrocede.
- `sessions`: el día D se recalcula leyendo `silver.events` de `[D-3, D+1]` por `event_ts`, **sin corte por `_ingest_date`** (Ruling "Relanzar un día"). Como los tardíos llegan en ≤ 72 h (C1), un relanzamiento de D después de D+3 ve las mismas entradas para esa ventana que la ejecución en orden del último día que la toca, así que el resultado final es idéntico. Se escribe por reemplazo de la partición del día de inicio dentro de la ventana (las sesiones que empiezan en `[D-3, D]`), no por MERGE con clave: `session_key = hash(customer_id, primer event_id)` cambia cuando un tardío pasa a ser el primer evento, y un MERGE dejaría la sesión antigua huérfana. Alternativa equivalente: MERGE con `WHEN NOT MATCHED BY SOURCE AND target.session_start_date BETWEEN D-3 AND D THEN DELETE`. Una sesión que cruza medianoche pertenece al día de su primer evento.
- `fx_daily` y `bookings_eur`: igual que en la Propuesta 1, con el tipo del día de `created_at` (Ruling "Tipo de cambio por reserva"); Silver guarda `fx_rate_applied` y la divisa original.

### Key Changes

| Component | Change |
|-----------|--------|
| `spark/requirements.txt` (o `pyproject.toml`), `docker/spark/Dockerfile` | New: `pyspark` y jars de Iceberg fijados a la versión de Glue 5 |
| `spark/jobs/bronze/ingest.py` | New: un job parametrizado por fuente |
| `spark/jobs/silver/{bookings_scd2,bookings_current,fx_daily,bookings_eur,events,sessions}.py` | New: 6 jobs Silver (más 1 Bronze genérico) |
| `spark/tests/` | New: `pytest` directo en el host o en la imagen ligera, catálogo `hadoop` temporal |
| `.github/workflows/spark-tests.yml` | New (opcional): pytest de `spark/tests` y `generators/tests` en PR; hoy ningún workflow corre pytest (C5) |
| Resto | Como en Base común |

### Trade-offs

| Benefit | Risk |
|---------|------|
| Cada PR demuestra un criterio completo (SCD2, FX, sesión) y es revisable de punta a punta | Más PRs (8) y más ciclos de gate del owner |
| Sesionización por inactividad: el criterio 3 se cumple de forma independiente del generador; el `session_id` del generador sirve de oráculo en los tests | Relanzar D reescribe las particiones `[D-3, D]`; sin corte por `_ingest_date`, relanzar D antes de que pasen 72 h ve menos tardíos que después, pero el relanzamiento posterior de D+1..D+3 los incorpora; la igualdad con la ejecución en orden depende de que el límite de 72 h (C1) se cumpla siempre (Validation 3) |
| `pyspark` de pip arranca rápido y permite CI barata con pytest (C5: hoy no hay CI de Python) | Riesgo de deriva frente a Glue 5 si las versiones no se fijan igual; la demo puede fallar por una diferencia de versión que el local no detecta |
| Bronze genérico asegura el histórico en una PR pequeña antes de Silver (T1) | El job genérico puede necesitar reescritura cuando aparezcan diferencias por fuente (CSV/JSON, esquema variable de C1) |
| SCD2 con clave `(booking_id, history_id)`: relanzar no duplica versiones, aunque dos cambios compartan `changed_at` | Depende de que `history_id` sea reproducible al regenerar `bookings_history` (OQ compartida 3); si la secuencia cambia entre regeneraciones, la clave cambia |

### Coste

Demo Glue: unos 0,20 USD (7 jobs: 1 Bronze genérico + 6 Silver; 7 × 3 min × 2 DPU × 0,29 USD/DPU-h, eu-west-3 sin confirmar). Resto igual que la Propuesta 1. Si se añade `spark-tests.yml`, los minutos de GitHub Actions en repo público no tienen coste (no comprobado en el research).

### Risks

- Deriva de versiones local/Glue (ver Trade-offs).
- Ocho PRs alargan la fase; el histórico está a salvo desde la PR 4, así que el retraso no amenaza el lifecycle.

### Validation

1. `pytest generators/tests -q` con los tests de la Propuesta 1 (Validation 1) más: dos regeneraciones del mismo rango producen `bookings_history` idéntica, `history_id` incluido.
2. `pytest spark/tests -q` (en el host con el entorno de `spark/requirements.txt`).
3. Idempotencia de sesiones: ejecutar D dos veces e igualar fila a fila; ejecutar D, D+1, D, D+1 y asertar igualdad con D, D+1; ejecutar D..D+5 y después D, y asertar igualdad fila a fila con la ejecución en orden; con un tardío que pasa a ser primer evento, asertar que no queda ninguna sesión huérfana.
4. Sesión: secuencia sintética con hueco de 31 min → 2 sesiones; con 29 min → 1; asertar que coincide con el `session_id` del generador en un día generado.
5. SCD2: relanzar D (sin duplicados, una `is_current` por `booking_id`); relanzar D tras D+1 (la versión de D+1 sigue `is_current`, ninguna fila con `valid_to < valid_from`); lote con dos versiones del mismo `booking_id` y el mismo `changed_at` (dos filas, desempate por `history_id`); `bookings_current` tras D..D+5 y relanzar D sigue en la versión de D+5. FX: como Validation 5 de la Propuesta 1.
6. Demo Glue: el owner lanza el job `skyroute-dev-silver-bookings_eur` (nombre `skyroute-<env>-silver-<tabla>`, a fijar en Plan) y compara `SELECT count(*), sum(amount_eur)` en Athena con el resultado local del mismo `run_date`.

### Open Questions

1. Umbral de inactividad (30 min es el estándar de analítica web, no un dato del research) y regla de sesión que cruza medianoche.
2. ¿Se añade CI de pytest en esta fase? No está en el Ruling; toca `.github/workflows/` (C5).
3. ¿Sesiones por reemplazo de partición del día de inicio o por MERGE con `NOT MATCHED BY SOURCE DELETE`? Las dos son idempotentes; la segunda cuenta como MERGE para el criterio 2.

## Proposal 3: Silver recalculado desde Bronze, MERGE solo donde hay estado

### Overview

Aprovecha el volumen mínimo (unos 5 MB en 30 días, 120 reservas/día; C1 "Volumen", C2, T6): las tablas derivadas de Silver (`sessions`, `bookings_scd2`, `fx_daily`) se recalculan enteras desde Bronze en cada run con funciones de ventana y se escriben con reemplazo; MERGE queda solo en `silver.events` (dedup por `event_id`) y `silver.bookings_current` (upsert por `booking_id`). Dos runtimes: `pyspark` de pip para pytest y la imagen de Glue 5 para un ensayo previo a cada demo.

Motivación: con historia completa en Bronze (Ruling "Histórico"), recalcular es determinista por construcción y elimina la clase de bugs de MERGE incremental (orden de versiones, tardíos que cruzan días).

### Orden de PRs y del histórico

Como la Propuesta 2 en los pasos 1–4 (bootstrap, módulo, generador, regeneración + Bronze genérico). Después una sola PR de Silver con las seis tablas (`events`, `sessions`, `bookings_scd2`, `bookings_current`, `fx_daily`, `bookings_eur`) y otra de mantenimiento y demo (6 PRs en total).

### Modelo de Silver

Salida (a), la única compatible con el Ruling "Relanzar un día": las derivadas recalculan sobre todo Bronze, sin corte `_ingest_date ≤ run_date`; relanzar D no cambia el estado actual y todas las tablas quedan en el último día ingerido.

- `bookings_scd2`: `lead(changed_at) over (partition by booking_id order by changed_at, history_id)` sobre todas las versiones de Bronze; se escribe con `INSERT OVERWRITE` de tabla completa (requiere enmienda de Idempotency, Open Question 1).
- `sessions`: inactividad de 30 min por `customer_id` sobre `silver.events` con `event_ts` en `[D-3, D+1]`, sin corte por `_ingest_date`, recalculada por partición de día de inicio para `[D-3, D]` con reemplazo de partición.
- `fx_daily`: recalculada entera desde Bronze FX (unas 30 filas/día hábil).
- MERGE: `events` y `bookings_current`, que son los dos únicos puntos con estado acumulado. `bookings_current` es condicional: `WHEN MATCHED AND (s.changed_at, s.history_id) > (t.changed_at, t.history_id) THEN UPDATE`, de modo que relanzar D tras D+5 no la retrocede y queda coherente con `bookings_scd2`.
- `bookings_eur`: como la Propuesta 1 (tipo del día de `created_at`, tipo aplicado y divisa original).

### Key Changes

| Component | Change |
|-----------|--------|
| `spark/requirements.txt`, `docker/spark/compose.yml` (dos servicios: `test` ligero y `glue` con la imagen de Glue 5) | New |
| `spark/jobs/bronze/ingest.py` | New: 1 job genérico, como la Propuesta 2 |
| `spark/jobs/silver/*.py` | New: 6 jobs (3 de recálculo, 2 de MERGE, 1 de conversión) |
| `spark/tests/` | New: tests de recálculo con historias sintéticas |
| Resto | Como en Base común |

### Trade-offs

| Benefit | Risk |
|---------|------|
| Idempotencia e independencia del orden triviales en las derivadas: la salida depende solo del contenido de Bronze (criterio 6, Ruling "Relanzar un día") | El `INSERT OVERWRITE` de tabla completa no es MERGE ni reemplazo de partición: exige enmienda de la Convention Idempotency (Open Question 1) |
| Menos código de MERGE y menos casos borde (orden de versiones, colisiones de `changed_at`) | MERGE aparece en dos tablas simples; el SCD2 "vía MERGE" que pide el brief queda sustituido por recálculo; el criterio 2 se cumple, pero el SCD2 no demuestra MERGE |
| Escala con el volumen de hoy sin coste: reescribir unos MB por run en local cuesta 0 USD | No escala al volumen del blueprint (50.000–200.000 eventos/día, T6) ni a 182 días en Glue; cada snapshot CoW reescribe la tabla entera y crece el almacenamiento hasta que `expire_snapshots` lo limpia |
| Dos runtimes: tests rápidos y ensayo con paridad antes de demo | Dos imágenes que mantener |

### Coste

Igual en AWS que las otras. Demo Glue: al menos 0,20 USD (7 jobs: 1 Bronze + 6 Silver; 7 × 3 min × 2 DPU × 0,29 USD/DPU-h, eu-west-3 sin confirmar); el recálculo completo puede alargar los jobs Silver por encima de 3 min (sin medir) y subir esa cifra.

### Risks

- `INSERT OVERWRITE` de tabla entera no es "MERGE o reemplazo de partición" según la Convention Idempotency: la propuesta requiere una enmienda del owner (Open Question 1).
- Snapshots CoW de tabla completa en cada run: `expire_snapshots` pasa a ser imprescindible desde el primer día.

### Validation

1. `pytest spark/tests -q`.
2. Recálculo: para una historia sintética de 5 días, ejecutar D1..D5 y luego D5 otra vez, y también D1 otra vez; asertar igualdad fila a fila de `bookings_scd2`, `bookings_current` y `sessions` con la ejecución en orden.
3. Equivalencia: asertar que la tabla SCD2 tras D1..D5 es igual a la de un único run con D5 (prueba de que no depende del camino); incluir dos versiones con el mismo `changed_at` (desempate por `history_id`).
4. Tamaño: tras 182 días de backfill, `SELECT count(*) FROM skyroute_silver.bookings_scd2.snapshots` antes y después de `maintenance/expire_snapshots.py`.
5. Demo y FX: como Validation 5 y 6 de las Propuestas 1 y 2.

### Open Questions

1. Enmienda requerida de la Convention Idempotency para admitir el overwrite de tabla completa en `bookings_scd2` y `fx_daily`; sin ella esta propuesta no puede pasar a Plan. Decisión del owner.
2. ¿Un SCD2 sin MERGE es aceptable para el criterio de la fase?

## Open Questions compartidas

1. **MFA con `aws login` (acción del Ruling "Credenciales en local" que Plan no puede saltar):** no confirmado (aws-researcher). El owner corre `aws sts get-caller-identity --profile skyroute-dev-local-data` antes de Plan. Si `get-caller-identity --profile skyroute-dev-local-data` falla, la alternativa `get-session-token` con MFA mantiene el Ruling; si ninguna funciona, el Ruling "Credenciales en local" necesita enmienda del owner.
2. **Clave HMAC fuera del state:** si Terraform crea el `SecureString` con valor, el valor queda en el state. Opciones: valor placeholder con `lifecycle { ignore_changes = [value] }` y el owner pone el real con la CLI (choca con IaC only), o `value_wo` write-only (requiere comprobar soporte en `hashicorp/aws ~> 6.73`, C4). Decisión del owner.
3. **Reproducibilidad de `history_id`:** la clave SCD2 usa la secuencia de `bookings_history` (Base común). Para que el histórico regenerado dé los mismos `history_id`, el backfill debe vaciar `bookings_history` y reiniciar la secuencia (`TRUNCATE … RESTART IDENTITY`) y aplicar los cambios en orden determinista; si el owner prefiere no depender de la secuencia, la alternativa es un `change_seq` por reserva calculado por el generador. A fijar en Plan.
4. **Origen de FX:** la tarea diaria del BCE lee una API externa; el histórico de 182 días necesita un backfill desde la serie histórica del BCE. Dónde corre (local, Lambda) no está en el Ruling.
5. **Dev o prod (T7)** y **regla de lifecycle de `athena-results/`** (¿en el módulo `generator-landing` que tiene el bucket o en el nuevo? Dos módulos no pueden gestionar el mismo `aws_s3_bucket_lifecycle_configuration`).
6. **Precio de Glue Flex en eu-west-3 (acción del Ruling "Budget" pendiente antes de Plan):** el Ruling pedía a Propose confirmarlo y no se confirmó (aws-researcher dio una tarifa de ejemplo). El owner lo comprueba con el AWS Pricing Calculator o el `aws pricing get-products` del research § No comprobado; Athena en París tampoco está confirmado.

## Recommendation

| Criterio | Proposal 1 | Proposal 2 | Proposal 3 |
|----------|-----------|-----------|-----------|
| Jobs PySpark con tests | Sí; tests lentos en la imagen de Glue | Sí; tests rápidos, CI opcional | Sí; tests rápidos |
| MERGE | `events`, `sessions`, SCD2 | `events`, `sessions`, SCD2 | Solo `events` y `bookings_current` |
| Sesionización | Del generador, validada (parcial) | Por inactividad, generador como oráculo | Por inactividad, recalculada |
| SCD2 | MERGE con staging unión pre-expandida (una fila de cierre por reserva, guarda `valid_from < t0`, anti-join por `history_id`) + recálculo acotado de `valid_to`/`is_current`; la más compleja | MERGE de inserción por `(booking_id, history_id)` + cierre acotado por `v0` | Recálculo con ventanas, sin MERGE |
| Conversión de divisas | `fx_daily` con arrastre, tipo del día de `created_at`, tipo aplicado y divisa original | Igual que 1 | Igual que 1 |
| Relanzar un día da el mismo resultado (independiente del orden) | Sí tras la corrección: sesiones recalculadas sobre todo `silver.events` del `session_id`, SCD2 con guardas; no protege de errores del generador en la sesión | Sí: sesiones sin corte por `_ingest_date` (depende del límite de 72 h, C1), SCD2 por `history_id`, `bookings_current` condicional | Sí por construcción (salida a) y `bookings_current` condicional |
| Paridad local/Glue | Alta | Media (versiones fijadas a mano) | Alta en ensayo, media en tests (dos runtimes) |
| Riesgo de lifecycle (T1) | Bajo (Bronze en PR 5) | Bajo (Bronze genérico en PR 4) | Bajo (PR 4) |
| Nº de PRs | 7 | 8 | 6 |
| Nº de jobs en demo | 8 (3 Bronze + 5 Silver) | 7 (1 Bronze + 6 Silver) | 7 (1 Bronze + 6 Silver) |
| Coste AWS | ≈ 0,23 USD/demo | ≈ 0,20 USD/demo | ≥ 0,20 USD/demo |
| Enmiendas | Ninguna | Ninguna | Requerida (Idempotency) |

**Cuándo elegir cada una:** la 1 si la prioridad es la paridad exacta con Glue y una entrega rápida de Bronze, aceptando el SCD2 más complejo; la 2 si la prioridad es demostrar cada capacidad del criterio de forma independiente y revisable; la 3 si se prefiere la máxima simplicidad aceptando la enmienda de Idempotency, que no escala y que el SCD2 no usa MERGE.

**Huecos comunes:** ninguna resuelve las Open Questions compartidas 1–6; las tres dependen del cambio de generador (con `bookings_history`) y de la regeneración antes de cualquier Silver útil. Antes de Plan quedan dos acciones del Ruling que no se pueden saltar: la prueba de MFA (OQ 1) y el precio de Glue Flex en eu-west-3 (OQ 6).

**Recomendación del autor (re-puntuada tras la comprobación de coherencia):** Proposal 2 (inserción SCD2 por `(booking_id, history_id)` con cierre acotado, `bookings_current` condicional, sesiones sin corte por `_ingest_date` y reemplazo por partición), con un solo runtime local (`pyspark` de pip con versiones fijadas a las de Glue 5) y la demo Glue como única comprobación de paridad (Validation 6 de P2). Con el Ruling "Relanzar un día" ya decidido, la 3 con la salida (a) cumple la independencia del orden por construcción, pero requiere enmienda de Idempotency y su SCD2 no usa MERGE; la 1 la cumple con un SCD2 más complejo y sesiones del generador. La 2 es la única que cubre los seis criterios con MERGE en SCD2 y sesionización por inactividad sin enmiendas; su coste es más PRs y paridad media. La elección es del owner.

## Decision

**Elegida: Proposal 2, por tabla de extremo a extremo, con PySpark de pip** (javiladino, 2026-11-20).

Razón: es la única que cumple los seis criterios con MERGE en el SCD2 y sesionización por inactividad, y no necesita enmendar ninguna Convention. El relanzado es independiente del orden siempre que se cumpla la ventana de 72 h para eventos tardíos. Va con un único runtime local (pyspark con las versiones de Glue 5) y la demo de Glue comprueba la paridad.

Decisiones del owner tomadas en esta etapa, con su home en el Ruling Research decisions de `context.md`: relanzar un día da el mismo resultado sea cual sea el orden; el export lee `bookings_history`, que alimenta un trigger; el tipo de cambio por reserva es el del día de `created_at`.

Antes de Plan (acciones del Ruling, a cargo del owner): probar el MFA con `aws login` y confirmar el precio de Glue Flex en eu-west-3. Las demás Open Questions se resuelven en Plan.
