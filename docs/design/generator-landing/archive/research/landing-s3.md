---
type: Research
---

# generator-landing: nota de área, `landing/` en S3 y su ciclo de vida

> **Fecha:** 2026-11-13. Nota de área de la etapa Research del topic `generator-landing`. Solo describe lo que existe hoy y los hechos externos; no propone ni elige (método `reppit-research`). Review adversarial: no ejecutada en esta nota; la ejecuta el orquestador sobre el `research.md` consolidado. Toda cifra de precio o comportamiento de AWS vale solo para la fecha de consulta (2026-11-13).

## Alcance

Qué existe hoy en el repo para un bucket de datos (nada) y qué documenta AWS sobre: nombre y layout por entorno del bucket con la capa `landing/`; layout de claves por fuente y fecha; regla de lifecycle de 30 días con versioning, delete markers y objetos con fecha pasada; cifrado SSE-S3 frente a KMS; public access block, política solo-TLS y access logging; checks de checkov que dispara un bucket de datos y cómo los trató `state_bucket.tf`; coste de S3 en eu-west-3 para el volumen estimado. Incluye la tensión entre el criterio de hecho de la Fase 2 (6 meses de histórico) y el lifecycle de 30 días de la Convention.

Fuera de alcance: elegir opción, diseñar el módulo Terraform, permisos de CI para el bucket (nota `ci-permissions.md`), volúmenes por fuente (nota `generator-data.md`, de la que se reutilizan cifras con su etiqueta de supuesto).

Reglas vigentes que no se reabren: Convention "Medallion layers" (`landing/`: archivos crudos tal cual, lifecycle de 30 días), "Region" (`eu-west-3`), "IaC only", "Apply gate", "Idempotency", "No hourly-billed resources". Criterio de hecho de la Fase 2, literal: "Simulador OTA coherente, Lambda + EventBridge, Postgres local, archivos en `landing/`. Hecho cuando hay 6 meses de histórico y llegan micro-lotes nuevos."

## Hechos

### H1. Estado del repo: no existe bucket de datos

- `infra/terraform/` solo contiene `bootstrap/` (AGENTS.md § Mapa del repo: `modules/` y `envs/{dev,prod}/` son "previstos"). El único bucket Terraform es el de state, `infra/terraform/bootstrap/state_bucket.tf:1`. Su nombre viene de `var.state_bucket_name` (`:2`); no hay convención de nombres para buckets de datos.
- La Convention "Medallion layers" nombra `landing/` como prefijo/capa ("archivos crudos tal cual, lifecycle de 30 días") sin fijar si es prefijo de un bucket compartido o un bucket propio. Tampoco fija el número de buckets por entorno.
- El blueprint (citado en `generator-data.md`, H1) lista 5 fuentes: clickstream (JSON, micro-lotes cada 15 min por Lambda + EventBridge), reservas (Postgres local, incremental por `updated_at`), gasto publicitario (CSV por plataforma), CRM y tipos de cambio (API BCE, diario).

### H2. Patrón S3 existente: `state_bucket.tf`

Fuente: `infra/terraform/bootstrap/state_bucket.tf`.

| Control | Líneas | Valor |
|---|---|---|
| Borrado | `:3`, `:10-12` | `force_destroy = false`, `prevent_destroy = true` |
| Cifrado | `:15-23` | SSE-S3 (`sse_algorithm = "AES256"`), sin KMS |
| Versioning | `:25-31` | `Enabled` |
| Public access block | `:33-40` | los cuatro flags en `true` |
| Ownership | `:42-48` | `BucketOwnerEnforced` |
| Política | `:50-82` | `DenyInsecureTransport` (`aws:SecureTransport = false`, `s3:*`, bucket y `/*`) y `DenyDeleteBucket`; `depends_on` el public access block |
| Lifecycle | `:84-107` | una regla con `filter {}` (todo el bucket): `noncurrent_version_expiration` 90 días, `expired_object_delete_marker = true`, `abort_incomplete_multipart_upload` 7 días; `depends_on` el versioning |
| Access logging | (ausente) | no hay `aws_s3_bucket_logging`; el skip de CKV_AWS_18 lo justifica (`:7`) |

El bucket de state es de un solo entorno y vive en `bootstrap/`. Los dos entornos de datos (`envs/dev`, `envs/prod`) no existen aún.

### H3. Checks de checkov y cómo los trató `state_bucket.tf`

Fuente en el repo: `state_bucket.tf:5-8` y `docs/design/foundations/current/test.md:97` (el fallo se resolvió con 4 skips `#checkov:skip=ID:motivo`, con aprobación del owner, porque checkov corre sin `--soft-fail`).

| Check | Skip en state | Motivo escrito en el skip |
|---|---|---|
| CKV_AWS_145 (KMS en el bucket) | sí (`:5`) | "Decisión del owner SSE-S3, sin KMS (Convention No hourly-billed resources)" |
| CKV_AWS_144 (réplica cross-region) | sí (`:6`) | "Convention Region... sin réplica cross-region" |
| CKV_AWS_18 (access logging) | sí (`:7`) | "Un bucket de logs adicional queda fuera de alcance de Fase 1 por coste y alcance" |
| CKV2_AWS_62 (notificaciones de eventos) | sí (`:8`) | "No hay consumidores de eventos del state" |

Comprobado por el repo: los checks de versioning, public access block, cifrado por defecto y lifecycle no necesitaron skip en el bucket de state, que los implementa (`:15-40`, `:84-107`).

Un bucket de datos con el mismo patrón: los cuatro IDs anteriores aparecen en el repo como los que dispararon en un bucket con ese patrón. Los motivos de CKV2_AWS_62 y CKV_AWS_18 escritos para state hablan de "state"/"Fase 1"; que esos motivos valgan para el bucket de datos no está dicho en el repo. El resto de IDs de checkov (versioning, PAB, lifecycle) no se verificaron contra la documentación de checkov (ver No verificado).

### H4. Cómo cuenta S3 la edad de un objeto para el lifecycle

Fuente: AWS, "Lifecycle configuration elements", https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html, recuperado 2026-11-13.

- `Days` en `Expiration` es "el número de días desde la creación del objeto". S3 suma los días a la hora de creación y redondea hacia arriba a la siguiente medianoche UTC (ejemplo de la doc: creado 15/1/2014 10:30 UTC con 3 días, acción 19/1/2014 00:00 UTC).
- "Amazon S3 maintains only the last modified date for each object... the creation date is synonymous with the Last modified date." Reescribir un objeto con la misma clave cambia esa fecha.
- La regla filtra por prefijo (`Filter.Prefix`), tags, tamaño o combinación; un filtro vacío aplica a todo el bucket. El lifecycle no lee fechas dentro de la clave.
- Consecuencia directa de lo anterior (inferencia, no cita literal): un objeto con clave `ingest_date=2026-05-13/` subido hoy tiene edad cero hoy; su expiración cuenta desde hoy, no desde mayo. No hay forma documentada de poner una fecha de creación pasada con `PutObject` (no se encontró en la doc consultada).
- Variante por fecha: una acción con `Date` (ISO 8601, medianoche UTC). "If you specify an S3 Lifecycle action with a date that is in the past, all qualified objects become immediately eligible"; y el date-based no es de una sola vez, sigue aplicándose a objetos nuevos mientras la regla esté `Enabled`. No se puede crear en consola.
- Al añadir una configuración, aplica a objetos existentes y nuevos: los objetos con prefijo que ya tengan más de 30 días se encolan para borrado (https://docs.aws.amazon.com/AmazonS3/latest/userguide/how-to-set-lifecycle-configuration-intro.html, 2026-11-13).
- Retraso: S3 encola las expiraciones de forma asíncrona; puede tardar "days or even weeks" en borrar tras cumplirse la regla, sin garantía de plazo. No se factura el almacenamiento desde que el objeto es elegible, aunque no se haya borrado todavía (misma página, sección "Changes in billing").
- Propagación de la configuración: unos minutos tras crearla o cambiarla.
- Una política de bucket no puede impedir un borrado de lifecycle: "even if your bucket policy denies all actions for all principals, your S3 Lifecycle configuration still functions as normal" (https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html, 2026-11-13).
- No hay cargo por acciones de expiración; los costes potenciales solo aparecen con clases con duración mínima (misma página). La clase por defecto es Standard.

### H5. Lifecycle con versioning activado

Fuente: AWS, "Expiring objects", https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html, y "Lifecycle configuration elements" (H4), recuperados 2026-11-13.

- Bucket sin versioning: `Expiration` borra el objeto de forma permanente.
- Bucket con versioning enabled: si la versión actual no es delete marker, `Expiration` crea un delete marker (nueva versión actual) y la versión previa pasa a noncurrent. No libera almacenamiento por sí sola.
- `Expiration` solo afecta a la versión actual. Las versiones noncurrent solo se borran con `NoncurrentVersionExpiration` (días desde que la versión pasó a noncurrent, contados desde la creación del sucesor; opcional `NewerNoncurrentVersions`, entre 1 y 100, que exige `Filter`).
- Si el delete marker es la versión actual y existen otras versiones, S3 no hace nada con él. Cuando solo queda el delete marker (expired object delete marker), S3 lo elimina; `ExpiredObjectDeleteMarker` / `expired_object_delete_marker = true` lo pide explícitamente. Esta acción no puede ir en una regla con filtro por tags.
- `AbortIncompleteMultipartUpload` es una acción aparte; tampoco puede ir en una regla con filtro por tags.
- Un objeto es elegible para una sola acción de lifecycle por día; borrado permanente prevalece sobre transición, y transición sobre crear delete markers.
- Una regla de 30 días solo en `Expiration` (current) en un bucket versionado deja los datos físicamente presentes como noncurrent hasta que otra acción los borre; el almacenamiento noncurrent se factura al precio de la clase. Hecho derivado de las dos citas anteriores (no hay cita literal de facturación para noncurrent en las páginas leídas; ver No verificado).
- El patrón existente en `state_bucket.tf:84-107` usa `filter {}` y 90 días noncurrent, no un prefijo y no `expiration { days }` sobre la versión actual; no hay hoy ninguna regla de 30 días en el repo.
- Con la regla de idempotencia (misma clave reescrita al relanzar un día): en un bucket versionado cada reescritura crea una versión nueva y deja la anterior como noncurrent; en uno no versionado la reescritura sustituye el objeto y reinicia la fecha de creación (H4).

### H6. Cifrado: SSE-S3 frente a SSE-KMS

Fuentes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html y https://aws.amazon.com/kms/pricing/, recuperadas 2026-11-13.

- SSE-S3 se aplica por defecto a todo bucket nuevo y a las subidas nuevas desde el 5-ene-2023, sin coste adicional ni impacto de rendimiento.
- SSE-KMS tiene "additional charges for using AWS KMS keys". Cifras del KMS pricing: clave gestionada por el cliente $1,00 por clave y mes; $0,03 por 10.000 peticiones simétricas (el dato sale del ejemplo de S3 de la página, no de una tabla propia); capa gratuita de 20.000 peticiones al mes, contada en todas las regiones. La clave administrada por AWS (`aws/s3`) no se cotizó en esta nota.
- Cada `PutObject`/`GetObject` de un objeto SSE-KMS exige permisos KMS (`kms:GenerateDataKey` para subir, `kms:Decrypt` para leer) en la identidad del llamante: la Lambda del generador, Spark/Glue y Athena. Las peticiones deben ir por TLS.
- S3 Bucket Keys reducen las peticiones a KMS "hasta un 99 %".
- Un bucket destino de access logs debe usar SSE-S3; con SSE-KMS por defecto S3 puede entregar logs que no se pueden leer.
- Precedente del repo: el state usa SSE-S3 y el skip de CKV_AWS_145 cita decisión del owner (`state_bucket.tf:5`). No hay decisión del owner sobre el cifrado del bucket de datos.

### H7. Public access block, TLS-only y access logging

- Public access block y política `DenyInsecureTransport`: ya implementados en el patrón del repo (H2).
- Access logging (https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-server-access-logging.html, 2026-11-13): sin cargo por activarlo, pero los logs entregados pagan almacenamiento normal. El destino debe estar en la misma región y cuenta; la doc recomienda un bucket distinto, porque entregar al propio bucket origen crea un bucle infinito de logs; el destino no puede tener Object Lock; con Object Ownership `BucketOwnerEnforced` la entrega se concede por política a `logging.s3.amazonaws.com` (con `aws:SourceArn` y `aws:SourceAccount`), no por ACL. La entrega puede tardar horas y es de mejor esfuerzo.
- En el repo, el único bucket existente no activa access logging (H2/H3).

### H8. Precios de S3 en eu-west-3

Fuente: archivo oficial de precios `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/eu-west-3/index.json`, versión 20261109154310 (publicación 2026-11-09T15:43:10Z), recuperado 2026-11-13. La página `https://aws.amazon.com/s3/pricing/` no mostró las tablas por región en la recuperación.

| Concepto | Precio USD | SKU / descripción de la oferta |
|---|---|---|
| Almacenamiento Standard, primeros 50 TB | 0,024 por GB-mes | SKU `4PMVMK58J94ER67S` (`EUW3-TimedStorage-ByteHrs`) |
| PUT, COPY, POST o LIST | 0,0053 por 1.000 peticiones (0,0000053 por petición) | SKU `JSTCNSNFYXFKBECA` (`EUW3-Requests-Tier1`) |
| GET y otras peticiones | 0,0042 por 10.000 (0,00000042 por petición) | SKU `9PAT6GAN57PYFYDZ` (`EUW3-Requests-Tier2`) |
| Expiración por lifecycle | sin cargo | https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html |

Los precios de transferencia, de request de lifecycle a otras clases y de la clave `aws/s3` no se consultaron.

### H9. Aritmética de coste para el volumen estimado

Entradas de volumen, reutilizadas de `docs/design/generator-landing/working/research/generator-data.md` (H1 y H5, sin fuente externa; son supuestos de esa nota): 96 micro-lotes/día de clickstream; 50.000-200.000 eventos/día (blueprint, central 125.000); 500-800 B por evento sin comprimir; 182 días de histórico; gasto publicitario 3 CSV/día (3 plataformas); CRM 1 JSON/día; FX 1 valor/día. Supuesto añadido aquí (no verificado): 1 archivo/día de extracción incremental de reservas; si no hay archivo, restar 1. Otros archivos diarios: 3 + 1 + 1 + 1 = 6. Tamaño de los archivos diarios no medido; se desprecia en el almacenamiento.

Escritura (PUT, por entorno que reciba esos archivos):

- Por día: 96 + 6 = 102 PUT.
- Régimen estable, 30 días: 102 × 30 = 3.060 PUT. 3.060 × 0,0000053 = 0,0162 USD/mes.
- Backfill de 182 días: (96 + 6) × 182 = 18.564 PUT. 18.564 × 0,0000053 = 0,0984 USD, una vez.
- Lectura (GET) si Bronze lee cada archivo una vez: 3.060 × 0,00000042 = 0,0013 USD/mes; backfill: 18.564 × 0,00000042 = 0,0078 USD.
- Cada reproceso de un día repite sus 102 PUT (idempotencia, H5): 102 × 0,0000053 = 0,00054 USD.

Almacenamiento (solo clickstream; sin compresión):

| Escenario | MB/día | 30 días (GB) | USD/mes (× 0,024) | 182 días (GB) | USD/mes (× 0,024) |
|---|---|---|---|---|---|
| Mínimo: 50.000 × 500 B | 25 | 0,75 | 0,018 | 4,55 | 0,109 |
| Central: 125.000 × 500 B | 62,5 | 1,875 | 0,045 | 11,375 | 0,273 |
| Central: 125.000 × 800 B | 100 | 3,0 | 0,072 | 18,2 | 0,437 |
| Máximo: 200.000 × 800 B | 160 | 4,8 | 0,115 | 29,12 | 0,699 |

(GB decimal; 1 GB = 1.000 MB. La facturación de AWS usa GB-mes; la diferencia con GiB no cambia el orden de magnitud.)

Con compresión gzip supuesta de 8-10:1 (supuesto de `generator-data.md`), los GB de la tabla se dividirían entre 8-10. Los archivos de 0,3-1,7 MB por micro-lote son pequeños, y el coste dominante son las peticiones, no el almacenamiento (H8: 0,0053 USD por 1.000 PUT).

Dos entornos: dev y prod duplican la columna de PUT y almacenamiento solo si ambos reciben el mismo volumen; el volumen de dev no está definido.

Con SSE-KMS (H6), peticiones de KMS en el mismo régimen estable: unos 3.060 PUT + 3.060 GET ≈ 6.120 al mes, por debajo de la capa gratuita de 20.000 (compartida con cualquier otro uso de KMS en la cuenta). La cuota fija de $1,00 por clave y mes, por entorno, es lo que cambia la factura: 2 claves = 2,00 USD/mes. El presupuesto del proyecto es 10 USD (CONTEXT.md, Active Context).

Versioning activado: el almacenamiento noncurrent se suma al de la versión actual hasta que una regla lo borre (H5); el coste de reescrituras idempotentes depende de cuántas reescrituras ocurran, no estimado.

## Opciones observadas

Sin recomendación. Cada fila describe qué implica la opción según los hechos anteriores.

### O1. Dónde vive `landing/`

| Opción | Qué implica (hechos) |
|---|---|
| Un bucket de datos por entorno con prefijos de capa (`landing/`, `bronze/`, `silver/`, `gold/`...) | Las Conventions nombran las capas como carpetas/prefijos; la regla de lifecycle de 30 días se filtra por prefijo `landing/` (H4: el filtro por prefijo está documentado); la política de bucket, el cifrado, el versioning y el access logging son únicos para todas las capas, es decir, el versioning de `landing/` es el mismo que el de Bronze. Un solo bucket por entorno reduce el número de recursos de Terraform y de checks. |
| Un bucket dedicado a `landing/` por entorno, aparte del de datos | Versioning, cifrado y lifecycle independientes; la regla puede ser `filter {}` como en `state_bucket.tf:91`; más recursos, más skips de checkov por bucket (H3: cada bucket repite 4 skips) y un ARN más en los permisos de CI y de la Lambda. |
| Nombre | El repo no tiene variable de prefijo ni de cuenta. El bucket manual existente `skyroute-tfstate-demo-437266392155-eu-north-1-an` (CONTEXT.md, Apply gate) y `var.state_bucket_name` (`state_bucket.tf:2`) muestran que el nombre del state lo fija una variable. Los nombres de bucket son globales y de DNS; la doc de naming no se consultó (ver No verificado). |

### O2. Layout de claves por fuente y fecha

- Patrón de la tarea: `landing/<source>/ingest_date=YYYY-MM-DD/...`. Bronze debe llevar `_ingest_date` y `_source_file` (Convention "Medallion layers"), por lo que la clave debe permitir reconstruirlos.
- Hecho para idempotencia: la Convention "Idempotency" exige que relanzar un día dé el mismo resultado y que dependa solo de la fecha lógica, no de `now()`. Una clave determinista derivada de `(source, run_date, slot)` hace que un relanzamiento sobrescriba el mismo objeto (H5: en versioning crea una versión noncurrent; sin versioning reinicia la edad). Una clave con `now()` o un UUID crea objetos distintos en cada reintento.
- Las dos formas de identificar un micro-lote observadas en `generator-data.md`: `(run_date, slot)` con 96 slots por día. Un nombre de archivo con `slot` (0-95 o `HHMM`) es una función de la fecha lógica.
- Un sufijo con compresión (`.json.gz`) o sin ella cambia el tamaño (H9) pero el repo no fija el formato de archivo del landing.
- `ingest_date` frente a fecha de evento: los eventos tardíos (hasta 72 h, según `generator-data.md`) pertenecen a un `ingest_date` posterior al de su fecha de evento; el nombre de partición de la clave no es la fecha de evento.
- Estilo `key=value` (tipo Hive): lo usa el ejemplo de la tarea; un estilo `YYYY/MM/DD` es el otro que aparece en la doc de access logs (`[YYYY]/[MM]/[DD]`). No se verificó cuál leería mejor Spark/Glue.

### O3. Cifrado

| Opción | Hechos |
|---|---|
| SSE-S3 | Gratis (H6); coincide con el state (H2); el skip de CKV_AWS_145 aplica igual (H3). |
| SSE-KMS con clave propia | $1,00/clave/mes más peticiones (H9); añade permisos KMS a Lambda, Glue y Athena; no encaja con un destino de access logs (H6); CKV_AWS_145 deja de dispararse. |
| SSE-KMS con `aws/s3` | No se cotizó. |

### O4. Lifecycle de `landing/` con versioning

| Opción | Hechos |
|---|---|
| Sin versioning en el bucket de `landing/` | `Expiration` de 30 días borra de verdad (H5). Idempotencia por reescritura sustituye el objeto. Requiere bucket dedicado o aceptar que no hay versioning en todo el bucket. CKV_AWS_21 (versioning) se dispararía; no verificado (ver No verificado). |
| Versioning activado y regla `Expiration` 30 días + `NoncurrentVersionExpiration` N días + `expired_object_delete_marker` + `abort_incomplete_multipart_upload` (patrón de `state_bucket.tf:84-107` con prefijo) | Tras 30 días + N días los datos desaparecen físicamente; entre medias están noncurrent y se facturan (H5). |
| Versioning activado y regla solo de `Expiration` | Los objetos quedan como noncurrent indefinidamente (H5). |

### O5. Tensión de histórico (ver la sección siguiente)

Las opciones que los hechos permiten, descritas sin pick:

1. **El histórico va directo a Bronze.** El generador escribe los 182 días a Bronze (o ejecuta Spark sobre una fuente local), sin pasar por `landing/`; solo los micro-lotes nuevos usan `landing/`. Hecho: `landing/` deja de ser el origen único de Bronze (`_source_file` apuntaría a otra ruta para el histórico); el criterio de hecho dice "archivos en `landing/`" y "6 meses de histórico" como dos cosas; el histórico no pasa por la validación de los archivos de landing.
2. **El histórico se regenera bajo demanda.** Hecho: la regeneración es determinista si las semillas son función de `run_date`/`slot` (`generator-data.md` H3-H4); cada regeneración repite el backfill de PUT (18.564 PUT ≈ 0,10 USD, H9) y vuelve a empezar la cuenta de 30 días para esos objetos (H4). `landing/` contiene 6 meses solo durante los 30 días siguientes a cada backfill.
3. **El lifecycle de 30 días se aplica solo tras la ingesta a Bronze.** Hecho: el lifecycle de S3 no sabe qué ha ingerido Bronze (H4: filtra por prefijo, tag, tamaño; cuenta desde la creación). Observables que sí filtra: un tag de objeto. Una regla filtrada por tag (por ejemplo un tag que se pone tras la ingesta) es posible según la doc (H4), con dos limitaciones documentadas: `expired_object_delete_marker` y `abort_incomplete_multipart_upload` no pueden ir en una regla con filtro por tags (H5); y poner un tag es una petición `PutObjectTagging` adicional, cuyo precio no se consultó. La expiración sigue contando desde la creación.
4. **Prefijo de histórico excluido del lifecycle.** Hecho: la regla se filtra por prefijo (H4), así que un prefijo distinto (por ejemplo, otra carpeta bajo `landing/` o fuera) no expiraría; la Convention "Medallion layers" dice "`landing/`... lifecycle de 30 días" y no hay hoy un ruling que prevea una excepción. Es un cambio de la Convention o una carpeta no considerada `landing/`.
5. **Dejar que expire y reintentar.** Hecho: se acepta que a los 30 días el histórico no esté; para reprocesar Bronze habría que regenerar (opción 2).
6. **Ampliar la retención de `landing/`.** Hecho: 182 días a ~11-18 GB cuesta 0,27-0,44 USD/mes (H9). Es un cambio de la Convention y lo decide el owner.

## Tensiones con Conventions

| # | Hecho | Convention | Dónde |
|---|---|---|---|
| T1 | El criterio de hecho pide "6 meses de histórico" y "archivos en `landing/`". El lifecycle cuenta desde la fecha de creación (H4); un backfill hecho hoy expira 30 días después de hoy, con independencia de `ingest_date` en la clave. Un histórico de 6 meses solo existe en `landing/` mientras no hayan pasado 30 días desde su escritura. | Medallion layers (`landing/`: lifecycle de 30 días) | H4, O5 |
| T2 | Una regla de lifecycle de 30 días en un bucket con versioning no libera almacenamiento sin una acción de noncurrent (H5); el patrón del repo tiene 90 días de noncurrent. Los "30 días" de la Convention no dicen si cubren las versiones noncurrent. | Medallion layers | H5 |
| T3 | Idempotency exige relanzar un día con el mismo resultado; en un bucket versionado cada reintento deja versiones noncurrent y en uno no versionado reinicia la edad del objeto (H5). Bronze es append-only por diseño y no reescribe landing, así que el relanzamiento afecta a landing, no a Bronze. | Idempotency | H5, O2 |
| T4 | CKV_AWS_18 (access logging) y CKV_AWS_144 se resolvieron con skip en state por coste y por Region. Un bucket de logs separado es un recurso adicional; la doc recomienda uno por región. | Region, No hourly-billed resources (no aplica: S3 no cobra por hora) | H3, H7 |
| T5 | El criterio de "mismo cifrado que el state" no está escrito como Convention: SSE-S3 en state es "decisión del owner" para ese bucket; no hay decisión para el bucket de datos. | Ninguna aplicable: laguna de decisión | H6, O3 |
| T6 | El Apply gate impide que un agente compruebe el comportamiento del lifecycle en AWS; solo CI aplica y el owner puede ejecutar `plan`. Las afirmaciones de la sección H4/H5 salen de la documentación, no de una prueba en la cuenta. | Apply gate, Verification ownership | H4, H5 |

## Preguntas para el owner

1. **Histórico y lifecycle (T1).** ¿El histórico de 6 meses debe poder consultarse desde `landing/` más de 30 días después de escribirse? Si sí, ¿qué cambia: la Convention, la ubicación del histórico, o su regeneración bajo demanda (O5)?
2. **Bucket de `landing/`.** ¿Un bucket de datos por entorno con prefijos de capa, o un bucket de `landing/` dedicado por entorno (O1)? Esto fija si el versioning, el cifrado y el lifecycle son compartidos con Bronze.
3. **Versioning de `landing/`.** ¿Se activa el versioning en `landing/` (y con qué plazo de noncurrent) o no (O4)? Afecta a si "30 días" significa borrado físico.
4. **Cifrado del bucket de datos.** ¿SSE-S3 (como el state) o SSE-KMS (O3)? Se necesita una decisión del owner para el skip de CKV_AWS_145.
5. **Access logging.** ¿Se acepta de nuevo el skip de CKV_AWS_18 o se activa el logging con un bucket de logs (H7)?
6. **Clave determinista.** ¿Se confirma que el nombre de archivo es función de `(source, run_date, slot)` y que relanzar sobrescribe (O2)? Qué formato (JSON, JSON.gz, CSV) y si la clave lleva `key=value`.
7. **Eventos tardíos.** ¿`ingest_date` en la clave es la fecha de llegada del archivo (lógica del run) o la fecha de evento? (O2).
8. **Reservas.** ¿La extracción incremental de Postgres aterriza como archivo en `landing/` (supuesto de H9) o entra por otro camino?

## No verificado

1. Que cualquier objeto subido con `PutObject` no puede llevar una fecha de creación pasada: no se encontró mecanismo en la doc consultada, pero no se buscó de forma exhaustiva (H4).
2. Facturación del almacenamiento noncurrent: no hay cita literal en las páginas leídas; se infiere (H5).
3. Lista de checks de checkov que dispara un bucket de datos (CKV_AWS_21 versioning, CKV2_AWS_6 PAB, CKV2_AWS_61 lifecycle, CKV_AWS_300 multipart, CKV_AWS_19 cifrado, CKV_AWS_53-56): no se consultó la doc de checkov; en el repo solo constan los 4 skips de `state_bucket.tf` (H3).
4. Que los motivos de skip de state valgan para un bucket de datos (H3): decisión del owner.
5. Precio de la clave `aws/s3`, de `PutObjectTagging`, de peticiones de lifecycle y de transferencia entre Lambda/Glue/Athena y S3 (H8).
6. Reglas de naming de buckets (DNS, 3-63 caracteres, globales) y su unicidad: no se consultó.
7. El comportamiento real del lifecycle en la cuenta (retrasos de días o semanas, H4) no se ha probado: el Apply gate prohíbe a un agente ejecutarlo.
8. Volumen por fuente y tamaño de archivos de gasto, CRM, FX y reservas: no medidos, solo supuestos (H9); depende de `generator-data.md`, cuyas cifras son estimaciones.
9. Que Spark/Glue y Athena lean mejor el estilo `key=value` que `YYYY/MM/DD` (O2).
10. La página `https://aws.amazon.com/s3/pricing/` no mostró las tablas de Paris; los precios vienen del archivo de oferta con fecha de publicación 2026-11-09, no de la web comercial.
11. El precio de KMS ($1,00/clave/mes, $0,03/10.000, 20.000 gratis) viene de la página de KMS vía un modelo de resumen, no de una tabla propia; la cifra de $0,03 sale del ejemplo de S3, no de una tabla de precios.
12. La versión del provider de Terraform y los nombres exactos de los argumentos de `aws_s3_bucket_lifecycle_configuration` solo se infirieron del uso en `state_bucket.tf`.
