# Spike 0c: dbt-athena con Iceberg (solo en la rama, se borra en la fase 5)

## Que se prueba

1. `spike_bookings_window`: `incremental` con `table_type='iceberg'`, `incremental_strategy='merge'`, `unique_key='booking_id'`, `partitioned_by=['day(changed_date)']` (`changed_date = date(changed_at)`), `incremental_predicates` sobre `target.changed_date` (D-4..D) y `pre_hook` `DELETE` de la ventana dentro de `is_incremental()`. Lee `skyroute_dev_silver.bookings_eur` y escribe en `skyroute_dev_gold`.
2. `spike_bookings_table`: `materialized='table'`, para confirmar que el drop o rename funciona con `GlueGoldWrite` de `local-dbt`.
3. Test singular `window_matches_silver`: anti-join en los dos sentidos por `booking_id` entre Silver y el modelo, ventana D-4..D. Esperado: 0 filas.
4. Idempotencia: el mismo `run_date` dos veces deja las mismas filas. La fecha solo llega por `--vars` (nunca `now()`); el default `1970-01-01` de `dbt_project.yml` es un centinela para `parse`.
5. `ProcessedBytes` del workgroup `skyroute-dev-dbt`: cada consulta por debajo de 100 MB.

Si algo falla se reabre la Design Decision 7 antes de la fase 5.

Deriva: spike sobre `bookings_eur` en lugar de `sessions` (no existe en dev); ventana de `sessions` en la fase 5; decidido por el owner el 2026-11-23.

## Comandos del owner (Apply gate)

Precondicion: `skyroute_dev_silver.bookings_eur` tiene los datos de la demo de Glue (D=2026-11-20, 132 filas, segun la evidencia de la Fase 3). D+1=2026-11-21 se usa en el tercer build: se espera que no traiga filas nuevas, pero no debe romper nada. Si la tabla esta vacia, el spike no puede correr (el paso 0 lo comprueba).

Un comando por paso. Datos: cuenta 437266392155, region eu-west-3, bucket `skyroute-dev-data-437266392155`, workgroup `skyroute-dev-dbt`.

Perfil en `~/.aws/config` (mismo patron que `local-data`, `docs/runbooks/bronze-silver-historico-dev.md`):

```
[profile skyroute-dev-local-dbt]
role_arn = arn:aws:iam::437266392155:role/workload/skyroute-dev-local-dbt
source_profile = skyroute-dev-login
mfa_serial = arn:aws:iam::437266392155:mfa/skyroute
region = eu-west-3
duration_seconds = 3600
```

Entrada (MFA) y entorno:

```
aws login --profile skyroute-dev-login
export AWS_PROFILE=skyroute-dev-local-dbt
export SKYROUTE_BUCKET=skyroute-dev-data-437266392155
mkdir -p ~/.dbt-skyroute
cp dbt/profiles.yml.example ~/.dbt-skyroute/profiles.yml
```

Comprobacion de identidad (debe mostrar `assumed-role/skyroute-dev-local-dbt`):

```
aws sts get-caller-identity --profile skyroute-dev-local-dbt --no-cli-pager
```

Paso 0: comprobar `bookings_eur` (min, max y count de `date(changed_at)`) y confirmar D=2026-11-20:

```
aws athena start-query-execution --work-group skyroute-dev-dbt --query-string "SELECT min(date(changed_at)), max(date(changed_at)), count(*) FROM skyroute_dev_silver.bookings_eur" --profile skyroute-dev-local-dbt --region eu-west-3 --no-cli-pager
aws athena get-query-results --query-execution-id <QueryExecutionId del paso anterior> --profile skyroute-dev-local-dbt --region eu-west-3 --no-cli-pager
```

Comprobacion de conexion de dbt:

```
.venv/bin/dbt debug --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev
```

Pasos (D = 2026-11-20, D+1 = 2026-11-21):

```
.venv/bin/dbt build --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev --select spike_bookings_window window_matches_silver --vars '{run_date: 2026-11-20}'
.venv/bin/dbt build --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev --select spike_bookings_window window_matches_silver --vars '{run_date: 2026-11-20}'
.venv/bin/dbt build --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev --select spike_bookings_window window_matches_silver --vars '{run_date: 2026-11-21}'
.venv/bin/dbt build --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev --select spike_bookings_table --vars '{run_date: 2026-11-20}'
.venv/bin/dbt build --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev --select spike_bookings_table --vars '{run_date: 2026-11-20}'
.venv/bin/dbt build --project-dir dbt --profiles-dir ~/.dbt-skyroute --target dev --full-refresh --select spike_bookings_window --vars '{run_date: 2026-11-20}'
```

Notas: el primer build crea la tabla (no incremental, el pre_hook no corre); el segundo repite `2026-11-20` y comprueba la idempotencia (mismo `count(*)` y mismos `booking_id`); el tercero con `2026-11-21` comprueba que el merge solo toca su ventana. El segundo build de `spike_bookings_table` fuerza drop o rename. El `--full-refresh` confirma que `GlueGoldWrite` basta para borrar y recrear.

Conteo tras cada build (Athena, workgroup `skyroute-dev-dbt`):

```
aws athena start-query-execution --work-group skyroute-dev-dbt --query-string "SELECT count(*), count(DISTINCT booking_id) FROM skyroute_dev_gold.spike_bookings_window" --profile skyroute-dev-local-dbt --region eu-west-3 --no-cli-pager
```

`ProcessedBytes` se consulta con `--profile skyroute-dev-login`, porque `local-dbt` no tiene permisos de CloudWatch (namespace `AWS/Athena`, dimension `WorkGroup=skyroute-dev-dbt`; ajusta `--start-time` y `--end-time` al intervalo de los builds, UTC):

```
aws cloudwatch get-metric-statistics --namespace AWS/Athena --metric-name ProcessedBytes --dimensions Name=WorkGroup,Value=skyroute-dev-dbt --start-time <ISO-8601 inicio> --end-time <ISO-8601 fin> --period 300 --statistics Maximum Sum --profile skyroute-dev-login --region eu-west-3 --no-cli-pager
```

Adjunta tambien `dbt/target/run_results.json` (ninguna consulta cancelada; cada una < 100 MB). Cada `AccessDenied` se anota abajo.

## Acciones IAM que faltan (S5)

Acotadas a recurso: nunca `athena:*` ni `Resource="*"`. Si falta en la boundary, PR de `bootstrap/` (Bootstrap identity); si solo en la inline de `local-dbt`, PR del modulo.

| Accion | Recurso (ARN acotado) | Paso que fallo | Donde se corrige (boundary / inline) |
|--------|-----------------------|----------------|--------------------------------------|
|        |                       |                |                                      |

Ninguna con este alcance (merge, pre_hook DELETE, table, full-refresh).

## Resultados (2026-11-23)

Ejecutado por el owner contra dev con el rol `skyroute-dev-local-dbt`, con credenciales exportadas (`aws configure export-credentials`) y MFA.

Entorno: `aws configure export-credentials --profile skyroute-dev-local-dbt --format env` evita que dbt pida MFA en cada invocacion. Se recomienda en el bloque de entorno.

| Paso | Resultado |
|------|-----------|
| Paso 0 (`bookings_eur`: min, max, count de `date(changed_at)`) | `2026-11-20, 2026-11-20, 132` |
| `dbt debug --target dev` | "All checks passed!". `work_group: skyroute-dev-dbt`, `schema: skyroute_dev_gold`, `s3_data_dir: s3://skyroute-dev-data-437266392155/gold/`, `s3_staging_dir: .../athena-results/` |
| Build 1: `spike_bookings_window` + `window_matches_silver`, `run_date 2026-11-20` | OK created sql incremental model, 132 filas en 4.08s; test PASS; PASS=2 WARN=0 ERROR=0 |
| Build 2: mismo `run_date` | OK 132 en 9.75s (camino incremental: merge con pre_hook DELETE); test PASS; PASS=2 ERROR=0 |
| Build 3: `run_date 2026-11-21` | OK 132 en 9.70s; test PASS; PASS=2 ERROR=0 |
| `spike_bookings_table`, dos veces | OK 132 en 3.72s y OK 132 en 7.51s (la segunda recrea la tabla); PASS=1 ERROR=0 en las dos |
| `--full-refresh spike_bookings_window` | OK 132 en 8.65s; test PASS; PASS=2 ERROR=0 |
| Idempotencia: `count(*), count(DISTINCT booking_id)` en `spike_bookings_window` | `132, 132` |
| AccessDenied | Ninguno |
| `ProcessedBytes` (`AWS/Athena`, `WorkGroup=skyroute-dev-dbt`, 2026-11-23T17:40Z a 17:50Z, periodo 600) | Un datapoint (`2026-11-23T18:40:00+01:00`): `Sum 45154` bytes (45 KB en todo el spike) y `Maximum 4642` bytes (4,6 KB como maximo por consulta), frente al corte de 104857600 bytes (100 MB) del workgroup |

dbt avisa "State adapter: dbt State disabled: target type 'athena' is not supported". Es informativo; el plan no usa dbt state.

**Conclusiones:**

- `merge` mas `pre_hook DELETE` con `incremental_predicates` funciona con Iceberg en dbt-athena 1.11.2 y dbt-core 1.12.7.
- La materializacion `table` recrea la tabla con los permisos de `local-dbt` (GlueGoldWrite).
- El resultado es idempotente con el mismo `run_date`.

**Limites:**

- Solo hay un dia de datos, asi que la ventana no prueba la salida de filas.
- La ventana D-4..D sobre `sessions` queda para la fase 5.

**Coste:** Athena factura un minimo de 10 MB por consulta (dato probable, no verificado, segun aws-researcher), asi que el coste del spike es del orden de centimos o menos.

**Pendiente:** ninguno.

**Veredicto:** Spike 0c: PASS
