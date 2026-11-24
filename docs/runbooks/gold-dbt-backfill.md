# Runbook: backfill único de Bronze y Silver (Fase 4, gold-dbt)

Lo ejecuta el owner en su shell (zsh, macOS), desde la raíz del repo. Objetivo: recrear Bronze y Silver una sola vez por entorno con el generador nuevo (ruta, `travel_date`, recorridos multi-campaña, funnel, `ad_spend`), en Spark local. Base: Ruling "Bronze rebuild exception" y "Plan decisions" de `docs/design/gold-dbt/context.md`; plan `docs/design/gold-dbt/working/plan.md`, fases 4 y 7.

Reglas de este runbook:

- Un comando por paso (Convention "Simple shell commands"); copia uno, ejecútalo, comprueba el esperado y pasa al siguiente. Los pasos por día se repiten cambiando `<D>`.
- Región `eu-west-3` en todo (Convention "Region").
- Ningún cambio de infraestructura desde la consola ni con `terraform apply` local: las PRs las aplica CI (IaC only, Apply gate).
- `rebuild_tables` es destructivo y de un solo uso por entorno: dev en la fase 4 y prod en la fase 7. Reintentar el backfill desde el paso de regeneración cuenta como el mismo backfill (plan, Open questions).

## 0. Estado de partida (ya hecho)

- Generador nuevo desplegado en dev y prod (PR #49).
- Schedule del generador de prod en pausa por IaC (`envs/prod/main.tf`, `schedule_enabled = false`, PR #48, aplicada el 2026-11-24). La Lambda de prod no escribe `landing/clickstream` mientras dure el backfill. La opción (a) del plan (pausar por IaC) está hecha; la (b) (comparar `CodeSha256`) no hace falta. Se reactiva en la fase 7 con una PR `schedule_enabled = true` tras el rebuild de prod (paso 7.8).
- Fases 1 (generador), 2 (Spark con `ad_spend` y `ad_spend_daily`) y 3 (`rebuild_tables` y este runbook) fusionadas en `main`.

## 1. Commit único del generador

Todo el backfill (dev y prod) sale de un único commit del generador (Ruling "un único cambio y un único backfill"). Anótalo y no cambies de rama hasta terminar.

1. `git checkout main`
2. `git pull`
3. `git rev-parse HEAD` → anota `<COMMIT>`.
4. `git status --short` → esperado: sin cambios en `generators/` ni `spark/`.

Si un paso posterior exige cambiar el generador, para: es un backfill nuevo y necesita decisión del owner.

## 2. Perfil AWS local con MFA

En `~/.aws/config`, un perfil por entorno (el de prod solo existe entre las PRs 7a y 7c):

```ini
[profile skyroute-dev-local-data]
role_arn = arn:aws:iam::437266392155:role/workload/skyroute-dev-local-data
source_profile = skyroute-dev-login
mfa_serial = arn:aws:iam::437266392155:mfa/skyroute
region = eu-west-3
```

Para no pedir MFA en cada comando, exporta credenciales temporales (1 h) una vez por sesión:

1. `aws login --profile skyroute-dev-login` (solo si la sesión del login caducó).
2. `eval "$(aws configure export-credentials --profile skyroute-dev-local-data --format env)"`
3. `aws sts get-caller-identity --region eu-west-3` → esperado: `Arn` = `arn:aws:sts::437266392155:assumed-role/skyroute-dev-local-data/...`.

No exportes `AWS_PROFILE` junto a las variables: el contenedor de Spark usaría el montaje de `~/.aws`. Cuando caduquen (`ExpiredToken`), repite el paso 2.2.

## 3. Rango y plazos

- El owner fija la fecha de inicio `<INICIO>` y el fin `<FIN>` (plan, Open question 4; rango de 182 días). La regeneración arranca en `<S>` = `<INICIO>` menos 6 días, para que ninguna reserva desde `<INICIO>` tenga recorrido truncado (Design Decision 6).
- `landing/` conserva 30 días por antigüedad del objeto (`bucket.tf:79-89`): Bronze del rango completo debe estar ingerido antes de 30 días desde la primera subida.
- Cómputo en Spark local (0 USD). En AWS solo quedan S3 y Glue Catalog. Tope de alarma de dev: 1 USD (O12). Si Cost Explorer lo supera, para.

## 4. Postgres local

Si el volumen de Postgres viene de antes de la fase 1 (tablas sin `origin`, `destination`, `travel_date`), recréalo. Los init SQL son idempotentes (`ADD COLUMN IF NOT EXISTS`), pero solo corren al crear el volumen.

1. `docker compose -f docker/postgres/compose.yml down -v`
2. `docker compose -f docker/postgres/compose.yml up -d`
3. `docker compose -f docker/postgres/compose.yml exec -T postgres psql -U postgres -c "\d bookings"` → esperado: aparecen `origin`, `destination`, `travel_date`.
4. `make seed-postgres SEED_FROM=<S> SEED_TO=<FIN> REBUILD=1` → esperado: sin error.

## 5. Backfill de dev (fase 4)

Datos de dev: bucket `skyroute-dev-data-437266392155` (`<B>`), Lambda `skyroute-dev-generator`, workgroup `skyroute-dev`, bases `skyroute_dev_bronze` y `skyroute_dev_silver`.

### 5.1 Regenerar `landing/` desde `<S>`

Por cada día `<D>` de `<S>` a `<FIN>`, en orden ascendente:

1. Clickstream (Lambda de dev, un día por invocación): `aws lambda invoke --function-name skyroute-dev-generator --cli-binary-format raw-in-base64-out --cli-read-timeout 0 --payload '{"from":"<D>","to":"<D>"}' --query FunctionError --output text --region eu-west-3 --profile skyroute-dev-login /dev/null` → esperado: `None`.
2. Reservas: `make export-bookings RUN_DATE=<D> OUT_DIR=build`
3. Gasto: `PYTHONPATH=generators .venv/bin/python -m ota.ad_spend --run-date <D> --out-dir build`

Una vez para todo el rango:

4. FX: `PYTHONPATH=generators .venv/bin/python -m fx.ecb --from <S> --to <FIN> --out-dir build`
5. `aws s3 sync build/landing/bookings s3://<B>/landing/bookings --dryrun --region eu-west-3 --profile skyroute-dev-login`, después sin `--dryrun`.
6. Ídem con `build/landing/fx` → `landing/fx` y `build/landing/ad_spend` → `landing/ad_spend`.

Esperado: una clave `ingest_date=<D>/part.json.gz` por día y fuente.

### 5.2 Recuento esperado de eventos

1. `PYTHONPATH=generators .venv/bin/python -m ota.backfill_counts --from <S> --to <FIN>` → anota `<TOTAL>` (Validation 4b). Sale del mismo `<COMMIT>`, sin leer S3.

### 5.3 `rebuild_tables` en dev

Con las credenciales de `skyroute-dev-local-data` del paso 2:

1. Dry-run: `docker compose -f docker/spark/compose.yml run --rm spark python -m jobs.maintenance.rebuild_tables --env dev --warehouse s3://<B>/silver --dry-run`
   Esperado: la identidad pasa, imprime las 11 tablas (`skyroute_dev_bronze.{clickstream,bookings,fx,ad_spend}` y `skyroute_dev_silver.{bookings_scd2,bookings_current,fx_daily,bookings_eur,events,sessions,ad_spend_daily}`) y `--dry-run: no se borra nada`.
2. Borrado: `docker compose -f docker/spark/compose.yml run --rm -it spark python -m jobs.maintenance.rebuild_tables --env dev --warehouse s3://<B>/silver`
   Teclea `dev` cuando lo pida. Esperado: una línea `DROP PURGE skyroute.<tabla>` por tabla y `terminado: 11 tablas`. Guarda la salida como evidencia.

Salidas de rechazo (código 2, no borra nada): identidad distinta de `skyroute-dev-local-data` (repite el paso 2), texto tecleado distinto de `dev`. Si falla con `No module named 'boto3'`, la imagen de Spark no trae boto3: para y avisa al orquestador (ver "Pendiente" al final).

### 5.4 Bronze en local, día ascendente, las cuatro fuentes

Un comando por fuente, en este orden; cada uno recorre el rango con `--from`/`--to`:

1. `docker compose -f docker/spark/compose.yml run --rm spark python -m jobs.bronze.ingest --source clickstream --from <S> --to <FIN> --landing-root s3a://<B> --warehouse s3://<B>/bronze --catalog-impl glue --env dev`
2. Ídem con `--source bookings`.
3. Ídem con `--source fx`.
4. Ídem con `--source ad_spend`.

Si caduca la sesión, el log dice `reanuda con --from X --to E`: renueva credenciales (paso 2.2) y relanza esa fuente con `--from X`.

### 5.5 Silver en local, tras su Bronze (WAP)

Mismo patrón, `--warehouse s3://<B>/silver --catalog-impl glue --env dev --from <S> --to <FIN>`, un job por paso y en este orden (cada uno después de sus entradas):

1. `jobs.silver.fx_daily`
2. `jobs.silver.ad_spend_daily`
3. `jobs.silver.bookings_scd2`
4. `jobs.silver.bookings_current`
5. `jobs.silver.bookings_eur`
6. `jobs.silver.events`
7. `jobs.silver.sessions`

Ejemplo: `docker compose -f docker/spark/compose.yml run --rm spark python -m jobs.silver.events --from <S> --to <FIN> --warehouse s3://<B>/silver --catalog-impl glue --env dev`

Esperado: ningún `schema_mismatch` ni `events_conflicting_published` en los logs (O5).

### 5.6 Validaciones (4 y 4b)

1. O3, por tabla sin partición: `aws s3 ls s3://<B>/silver/<tabla>/data/ --recursive --summarize --region eu-west-3 --profile skyroute-dev-login` → `Total Size` < 100 MB.
2. O4 en Athena (workgroup `skyroute-dev`): `SELECT count(*), count(DISTINCT event_id) FROM skyroute_dev_silver.events` → los dos iguales a `<TOTAL>`.
3. O6: una versión abierta por `booking_id` en `skyroute_dev_silver.bookings_scd2`.

### 5.7 Un día de demo en Glue Flex

Solo uno, después del backfill (Design Decision 11). Sigue `docs/runbooks/bronze-silver-demo-glue.md` con un único `<D>` del rango. Ningún otro día del backfill se lanza en Glue.

### 5.8 Coste

Cost Explorer (Glue, Athena, S3; `eu-west-3`) al día siguiente del backfill y del día de demo. Adjunta la cifra (O12). Acumulado de dev por debajo de 1 USD; si no, para y avisa.

## 6. Antes de la fase 7: el histórico de prod se puede regenerar

Comprueba, y deja escrito en la evidencia, que todo lo que Bronze y Silver de prod contienen sale del generador: clickstream de la Lambda (determinista por fecha), reservas de Postgres local sembradas por `seed_postgres`, FX del BCE y gasto de `ota.ad_spend`. Si alguna tabla de prod tiene datos que no salen del generador, no ejecutes el paso 7: el DROP los perdería sin vuelta atrás.

## 7. Prod al cierre (fase 7)

Datos de prod: bucket `skyroute-prod-data-437266392155` (`<BP>`), bases `skyroute_prod_bronze` y `skyroute_prod_silver`. Requiere el paso 6 y Gold validado en dev (fase 5).

1. PR 7a: `infra/terraform/envs/prod/main.tf`, `create_local_data_role = true`. Revisa el plan de CI (solo el rol y su inline); el apply lo hace CI.
2. Perfil `[profile skyroute-prod-local-data]` como el del paso 2 con `role_arn = arn:aws:iam::437266392155:role/workload/skyroute-prod-local-data`; `eval "$(aws configure export-credentials --profile skyroute-prod-local-data --format env)"`; `aws sts get-caller-identity --region eu-west-3` → `assumed-role/skyroute-prod-local-data/...`.
3. Regenera `landing/` de prod como en 5.1 (Lambda `skyroute-prod-generator` con `--profile` de prod; bucket `<BP>`) y el recuento de 5.2. El schedule sigue pausado (paso 0).
4. `docker compose -f docker/spark/compose.yml run --rm spark python -m jobs.maintenance.rebuild_tables --env prod --confirm-prod --warehouse s3://<BP>/silver --dry-run`
5. `docker compose -f docker/spark/compose.yml run --rm -it spark python -m jobs.maintenance.rebuild_tables --env prod --confirm-prod --warehouse s3://<BP>/silver` y teclea `prod`. Es el segundo y último uso de la excepción. Sin `--confirm-prod` sale con error y no borra.
6. Bronze y Silver de prod como 5.4 y 5.5 con `--env prod` y `<BP>`; validaciones como 5.6 sobre `skyroute_prod_*`.
7. `dbt build` de prod con `local-dbt` de prod: `.venv/bin/dbt build --project-dir dbt --profiles-dir <dir del profiles.yml del owner> --target prod --vars '{run_date: <D>}'`.
8. PR de reanudación: `infra/terraform/envs/prod/main.tf`, `schedule_enabled = true`, aplicada por CI. Nunca desde la consola.
9. PR 7c: `create_local_data_role = false`, aplicada por CI. Evidencia (O15): salida del apply con el `destroy` de `aws_iam_role.local_data` y su `aws_iam_role_policy`; después `aws iam get-role --role-name skyroute-prod-local-data` (sin `--region`, IAM es global) → `NoSuchEntity`.

## 8. Qué pegar al orquestador

- `<COMMIT>`, `<INICIO>`, `<S>`, `<FIN>` y `<TOTAL>`.
- Salida de `rebuild_tables` (dry-run y borrado) de cada entorno.
- Resultados de 5.6 (o su equivalente de prod) y la cifra de Cost Explorer.
- Si algo falló: el paso, el comando, el mensaje literal y la última fecha OK del log.

## Pendiente

- La imagen `docker/spark` instala solo `spark/requirements.txt`, que no incluye `boto3`; `rebuild_tables` lo necesita para `sts:GetCallerIdentity` y falla cerrado (sin borrar) si no está. Decisión del owner antes del paso 5.3.
- `ota.ad_spend` y `export_bookings` solo aceptan `--run-date`, así que 5.1 es un comando por día.
