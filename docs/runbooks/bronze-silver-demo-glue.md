# Runbook: demo Glue de `silver-bookings_eur` en dev (Fase 8, bronze-silver)

Lo ejecuta el owner en su shell (zsh, macOS), desde la raíz del repo. Objetivo: lanzar a mano `skyroute-dev-silver-bookings_eur` para un run_date D y comprobar que `count(*)` y `sum(amount_eur)` en Athena coinciden con el resultado de los mismos jobs en Spark local. Éxito: valores idénticos y gasto < 0,50 USD en Cost Explorer.

Datos: cuenta 437266392155, región eu-west-3, bucket `skyroute-dev-data-437266392155`, workgroup `skyroute-dev`. Bronze de dev ya tiene 182 días (2026-05-23..2026-11-20): no se lanza `skyroute-dev-bronze-ingest`. Perfiles: `skyroute-dev-login` (admin) y `skyroute-dev-local-data` (MFA, 1 h; aquí solo lee `landing/`).

Diseño de la comparación. `bookings_eur` lee solo la partición `_ingest_date = D` de Bronze (`bookings_eur.py:126`) y busca el tipo por la fecha de `created_at` en `silver.fx_daily` (`bookings_eur.py:74-77`); no depende de `bookings_scd2` ni `bookings_current`, que no se lanzan. Las versiones de D pueden ser de reservas creadas antes de D (`updated_at` crece hasta 600 min por versión, `ota/model.py:101`), así que antes de lanzar se mide la fecha C más antigua de `created_at` de D y `fx_daily` se carga con `--from C --to D` en un solo run (`fx_daily.py:121-130` recorre el rango; `lib/args.py:132-135`). Si falta un tipo, el check not_null de `bookings_eur` impide publicar. El "local" re-ingesta Bronze desde `landing/` y corre Silver en un catálogo hadoop dentro del contenedor, sin escribir en AWS (Convention "IaC only").

## 0. Pre-checks y funciones auxiliares

```bash
export AWS_REGION=eu-west-3 AWS_DEFAULT_REGION=eu-west-3 B=skyroute-dev-data-437266392155 D=2026-11-20
unset AWS_PROFILE
docker info > /dev/null && echo OK-docker
aws sts get-caller-identity --profile skyroute-dev-login
aq() { local q s; q=$(aws athena start-query-execution --work-group skyroute-dev --query-string "$1" --query QueryExecutionId --output text --profile skyroute-dev-login); while :; do s=$(aws athena get-query-execution --query-execution-id $q --query QueryExecution.Status.State --output text --profile skyroute-dev-login); case $s in QUEUED|RUNNING) sleep 3;; *) break;; esac; done; echo "$s"; aws athena get-query-results --query-execution-id $q --query 'ResultSet.Rows[1].Data[*].VarCharValue' --output text --profile skyroute-dev-login; }
gl() { local r s; r=$(aws glue start-job-run --job-name skyroute-dev-$1 --arguments "$2" --query JobRunId --output text --profile skyroute-dev-login --region eu-west-3) || return 1; echo "$1 run=$r"; while :; do s=$(aws glue get-job-run --job-name skyroute-dev-$1 --run-id $r --query JobRun.JobRunState --output text --profile skyroute-dev-login --region eu-west-3); case $s in STARTING|RUNNING|STOPPING|WAITING) sleep 20;; *) break;; esac; done; echo "$1: $s"; [ "$s" = SUCCEEDED ] || aws glue get-job-run --job-name skyroute-dev-$1 --run-id $r --query JobRun.ErrorMessage --output text --profile skyroute-dev-login --region eu-west-3; [ "$s" = SUCCEEDED ]; }
```

Esperado: `OK-docker` y la cuenta 437266392155. Si falla el login: `aws login --profile skyroute-dev-login`. Mantén `B`, `D`, `aq` y `gl` en la misma terminal (si abres otra, repite el bloque).

## 1. Fecha C: la `created_at` más antigua de D

```bash
export C=$(aq "SELECT min(substr(created_at,1,10)) FROM skyroute_dev_bronze.bookings WHERE _ingest_date = DATE '$D'" | tail -1); echo "C=$C D=$D"
```

Esperado: `C` entre 2026-11-17 y D (típicamente D-1 o D-2). Si sale vacío, D no tiene reservas en Bronze: elige otro D dentro de 2026-05-23..2026-11-20 y repite. Si `C` < 2026-05-23, no hay FX para ese día: elige un D posterior.

## 2. Glue: fx_daily de C a D (un solo run)

```bash
gl silver-fx_daily "{\"--from\":\"$C\",\"--to\":\"$D\"}"
```

Esperado: `silver-fx_daily: SUCCEEDED` (3-6 min; el arranque Flex puede tardar). Si `FAILED`: se imprime `ErrorMessage`; el detalle está en CloudWatch, grupo `/aws-glue/jobs/error` (stream = JobRunId):

```bash
aws logs tail /aws-glue/jobs/error --since 30m --profile skyroute-dev-login --region eu-west-3 | tail -40
```

`Bronze sin tipos para X` indica que falta X en `skyroute_dev_bronze.fx`; el log dice `reanuda con --from X`.

## 3. Glue: bookings_eur de D

```bash
gl silver-bookings_eur "{\"--run-date\":\"$D\"}"
```

Esperado: `silver-bookings_eur: SUCCEEDED`. Un fallo `not_null` sobre `fx_rate_applied` significa que `fx_daily` no cubre algún `created_at` de D: vuelve al paso 1 y 2.

## 4. Athena: resultado de Glue

```bash
aq "SELECT count(*), sum(amount_eur) FROM skyroute_dev_silver.bookings_eur"
```

Esperado: `SUCCEEDED` y una línea `N<TAB>TOTAL`. La tabla estaba vacía, así que son solo las reservas de D. Si `FAILED`: `aws athena get-query-execution --query-execution-id <q> --query QueryExecution.Status.StateChangeReason --profile skyroute-dev-login`.

## 5. Local: pipeline completo en Docker, sin escribir en AWS

Solo lee `landing/` de S3 (los objetos de 2026-05-23..2026-11-20 se subieron el 2026-11-21 y no caducan hasta 2026-12-21). El catálogo es hadoop y el warehouse vive dentro del contenedor (`/tmp/wh`): `compose.yml` solo monta `spark/` (solo lectura), `~/.aws` y la caché de jars, no hay volumen escribible, y cada `run --rm` es un contenedor nuevo. Por eso todo va en un único `sh -c`; al terminar, el warehouse desaparece. Bronze y Silver comparten catálogo (`skyroute.skyroute_dev_bronze` y `skyroute.skyroute_dev_silver`), así que el warehouse es el mismo.

```bash
unset AWS_PROFILE
eval "$(aws configure export-credentials --profile skyroute-dev-local-data --format env)"
docker compose -f docker/spark/compose.yml run --rm spark sh -c "set -e; python -m jobs.bronze.ingest --source bookings --run-date $D --landing-root s3a://$B --catalog-impl hadoop --warehouse /tmp/wh --env dev; python -m jobs.bronze.ingest --source fx --from $C --to $D --landing-root s3a://$B --catalog-impl hadoop --warehouse /tmp/wh --env dev; python -m jobs.silver.fx_daily --from $C --to $D --catalog-impl hadoop --warehouse /tmp/wh --env dev; python -m jobs.silver.bookings_eur --run-date $D --catalog-impl hadoop --warehouse /tmp/wh --env dev; python /app/spark/tools/count_table.py --warehouse /tmp/wh --table skyroute.skyroute_dev_silver.bookings_eur --sum-column amount_eur"
```

Esperado: `bronze ingest {... 'rows_written': N ...}` por día, `silver fx_daily {...}`, `silver bookings_eur {'run_date': ..., 'rows_in_batch': N ...}` y, al final, `count=N sum_amount_eur=TOTAL`. Si caduca la sesión (`ExpiredToken`/403), repite el `eval` y relanza el bloque entero (el warehouse empieza vacío cada vez). `sin archivos de entrada en ...`: falta ese día en `landing/`.

## 6. Comparación

Compara a mano `N` y `TOTAL` del paso 4 (Glue) con `count` y `sum_amount_eur` del paso 5 (local). Éxito: idénticos. Si difieren, no los "arregles": pégalos al orquestador con el `rows_in_batch` de ambos jobs.

## 7. Coste en Cost Explorer

Los datos de Cost Explorer tardan hasta 24 h en aparecer: ejecuta esto al día siguiente (el endpoint de CE es us-east-1).

```bash
aws ce get-cost-and-usage --time-period Start=$(date -u +%F -v-2d),End=$(date -u -v+1d +%F) --granularity DAILY --metrics UnblendedCost --filter '{"Dimensions":{"Key":"SERVICE","Values":["AWS Glue"]}}' --profile skyroute-dev-login --region us-east-1
```

Esperado: `Amount` de AWS Glue por día; suma de los días de la demo < 0,50 USD (2 DPU Flex, unos 10 min de run por job). Si `AccessDenied` en `ce:GetCostAndUsage`, mira Billing > Cost Explorer en consola, filtro Servicio = AWS Glue. Para ver también Athena y S3, cambia el filtro por `--group-by Type=DIMENSION,Key=SERVICE`.

## 8. Qué pegar al orquestador

- `C=... D=...` del paso 1.
- Estado de los dos runs Glue (pasos 2 y 3) y sus JobRunId.
- Salida del paso 4 y la línea `count=... sum_...` del paso 5, y si coinciden.
- Importe de Glue por día del paso 7 (cuando esté disponible).
- Si algo falló: el paso, el comando, el `ErrorMessage` literal y las últimas líneas de `/aws-glue/jobs/error`.
