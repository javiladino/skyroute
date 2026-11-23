# Runbook: demo del recorrido de punta a punta, Fases 1 a 3 (dev)

Lo ejecuta el owner en su shell (zsh, macOS), desde la raíz del repo. Objetivo: enseñar el camino generador OTA -> `landing/` -> Bronze -> Silver -> consulta en Athena, todo en dev. La guía no crea ni modifica recursos: solo lee `landing/`, lanza jobs Glue ya desplegados y consulta Athena (Conventions "No hourly-billed resources", "Idempotency" y "Apply gate").

Datos (de `bronze-silver-demo-glue.md`): cuenta 437266392155, región eu-west-3, bucket `skyroute-dev-data-437266392155`, workgroup `skyroute-dev`, bases `skyroute_dev_bronze` y `skyroute_dev_silver`, perfil `skyroute-dev-login`. Fecha de la demo: D = 2026-11-20 (Bronze de dev ya tiene 182 días, 2026-05-23..2026-11-20).

Cada comando es simple (sin `;`, `&&`, tuberías ni heredocs) y va con `--profile skyroute-dev-login --region eu-west-3 --no-cli-pager`. Los marcadores `<...>` se sustituyen a mano con la salida del comando anterior.

## 0. Pre-check

```bash
aws sts get-caller-identity --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Se ve la cuenta 437266392155. Si falla el login: `aws login --profile skyroute-dev-login`.

## 1. Generador: schedule y Lambda, y `landing/` de un día

Qué se ve: un schedule de EventBridge Scheduler con `rate(15 minutes)` (`infra/terraform/modules/generator-landing/scheduler.tf`) que invoca la Lambda `skyroute-dev-generator`. Por qué importa: es el origen de los datos y demuestra que la ingesta es un push periódico, no un job de Spark.

En dev el schedule está en `schedule_enabled = false` (`infra/terraform/envs/dev/main.tf`), así que debe aparecer `DISABLED`: el histórico se generó por invocaciones manuales (ver `bronze-silver-historico-dev.md`) y no hay nada encendido.

```bash
aws scheduler get-schedule --name skyroute-dev-generator --group-name default --query "{estado:State,frecuencia:ScheduleExpression}" --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Esperado: `DISABLED` y `rate(15 minutes)`. El nombre del schedule es `local.function_name` del módulo; si da `ResourceNotFoundException`, TODO(confirmar) el nombre exacto con `aws scheduler list-schedules`.

```bash
aws lambda get-function-configuration --function-name skyroute-dev-generator --query "{runtime:Runtime,memoria:MemorySize,timeout:Timeout}" --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Esperado: la configuración de la Lambda (runtime, memoria, timeout).

Listado de `landing/` del día D (sin `--recursive`, lista los objetos de la partición):

```bash
aws s3 ls s3://skyroute-dev-data-437266392155/landing/bookings/ingest_date=2026-11-20/ --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

```bash
aws s3 ls s3://skyroute-dev-data-437266392155/landing/clickstream/ingest_date=2026-11-20/ --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

```bash
aws s3 ls s3://skyroute-dev-data-437266392155/landing/fx/ingest_date=2026-11-20/ --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Esperado: un `part.json.gz` por día en bookings y fx, y 96 objetos de clickstream (cifra del runbook histórico). Los objetos se subieron el 2026-11-21 y caducan por lifecycle el 2026-12-21 (30 días desde la subida): pasada esa fecha este paso y el 2 no se pueden repetir sin regenerar. Si no devuelve nada, `landing/` ya expiró: salta al paso 4, porque Bronze y Silver conservan los datos.

## 2. Bronze: landing -> Iceberg

Qué se ve: el job `skyroute-dev-bronze-ingest` (script `spark/jobs/bronze/ingest.py`) copia el día D de `landing/` a una tabla Iceberg particionada por `_ingest_date`, una fuente por ejecución (`clickstream`, `bookings`, `fx`). Por qué importa: es la capa cruda e inmutable; reejecutar un día reemplaza solo su partición.

Si ya hay datos de D en Bronze (lo normal: 182 días cargados), se puede saltar el lanzamiento y pasar a verificar con el conteo del paso 4. Para enseñar el job, relanzar D es idempotente. Coste: Glue 5 Flex, 2 DPU, unos 10 min por job (`bronze-silver-demo-glue.md`). El objetivo de ese runbook es < 0,50 USD por demo. Estimación de una demo de dos jobs (fx_daily + bookings_eur): ~0,20 USD (cálculo del orquestador sobre 2 DPU Flex x ~10 min; TODO(confirmar) con Cost Explorer, paso 5). Cada job adicional suma del orden de 0,10 USD.

```bash
aws glue start-job-run --job-name skyroute-dev-bronze-ingest --arguments '{"--source":"bookings","--run-date":"2026-11-20"}' --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Anota el `JobRunId` devuelto (`<RUN>`). Espera hasta `SUCCEEDED` repitiendo (cada ~30 s; con Flex el arranque puede tardar):

```bash
aws glue get-job-run --job-name skyroute-dev-bronze-ingest --run-id <RUN> --query JobRun.JobRunState --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Para `clickstream` (necesario para `events` y `sessions`) repite los dos comandos con `"--source":"clickstream"`. Para `fx` no hace falta si ya está cargado: `fx_daily` lee todo el rango de Bronze.

```bash
aws glue start-job-run --job-name skyroute-dev-bronze-ingest --arguments '{"--source":"clickstream","--run-date":"2026-11-20"}' --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Si un job acaba `FAILED`:

```bash
aws glue get-job-run --job-name skyroute-dev-bronze-ingest --run-id <RUN> --query JobRun.ErrorMessage --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

El detalle está en CloudWatch, grupo `/aws-glue/jobs/error` (stream = JobRunId).

## 3. Silver: los seis jobs

Qué se ve: seis jobs `skyroute-dev-silver-*` (`infra/terraform/modules/lakehouse/glue_jobs.tf`): `bookings_scd2`, `bookings_current`, `fx_daily`, `bookings_eur`, `events`, `sessions`. Por qué importa: Silver tipa, deduplica, convierte a EUR y sesioniza; cada job valida con checks YAML antes de publicar (patrón write-audit-publish), de modo que un dato malo no se publica.

Orden mínimo para la demo, el que ya está verificado (`bronze-silver-demo-glue.md`): primero `fx_daily` (sin él `bookings_eur` falla el check `not_null` de `fx_rate_applied`), después `bookings_eur`. Los tipos hacen falta desde la fecha `created_at` más antigua de las versiones de D (C, típicamente D-1 o D-2). Para la demo se usa C = 2026-11-18 como punto de partida seguro; si el check falla, ese runbook explica cómo medir C.

```bash
aws glue start-job-run --job-name skyroute-dev-silver-fx_daily --arguments '{"--from":"2026-11-18","--to":"2026-11-20"}' --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Espera `SUCCEEDED` (3-6 min) con `get-job-run` como en el paso 2, cambiando `--job-name` a `skyroute-dev-silver-fx_daily` y `<RUN>`.

```bash
aws glue start-job-run --job-name skyroute-dev-silver-bookings_eur --arguments '{"--run-date":"2026-11-20"}' --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Espera `SUCCEEDED`. Qué se ve: la tabla `skyroute_dev_silver.bookings_eur` con `amount`, `fx_rate_applied` y `amount_eur`.

Resto de jobs Silver (opcionales; cada uno suma coste y tiempo). Todos aceptan `--run-date`:

```bash
aws glue start-job-run --job-name skyroute-dev-silver-bookings_scd2 --arguments '{"--run-date":"2026-11-20"}' --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

`bookings_current` va después de `bookings_scd2` (misma sintaxis con `--job-name skyroute-dev-silver-bookings_current`). `events` lee Bronze clickstream y lee la clave HMAC del email desde SSM (la política IAM del módulo ya lo permite); `sessions` va después de `events` y reescribe las sesiones que empiezan en [D-4, D], con lectura hasta D+2. TODO(confirmar): que `events` y `sessions` se hayan ejecutado en Glue con D = 2026-11-20 (el runbook de la demo solo documenta `fx_daily` y `bookings_eur`) y que Bronze/Silver events tengan D-5..D+2 cargados; si `sessions` falla por ventana incompleta, enseña la tabla con otro día ya poblado.

## 4. Athena: qué enseñar

Cada consulta son dos comandos simples: lanzarla (devuelve `QueryExecutionId`, `<Q>`) y leer el resultado. Espera unos segundos entre ambos; el estado se ve con `get-query-execution`:

```bash
aws athena get-query-execution --query-execution-id <Q> --query QueryExecution.Status.State --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Para leer el resultado:

```bash
aws athena get-query-results --query-execution-id <Q> --query "ResultSet.Rows[*].Data[*].VarCharValue" --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

### 4.1 Recuentos por capa

Por qué importa: muestra que cada capa se conecta con la anterior. El de Silver es el total de la tabla: coincide con D solo si `bookings_eur` se cargó únicamente para D (caso de la demo ya hecha).

```bash
aws athena start-query-execution --work-group skyroute-dev --query-string "SELECT 'bronze.bookings D' AS capa, count(*) AS filas FROM skyroute_dev_bronze.bookings WHERE _ingest_date = DATE '2026-11-20' UNION ALL SELECT 'silver.bookings_eur' AS capa, count(*) AS filas FROM skyroute_dev_silver.bookings_eur" --query QueryExecutionId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Anota las dos cifras (`<N>`) para el 4.5. Para la capa landing, el recuento son los objetos del paso 1.

### 4.2 Una reserva con `amount_eur` y su tipo de cambio

Por qué importa: es la regla de negocio central de Silver: `amount_eur` = `amount` convertido con el tipo del día de `created_at` (`fx_rate_applied`, `decimal(18,6)`).

```bash
aws athena start-query-execution --work-group skyroute-dev --query-string "SELECT booking_id, changed_at, currency, amount, fx_rate_applied, amount_eur FROM skyroute_dev_silver.bookings_eur ORDER BY changed_at LIMIT 5" --query QueryExecutionId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Para contrastar el tipo con su fuente (`skyroute_dev_silver.fx_daily`: `fx_date`, `currency`, `rate_per_eur`):

```bash
aws athena start-query-execution --work-group skyroute-dev --query-string "SELECT fx_date, currency, rate_per_eur FROM skyroute_dev_silver.fx_daily WHERE fx_date = DATE '2026-11-20' ORDER BY currency" --query QueryExecutionId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Se ve que el `fx_rate_applied` de una reserva en moneda no EUR coincide con `rate_per_eur` de su `created_at`. Cálculo a explicar en pantalla: `amount_eur` = `amount` / `rate_per_eur` (convención BCE, tipo por 1 EUR); TODO(confirmar) la dirección exacta (división o multiplicación) en `spark/jobs/silver/bookings_eur.py` antes de enseñarlo.

### 4.3 Sesiones

Por qué importa: muestra el valor analítico del clickstream (sesiones con hueco de inactividad y marca de conversión). Requiere que `sessions` se haya ejecutado (ver TODO del paso 3).

```bash
aws athena start-query-execution --work-group skyroute-dev --query-string "SELECT converted, count(*) AS sesiones, round(avg(n_events), 1) AS eventos_medios FROM skyroute_dev_silver.sessions WHERE session_start_date = DATE '2026-11-20' GROUP BY converted" --query QueryExecutionId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

### 4.4 Historial de snapshots de Iceberg

Por qué importa: cada ejecución de un job publica un snapshot nuevo; es la base del time travel y de la idempotencia (un `overwrite` sustituye datos, no los duplica).

```bash
aws athena start-query-execution --work-group skyroute-dev --query-string "SELECT snapshot_id, committed_at, operation FROM skyroute_dev_silver.\"bookings_eur\$snapshots\" ORDER BY committed_at DESC" --query QueryExecutionId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Se ven los snapshots con su operación (`append` u `overwrite`) y la hora de commit. El `\$` evita que zsh expanda `$snapshots`; si Athena devuelve error de sintaxis, TODO(confirmar) el escape de comillas en zsh y prueba la consulta desde la consola de Athena (workgroup `skyroute-dev`).

### 4.5 Idempotencia: relanzar D da el mismo recuento

Por qué importa: es la Convention "Idempotency": reejecutar un día no duplica filas. Relanza `bookings_eur` para D (mismo comando del paso 3), espera `SUCCEEDED` y repite la consulta 4.1.

```bash
aws glue start-job-run --job-name skyroute-dev-silver-bookings_eur --arguments '{"--run-date":"2026-11-20"}' --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Esperado: el recuento de `silver.bookings_eur` es idéntico al anotado en 4.1, y 4.4 muestra un snapshot nuevo (la tabla cambió de versión, los datos no). Coste de esta repetición: un job más (~0,10 USD, estimación).

## 5. Limpieza y coste

Nada se queda encendido: la guía solo lanza ejecuciones de Glue (facturadas por DPU-segundo y terminadas al acabar) y consultas de Athena (facturadas por dato escaneado). No hay recursos por hora ni nada que borrar; el schedule del generador sigue `DISABLED`.

Comprobar que no queda ningún run vivo (debe devolver vacío o solo estados terminales):

```bash
aws glue get-job-runs --job-name skyroute-dev-silver-bookings_eur --max-results 3 --query "JobRuns[*].[Id,JobRunState]" --output text --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Repite con `skyroute-dev-bronze-ingest` y `skyroute-dev-silver-fx_daily` si se lanzaron. Si un run queda en `RUNNING`:

```bash
aws glue batch-stop-job-run --job-name <JOB> --job-run-ids <RUN> --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Coste: Cost Explorer tarda hasta 24 h en reflejarlo; consúltalo al día siguiente (el endpoint de CE es us-east-1). Éxito: suma de Glue de los días de la demo < 0,50 USD con dos jobs, en línea con el runbook de la demo.

```bash
aws ce get-cost-and-usage --time-period Start=<AAAA-MM-DD>,End=<AAAA-MM-DD+1> --granularity DAILY --metrics UnblendedCost --filter '{"Dimensions":{"Key":"SERVICE","Values":["AWS Glue"]}}' --profile skyroute-dev-login --region us-east-1 --no-cli-pager
```

Si `AccessDenied` en `ce:GetCostAndUsage`, mira Billing > Cost Explorer en consola con filtro Servicio = AWS Glue.

## Qué pegar al orquestador

- Estado y `JobRunId` de cada job lanzado.
- Cifras de los pasos 4.1 y 4.5 (antes y después de relanzar D).
- Importe de Glue por día (paso 5, cuando esté disponible).
- Si algo falló: el paso, el comando, el `ErrorMessage` literal y las últimas líneas de `/aws-glue/jobs/error`.
