# Runbook: gate "Histórico" en dev (Fase 4, bronze-silver)

Lo ejecuta el owner en su shell (zsh, macOS), desde la raíz del repo. Objetivo: 182 días regenerados en dev e ingeridos en Bronze antes de R + 30 días (Ruling "Histórico"; `landing/` conserva 30 días). El lifecycle expira por antigüedad del objeto (momento de subida), no por la fecha lógica: los objetos recién regenerados no caducan hasta R + 30.

Datos: cuenta 437266392155, región eu-west-3, bucket `skyroute-dev-data-437266392155`, Lambda `skyroute-dev-generator`, workgroup `skyroute-dev`, base `skyroute_dev_bronze`. Perfiles: `skyroute-dev-login` (admin, S3/Lambda/Athena) y `skyroute-dev-local-data` (MFA, 1 h; lee `landing/`, escribe `bronze/`, Glue `skyroute_dev_*`).

## 0. Pre-checks

```bash
export AWS_REGION=eu-west-3 AWS_DEFAULT_REGION=eu-west-3 B=skyroute-dev-data-437266392155
unset AWS_PROFILE
docker info > /dev/null && echo OK-docker
docker compose -f docker/postgres/compose.yml up -d
test -x .venv/bin/python && echo OK-venv
aws sts get-caller-identity --profile skyroute-dev-login
docker compose -f docker/spark/compose.yml build
```

Esperado: `OK-docker`, `OK-venv`, cuenta 437266392155 y build sin error. Java no hace falta en el host. Si `docker info` falla, arranca OrbStack. Si falla el login: `aws login --profile skyroute-dev-login`.

## 1. Rango de 182 días y fecha R

La Lambda exige `to <= hoy-1` (UTC), así que el rango termina ayer: E = hoy-1, S = hoy-182 (182 días inclusive).

```bash
export R=$(date -u +%F) E=$(date -u -v-1d +%F) S=$(date -u -v-182d +%F)
echo "R=$R rango=$S..$E"
```

Ejemplo con hoy 2026-11-21: R=2026-11-21, S=2026-05-23, E=2026-11-20. Anota R: el gate vence en R + 30 días. Mantén `S`, `E`, `B` exportadas en el resto de pasos (misma terminal; si abres otra, repite los `export`).

## 2. Backfill de clickstream en la Lambda de dev

Mecanismo de la Fase 2 (`generators/lambda_handler.py:75-92,104-105`; evidencia en `docs/design/generator-landing/current/test.md:341-347,174`): invocaciones síncronas de 1 día con payload `{"from":"D","to":"D"}` (96 objetos por día), `--cli-read-timeout 0`, parada ante `FunctionError`. Es determinista: repetir un día sobrescribe las mismas claves.

```bash
aws lambda get-function-configuration --function-name skyroute-dev-generator --query Timeout --profile skyroute-dev-login
for n in $(seq 182 -1 1); do
  d=$(date -u -v-${n}d +%F)
  fe=$(aws lambda invoke --function-name skyroute-dev-generator --cli-binary-format raw-in-base64-out --cli-read-timeout 0 --payload "{\"from\":\"$d\",\"to\":\"$d\"}" --query FunctionError --output text --profile skyroute-dev-login /dev/null)
  [ "$fe" = "None" ] || { echo "FALLO $d: $fe"; break; }
  echo "ok $d"
done
```

Esperado: `Timeout` suficiente para 96 puts (300 en prod; si es menor y falla, avisa) y 182 líneas `ok`. Verifica un día: `aws s3 ls s3://$B/landing/clickstream/ingest_date=$S/ --recursive --summarize --profile skyroute-dev-login | tail -2` debe dar `Total Objects: 96`. Si hay `FALLO d`: relanza el bucle desde ese día (cambia el `seq`). Si el error es `to debe ser <= hoy-1`, revisa el paso 1 (UTC).

## 3. Postgres con REBUILD

```bash
set -a; source .env; set +a
make seed-postgres SEED_FROM=$S SEED_TO=$E REBUILD=1
```

Esperado: sin error (`psql` en silencio, `-q`). Si falla la conexión, revisa `docker compose -f docker/postgres/compose.yml ps` y el puerto 5433.

## 4. Export de Reservas y FX a build/

```bash
rm -rf build/landing
export PGPASSWORD="$POSTGRES_PASSWORD"
for n in $(seq 182 -1 1); do make export-bookings RUN_DATE=$(date -u -v-${n}d +%F) OUT_DIR=build || break; done
PYTHONPATH=generators .venv/bin/python -m fx.ecb --from $S --to $E --out-dir build
ls build/landing/bookings | wc -l
ls build/landing/fx | wc -l
```

Esperado: una línea `build/landing/bookings/ingest_date=D/part.json.gz (N filas)` por día (un día sin filas escribe un gzip vacío válido), `182 archivos en build` para FX y ambos `wc -l` = 182. FX falla (exit 2) si el BCE no publica alguna fecha: no escribe nada; reintenta más tarde (si hay red, usa la serie completa por sí solo).

## 5. Subida a landing/ (dry-run primero)

```bash
aws s3 sync build/landing/bookings s3://$B/landing/bookings --dryrun --profile skyroute-dev-login | tail -3
aws s3 sync build/landing/fx s3://$B/landing/fx --dryrun --profile skyroute-dev-login | tail -3
aws s3 sync build/landing/bookings s3://$B/landing/bookings --profile skyroute-dev-login | tail -1
aws s3 sync build/landing/fx s3://$B/landing/fx --profile skyroute-dev-login | tail -1
```

Esperado: el dry-run muestra `(dryrun) upload: ... ingest_date=D/part.json.gz` y las claves mantienen `ingest_date=D/part.json.gz`. Comprueba: `aws s3 ls s3://$B/landing/fx/ --profile skyroute-dev-login | wc -l` = 182 (y bookings igual). Si hay `AccessDenied`, el login caducó: repite `aws login`.

## 6. Ingesta Bronze (Spark en Docker)

Credenciales temporales (pide MFA; el contenedor no puede hacerlo ni usar sesiones `aws login`). No exportes `AWS_PROFILE`: forzaría el montaje de `~/.aws`.

```bash
unset AWS_PROFILE
eval "$(aws configure export-credentials --profile skyroute-dev-local-data --format env)"
for src in clickstream bookings fx; do
  docker compose -f docker/spark/compose.yml run --rm spark python -m jobs.bronze.ingest --source $src --from $S --to $E --landing-root s3a://$B --warehouse s3://$B/bronze --catalog-impl glue --env dev || break
done
```

Esperado: por día una línea `bronze ingest {... 'rows_written': N ...}` y exit 0 por fuente (la primera ejecución descarga jars; tarda). Un commit atómico por día; repetir un día reemplaza su partición.

La sesión dura 1 h. Si caduca (`ExpiredToken`/403) o un día falla, el log dice `fallo en X; ultima fecha OK: Y; reanuda con --from X --to E`. Repite el `eval` con credenciales nuevas y relanza solo lo pendiente, con `--from X` (la fuente fallida y las siguientes; las anteriores ya están completas):

```bash
docker compose -f docker/spark/compose.yml run --rm spark python -m jobs.bronze.ingest --source <src> --from <X> --to $E --landing-root s3a://$B --warehouse s3://$B/bronze --catalog-impl glue --env dev
```

`sin archivos de entrada en ...`: falta ese día en `landing/` (vuelve al paso 2 o 5). `columnas nuevas en landing`: avisa al orquestador.

## 7. Verificación en Athena

```bash
for t in clickstream bookings fx; do
  q=$(aws athena start-query-execution --work-group skyroute-dev --query-string "SELECT count(DISTINCT _ingest_date) FROM skyroute_dev_bronze.$t" --query QueryExecutionId --output text --profile skyroute-dev-login)
  until [ "$(aws athena get-query-execution --query-execution-id $q --query QueryExecution.Status.State --output text --profile skyroute-dev-login)" != "RUNNING" ] && [ "$(aws athena get-query-execution --query-execution-id $q --query QueryExecution.Status.State --output text --profile skyroute-dev-login)" != "QUEUED" ]; do sleep 3; done
  echo "$t: $(aws athena get-query-results --query-execution-id $q --query 'ResultSet.Rows[1].Data[0].VarCharValue' --output text --profile skyroute-dev-login)"
done
```

Esperado: `clickstream: 182`, `bookings: 182`, `fx: 182`. Si la consulta acaba `FAILED`, mira `aws athena get-query-execution --query-execution-id $q --query QueryExecution.Status.StateChangeReason --profile skyroute-dev-login`. Si un conteo es menor, localiza los días con `SELECT DISTINCT _ingest_date ... ORDER BY 1` y reanuda con `--from` ese día (paso 6).

## 8. Qué pegar al orquestador

- R, S y E (`echo "R=$R rango=$S..$E"`).
- Las tres líneas de conteo del paso 7.
- Si algo falló: el paso, el comando, el mensaje literal y la última fecha OK del log de Spark.
