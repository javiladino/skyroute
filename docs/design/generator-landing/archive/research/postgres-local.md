---
type: Research
topic: generator-landing
area: postgres-local
---

# Research (área): Postgres local para Reservas

Fecha de consulta de todas las fuentes externas: 2026-11-13. Toda cifra vale solo para esa fecha. Nota de área para consolidar después; no propone soluciones.

## Alcance

- Qué existe hoy: nada. `AGENTS.md` marca como "previsto, aún no existe" `generators/`, `airflow/`, `observability/` y `landing/`, y deja `# TODO: entorno local (make up)`. No hay docker-compose ni DDL en el repo.
- Qué dice el diseño: `docs/design/platform-blueprint/current/project/README.md:28` fija la fuente Reservas (OLTP) como "Postgres local en Docker, incremental por `updated_at`", con "cambios de estado, varias divisas".
- Criterio de hecho de la Fase 2: 6 meses de histórico y micro-lotes nuevos.
- Cubre: versión e imagen, convivencia de compose con Astro/Marquez/OpenMetadata, esquema para extracción incremental, escritura de cambios de estado, vías de extracción a `landing/` (solo opciones), volúmenes/reset, credenciales.
- No cubre: el simulador en sí (otras áreas), Lambda/EventBridge, el diseño de Bronze.
- Reglas de proyecto citadas por nombre (veredicto en `docs/design/CONTEXT.md` § Conventions): Idempotency, Medallion layers, No hourly-billed resources, Compute split, Orchestration runtime.

## Hechos

Cada hecho lleva fuente y fecha de consulta (2026-11-13) salvo los del repo.

### Versión e imagen

- H1. PostgreSQL 18 es la major más reciente soportada; última minor 18.7 (primera release 2025-09-25, fin de soporte 2030-11-14). Otras: 17.12, 16.16, 15.20, 14.25. PG 14 llega a EOL el 2026-11-12. Soporte de 5 años por major; minors al menos cada 3 meses. Fuente: https://www.postgresql.org/support/versioning/
- H2. Imagen oficial Docker `postgres`: `latest` apunta a 18.7 (tags `18`, `18.7`, variantes Debian trixie/bookworm y Alpine). La página lista además una 19rc2 (release candidate). Fuente: https://hub.docker.com/_/postgres
- H3. Desde PG 18 la imagen declara el volumen en `/var/lib/postgresql` y el `PGDATA` por defecto es `/var/lib/postgresql/18/docker`. Para 17 y anteriores el montaje es `/var/lib/postgresql/data`; montar `/var/lib/postgresql` en ellas no persiste datos. Fuente: https://hub.docker.com/_/postgres
- H4. La imagen admite el sufijo `_FILE` (`POSTGRES_PASSWORD_FILE`, `POSTGRES_USER_FILE`, `POSTGRES_DB_FILE`) para leer valores de ficheros, p. ej. Docker secrets en `/run/secrets/...`. Fuente: https://hub.docker.com/_/postgres
- H5. Los scripts `*.sql`, `*.sql.gz`, `*.sh` de `/docker-entrypoint-initdb.d` se ejecutan en orden alfabético solo cuando el directorio de datos está vacío; una base existente no se toca. Fuente: https://hub.docker.com/_/postgres
- H6. Marquez fija `postgres:14` en su compose (sin minor). PG 14 es EOL desde 2026-11-12 (H1). Fuente: https://github.com/MarquezProject/marquez/blob/main/docker-compose.yml

### Convivencia con Astro, Marquez y OpenMetadata

- H7. Astro CLI local: la metadata DB Postgres publica el puerto 5432 y el webserver el 8080. Si el puerto está ocupado, `astro dev start` falla con "Ports are not available: exposing port TCP 0.0.0.0:5432". Se cambian con `astro config set postgres.port <p>` y `astro config set webserver.port <p>`. Fuente: https://www.astronomer.io/docs/astro/cli/troubleshoot-locally
- H8. `astro dev start` levanta 4 contenedores (webserver, scheduler, triggerer, Postgres de metadata). `astro dev kill` borra los datos de esa Postgres (conexiones, logs, historial); `astro dev stop` los conserva. `docker-compose.override.yml` en la raíz del proyecto Astro añade servicios; los ejemplos los conectan a una red llamada `airflow`. Los overrides solo valen en modo contenedor. Fuente: https://www.astronomer.io/docs/astro/cli/run-airflow-locally
- H9. Marquez: servicios `api` (puertos `${API_PORT}`, `${API_ADMIN_PORT}`) y `db` (`postgres:14`, puerto `${POSTGRES_PORT}:${POSTGRES_PORT}`); volúmenes con nombre `data`, `db-conf`, `db-init`, `db-backup`; credenciales por defecto en el propio compose (`POSTGRES_PASSWORD=password`, `MARQUEZ_PASSWORD=marquez`). Los números de puerto salen de un `.env` no incluido en el fichero. Fuente: https://github.com/MarquezProject/marquez/blob/main/docker-compose.yml
- H10. OpenMetadata local: UI/API en 8585-8586, Airflow de ingesta en 8080, Elasticsearch en 9200/9300; base MySQL (`docker-compose.yml`) o PostgreSQL (`docker-compose-postgres.yml`), puertos de BD no publicados en el ejemplo; pide al menos 6 GiB de memoria y 4 vCPU para Docker; la red aparece como `metadata_app_net` (y como `openmetadata_app_net` en la sección de troubleshooting). Fuente: https://docs.open-metadata.org/latest/quick-start/local-docker-deployment
- H11. Resumen de colisiones por defecto documentadas: 5432 (Astro metadata Postgres; también el puerto estándar de cualquier Postgres) y 8080 (webserver Astro y Airflow de OpenMetadata). Derivado de H7, H10.

### Esquema para extracción incremental

- H12. `now()`, `transaction_timestamp()` y `CURRENT_TIMESTAMP` devuelven el inicio de la transacción, fijo durante toda ella; `statement_timestamp()` el inicio de la sentencia; `clock_timestamp()` la hora real en cada llamada. Un `timestamptz` se almacena internamente en UTC y se muestra según el `TimeZone` de la sesión. Fuente: https://www.postgresql.org/docs/current/functions-datetime.html
- H13. Un trigger `BEFORE UPDATE ... FOR EACH ROW` puede modificar `NEW`; el manual lo ejemplifica con una función que asigna `NEW.updated_at := now()`. Con varios triggers del mismo tipo, el orden es alfabético por nombre. Los cambios de un BEFORE trigger no cuentan para `UPDATE OF columna`. Fuente: https://www.postgresql.org/docs/current/sql-createtrigger.html
- H14. Un `BEFORE DELETE` se dispara antes del borrado; un DELETE físico no deja fila que un filtro por `updated_at` pueda leer (consecuencia directa de que la fila desaparece; la página de CREATE TRIGGER indica que los cambios a `NEW` no aplican a DELETE). Fuente: https://www.postgresql.org/docs/current/sql-createtrigger.html
- H15. Por tanto, con H12 y H13, el valor de `updated_at` fijado con `now()` es el inicio de la transacción, no su commit. Una transacción larga puede confirmar con un `updated_at` anterior al de filas ya confirmadas y ya leídas. Derivado de H12; el patrón de "commit tardío con `updated_at` antiguo" lo describe también una fuente secundaria (ver H16).
- H16. Fuentes secundarias sobre extracción por watermark: la transacción larga que se hace visible tras capturar el límite superior es el hueco principal; mitigaciones citadas: fijar el límite superior de la ejecución antes de extraer, guardar el checkpoint solo tras cargar con éxito, comparar con `>=` por timestamps idénticos, derivar el watermark de los registros realmente leídos, ventana de solapamiento mayor que la transacción más larga esperada, deduplicar en destino (upsert por clave primaria); alternativa: CDC por log de transacciones. Ninguna fuente dio un tamaño concreto de solapamiento. Fuentes: https://oneuptime.com/blog/post/2026-01-30-data-pipeline-incremental-extraction/markdown ; https://oneuptime.com/blog/post/2026-01-30-data-pipeline-timestamp-based-cdc/markdown (vistas solo como resultado de búsqueda, no abiertas íntegras).

### Extracción hacia `landing/` (hechos de herramientas)

- H17. Spark JDBC (docs 4.3.0): requiere el JAR del driver en el classpath; `partitionColumn`, `lowerBound`, `upperBound`, `numPartitions` van juntos y `partitionColumn` debe ser numérica, fecha o timestamp; los bounds solo fijan el stride, no filtran filas; `query` y `partitionColumn` no se combinan (hay que usar `dbtable` con subconsulta y alias); `fetchsize` por defecto 0. Fuente: https://spark.apache.org/docs/latest/sql-data-sources-jdbc.html
- H18. `COPY (consulta) TO STDOUT WITH (FORMAT csv, HEADER)` y `\copy` de psql (lado cliente) existen; `COPY ... TO 'ruta'` escribe en el servidor y exige superusuario o `pg_write_server_files`. Formatos de `COPY`: `text`, `csv`, `binary`; no Parquet. En CSV, NULL sale como cadena vacía sin comillas. Fuente: https://www.postgresql.org/docs/current/sql-copy.html
- H19. Repo: Compute split dice que Spark escribe Bronze y Silver; `landing/` guarda archivos crudos tal cual con lifecycle de 30 días (Medallion layers). La Convention Orchestration runtime sitúa Airflow en Docker local (Astro CLI). Fuente: `docs/design/CONTEXT.md:39-41`.

## Opciones observadas

Sin recomendación; se listan para que Propose elija.

### Compose y red

- O1. Un compose propio de Postgres de datos (p. ej. bajo `generators/` o en la raíz) con puerto de host distinto de 5432 y 8080 libres; Astro conserva 5432 (H7).
- O2. Mantener 5432 para Postgres de datos y mover Astro con `astro config set postgres.port` (H7).
- O3. Poner la BD de datos en `docker-compose.override.yml` del proyecto Astro (H8), compartiendo su ciclo de vida; `astro dev kill` afecta a la metadata DB, no está documentado qué pasa con volúmenes de servicios añadidos (ver No verificado).
- O4. Postgres de datos en una red Docker externa y con nombre fijo, a la que se unen Airflow (vía override), Marquez y OpenMetadata, frente a acceso solo por `localhost:<puerto>` del host.
- O5. Marquez y OpenMetadata mantienen su Postgres/MySQL propio (H9, H10) frente a reutilizar la instancia de datos con bases/roles separados.
- O6. Tag de imagen: `postgres:18` (minor flotante), `postgres:18.7` (fijo) o 17; Marquez usa 14 (H6, H1). Montaje del volumen según versión (H3).

### Esquema de `bookings`

- O7. Columna `updated_at timestamptz NOT NULL` con índice (simple sobre `updated_at` o compuesto `(updated_at, booking_id)`), frente a `timestamp` sin zona (H12 muestra que `timestamptz` guarda UTC).
- O8. `updated_at` mantenido por trigger BEFORE UPDATE con `now()` o `clock_timestamp()` (H12, H13) frente a asignado por el generador desde la fecha simulada.
- O9. Borrados: DELETE físico (invisible al filtro, H14), soft-delete con `deleted_at`/estado `cancelled` que además actualiza `updated_at`, o tabla de eventos/historial de estados aparte.
- O10. Modelo de cambios de estado: una fila viva por reserva (estado actual, `updated_at` cambia) frente a fila viva más tabla append-only de transiciones; en ambos, divisa por reserva (`currency`, importe en unidades menores o `numeric`) con la cuestión de tipos del lado Spark/Iceberg abierta.
- O11. Hueco de commit tardío: ventana de solapamiento sobre el watermark con dedupe aguas abajo, límite superior fijo por ejecución, o CDC por log (H16). Con el límite fijado por la fecha lógica del DAG, el rango de cada ejecución es determinista.

### Cómo escribe el generador 6 meses de historia

- O12. Backfill en masa: insertar reservas con `created_at`/`updated_at` repartidos en 6 meses y luego aplicar transiciones de estado en orden temporal, con `updated_at` asignado por la app (necesario para que el trigger con `now()` no colapse todo el histórico en el instante de carga).
- O13. Generación por día simulado: un bucle que avanza la fecha lógica y por cada día inserta altas y actualiza estados (confirmada, modificada, cancelada, reembolsada…), reproducible por semilla.
- O14. Micro-lotes posteriores: el mismo generador (Lambda/EventBridge según la fase) o un proceso local que escribe en Postgres con `updated_at` reciente; el criterio de hecho pide que "lleguen micro-lotes nuevos".

### Extracción a `landing/`

- O15. Quién lee: tarea de Airflow local (Astro) con un script Python; un job Spark local; o un job Glue (que no alcanzaría el Postgres local, ver Tensiones).
- O16. Spark JDBC (H17): lectura con filtro por `updated_at` en `dbtable` subconsulta, driver JAR a distribuir; Spark escribe Bronze/Silver, no `landing/` (H19).
- O17. Export Python: `psycopg` + `COPY ... TO STDOUT` CSV o consulta paginada, serializado a JSON/CSV (Parquet exigiría una librería externa, H18) y subido a S3 `landing/`.
- O18. Formato del archivo en `landing/` (CSV, JSON lines, Parquet) y particionado por fecha lógica en la ruta, con nombre determinista por ejecución; el README del blueprint no fija formato para Reservas (solo para otras fuentes, líneas 27-30).

### Volúmenes, reset y credenciales

- O19. Volumen con nombre (se conserva entre `down` y `up`) frente a bind mount a una carpeta ignorada por git; reset con eliminación del volumen frente a regenerar la base desde cero con el generador y semilla fija. Los scripts de `initdb.d` solo corren con datos vacíos (H5).
- O20. Credenciales: `.env` ignorado por git más `.env.example` versionado; `POSTGRES_PASSWORD_FILE` con fichero ignorado (H4); Docker secrets; variables de Airflow/Connection. Marquez trae credenciales por defecto en claro en su compose (H9).

## Tensiones con Conventions

Registradas sin resolver.

- T1. Idempotency vs `updated_at` automático: "depende solo de la fecha lógica, nunca de `now()`". Un trigger que usa `now()` (H12, H13) o el filtro "desde el último watermark hasta ahora" introducen el reloj; el rango por fecha lógica y la extracción con solapamiento (O11) tendrían que convivir con esa regla. Además, una re-ejecución de un día pasado leerá el estado actual de la fila, que puede haber cambiado desde la ejecución original.
- T2. Idempotency vs backfill del generador: el generador escribe en una fuente OLTP mutable; "relanzar un día da el mismo resultado" no es aplicable a las filas de origen salvo que el generador sea determinista por semilla y fecha.
- T3. Medallion layers (`landing/` = archivos crudos tal cual, 30 días) vs 6 meses de histórico: si el histórico se materializa solo en Postgres y se exporta en pocas ejecuciones, `landing/` caduca a 30 días; la ruta de reproceso desde `landing/` solo cubre 30 días de archivos, y el origen es lo único que conserva los 6 meses.
- T4. Medallion layers vs Compute split: "Spark escribe Bronze y Silver"; la extracción Postgres → `landing/` no es una capa de Spark. La Convention no dice quién escribe `landing/`; el export Python (O17) y el Spark JDBC (O16) tienen lectura distinta de la regla.
- T5. No hourly-billed resources / "sin VPC privada" vs Postgres local: los jobs Glue (Flex) corren en AWS y no alcanzan un Postgres en Docker local sin exponerlo; la extracción debe correr en local (el brief ya lo asume). Una instancia gestionada (RDS) queda excluida por la Convention.
- T6. Orchestration runtime ("DAG desplegable en MWAA sin cambios") vs conexión a Postgres local: el host y la red del Postgres de datos deben ser configurables por Connection/variable y no depender de nombres de red de Astro.
- T7. Región/AWS vs Postgres local: el histórico del generador y el Postgres viven fuera de Terraform (IaC only se aplica a recursos AWS); no se evaluó aquí si ese reparto contradice la Convention IaC only (ver Preguntas).
- T8. Diseño vs versión: el blueprint no fija versión de Postgres; la imagen más usada del ecosistema citado (Marquez) está en 14, que es EOL desde 2026-11-12 (H1, H6).

## Preguntas para el owner

- P1. ¿La instancia Postgres de datos debe arrancar con `make up` junto a Airflow y observabilidad, o es un compose independiente? (`AGENTS.md` deja `make up` como TODO.)
- P2. ¿Qué puerto de host se reserva para el Postgres de datos, y cede Astro el 5432?
- P3. ¿Versión objetivo de Postgres: 18 (actual) o alinear con otra? ¿Se fija minor?
- P4. ¿`updated_at` lo fija el trigger con el reloj real o el generador con la fecha simulada? Afecta a T1/T2.
- P5. ¿Se permiten DELETE físicos en `bookings` o solo cancelaciones/soft-deletes? ¿La tabla de historial de estados forma parte del alcance de la fuente?
- P6. ¿Qué archivo y formato espera `landing/` de Reservas (CSV, JSON, Parquet) y quién lo escribe (Airflow, Spark local)? Afecta a T3/T4.
- P7. ¿Dónde viven los 6 meses de histórico a efectos de reproceso, dado el lifecycle de 30 días de `landing/` (T3)?
- P8. ¿El tamaño del solapamiento y la zona horaria de referencia (UTC) son decisión del owner o de Propose?
- P9. ¿Qué divisas y qué reglas de conversión entran en el origen (importes por divisa, sin conversión en OLTP)?

## No verificado

1. Que Docker Compose cree redes con nombre fijo/compartible entre proyectos y el nombre real de la red de Astro (la doc de Astro no lo indica; solo los ejemplos de override usan `airflow`).
2. Puerto del API server de Airflow 3 en Astro (la página no lo da; solo 8080 del webserver y 5432).
3. Qué ocurre con servicios y volúmenes añadidos vía `docker-compose.override.yml` ante `astro dev kill`.
4. Valores de `.env` de Marquez (puertos por defecto): el compose los lee de variables no mostradas.
5. Compatibilidad de la imagen `postgres:18` con el cliente JDBC y el driver Spark concreto a usar (versión del driver no investigada).
6. La existencia y estado de PG 19 más allá de que Docker Hub lista "19rc2"; no se abrió la página de release.
7. Tamaño razonable de la ventana de solapamiento: ninguna fuente lo da (solo "mayor que la transacción más larga esperada").
8. Los dos artículos de oneuptime (H16) se leyeron solo como extracto de búsqueda, no íntegros; son fuentes secundarias.
9. Que un DELETE físico no sea visible por `updated_at` está deducido del comportamiento general; la fuente solo documenta triggers (H14).
10. Que `landing/` y el histórico de 6 meses no tengan otra fuente de verdad: no se leyó ningún `context.md` ni proposal de `generator-landing` más allá del contexto del brief.
11. Estado de la Convention IaC only respecto a un Postgres local fuera de Terraform (T7): no se leyó su texto completo.
