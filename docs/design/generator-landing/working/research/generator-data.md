---
type: Research
topic: generator-landing
area: generador y datos
date: 2026-11-13
---

# Nota de área: generador y datos (Fase 2, Generador y landing)

## Alcance

Nota de un solo área para consolidar después en `research.md`. Describe lo que existe y los hechos; no propone. Criterio de "hecho" de la fase, literal: "Simulador OTA coherente, Lambda + EventBridge, Postgres local, archivos en `landing/`. Hecho cuando hay 6 meses de histórico y llegan micro-lotes nuevos."

Estado del repo: `generators/` está previsto y no existe (AGENTS.md § Mapa del repo). No hay código que analizar. Las cifras de volumen son estimaciones aritméticas con supuestos declarados. Toda cifra externa vale solo para la fecha de consulta (2026-11-13). Rutas citadas leídas: `docs/design/platform-blueprint/current/project/README.md` (§ Fuentes simuladas, líneas 21-31) y `docs/design/CONTEXT.md` § Conventions (líneas 34-55).

## Hechos

### H1. Las 5 fuentes según el blueprint
Fuente: `docs/design/platform-blueprint/current/project/README.md:21-31`.

| Fuente | Formato y llegada | Dificultad |
|--------|-------------------|------------|
| Clickstream web/app | JSON, micro-lotes cada 15 min (Lambda + EventBridge) | Duplicados, tardíos (hasta 72 h), campos nuevos |
| Reservas (OLTP) | Postgres local en Docker, incremental por `updated_at` | Cambios de estado, varias divisas |
| Gasto publicitario | CSV diario por plataforma (Google Ads, Meta, Criteo) | Esquemas distintos, correcciones retroactivas |
| CRM emailing | JSON diario | Bajas de consentimiento a propagar |
| Tipos de cambio | API BCE, diario | Días sin publicación: arrastrar el último valor |

El blueprint fija: generador Python (Faker + reglas de negocio), datos coherentes entre fuentes "lo que permite calcular atribución real", 50.000-200.000 eventos/día, ~6 meses de histórico (README.md:23).

### H2. Qué necesita cada fuente para ser coherente con las demás
Derivado del blueprint (atribución real) y de la lista de fuentes; el blueprint no define esquemas ni nombres de columna, así que lo siguiente es el conjunto mínimo de claves compartidas, no un esquema existente.

| Identificador compartido | Fuentes que lo llevan | Para qué |
|---|---|---|
| `customer_id` | Clickstream (usuario identificado), Reservas, CRM | Unir comportamiento, compra y email; propagar bajas |
| `session_id` (y un id anónimo previo al login) | Clickstream; referenciado desde Reservas | Atribuir una reserva a la sesión que convirtió |
| `booking_id` | Reservas; evento de compra del clickstream | Cerrar el embudo evento-reserva |
| `campaign_id` (y `utm_*`) | Gasto publicitario (por plataforma), Clickstream (UTM de la sesión), CRM (campaña de email) | Coste vs ingresos por campaña |
| `currency` + fecha | Reservas, Gasto publicitario, Tipos de cambio | Convertir importes a una divisa común |
| `consent` / baja con marca de tiempo | CRM; efecto sobre Clickstream y Reservas | Propagar la baja |

Hecho de diseño relevante: para que la atribución sea comprobable, el generador debe poder emitir la verdad de base (qué campaña originó cada reserva) aparte de los datos observables. El blueprint no dice dónde viviría esa verdad de base; queda como pregunta (P4).

### H3. Determinismo por fecha lógica
Convention **Idempotency**: "cada tarea y job depende solo de la fecha lógica (`{{ ds }}` / `--run-date` / `var("run_date")`), nunca de `now()`... relanzar un día da el mismo resultado".

Hechos técnicos verificables sobre las herramientas (no consultados en fuente externa hoy; ver No verificado):
- Faker expone `Faker.seed()` (global) y `seed_instance()` por instancia; NumPy ofrece `numpy.random.default_rng(seed)` aceptando enteros o secuencias de enteros.
- Un entero derivado de `run_date` (p. ej. una secuencia `[semilla_global, año, mes, día, slot]`) sirve de entrada a ambas.

Puntos del diseño del dato que condicionan el determinismo, como hechos de la restricción:
- Micro-lote cada 15 min = 96 lotes/día. Un lote identificado por `(run_date, slot)` necesita su propia semilla para ser reproducible.
- Eventos tardíos hasta 72 h: un lote de la fecha lógica D contiene eventos con `event_time` en D, D-1, D-2 y D-3. Para que relanzar D dé el mismo resultado, el retraso de cada evento tiene que ser función determinista de su propia semilla, no de la hora de ejecución.
- Duplicados: la repetición debe ser determinista (mismo `event_id` reenviado en un lote posterior elegido por semilla).
- Las entidades de larga vida (clientes, campañas, catálogo) necesitan semilla independiente de la fecha para ser estables entre días.
- Reservas con cambios de estado: la historia de cada reserva (creada, pagada, cancelada...) con sus `updated_at` es función de `booking_id` y semilla; el estado visible en el Postgres depende de la fecha lógica hasta la que se haya cargado.

### H4. Dificultades inyectadas y su regla de generación
Fuente: README.md:27-31. Las columnas "Observable" son hechos sobre lo que cada dificultad implica en los datos.

| Dificultad | Fuente | Qué debe verse en los datos |
|---|---|---|
| Duplicados | Clickstream | Mismo `event_id` en dos o más archivos/lotes |
| Tardíos hasta 72 h | Clickstream | `event_time` anterior a la hora de llegada del lote hasta 72 h |
| Campos nuevos | Clickstream | Evolución de esquema a lo largo del histórico (campo presente solo desde cierta fecha) |
| Cambios de estado | Reservas | Misma fila con `status` y `updated_at` cambiantes |
| Varias divisas | Reservas | Importe + `currency` distintos de la divisa de reporte |
| Esquemas distintos | Gasto publicitario | Un CSV con columnas/nombres/formatos diferentes por plataforma (Google Ads, Meta, Criteo) |
| Correcciones retroactivas | Gasto publicitario | Archivo de un día posterior que revisa cifras de días anteriores |
| Bajas de consentimiento | CRM | Registros que revocan consentimiento de clientes ya presentes en otras fuentes |
| Días sin publicación | Tipos de cambio | Fechas sin tipo; ver H8 |

### H5. Volumen y tamaño de 6 meses de histórico (aritmética)
Supuestos declarados (no medidos): 6 meses = 182 días (26 semanas × 7); un evento de clickstream en JSON, una línea, ~500-800 B con ids, UTM, user agent, página, timestamps (rango supuesto, sin fuente); compresión gzip de JSON repetitivo ~8-10:1 (supuesto).

- Eventos: 50.000 × 182 = 9,1 M; 200.000 × 182 = 36,4 M; punto medio 125.000 × 182 = 22,75 M.
- Tamaño sin comprimir: 9,1 M × 500 B = 4,55 GB (mínimo); 36,4 M × 800 B = 29,1 GB (máximo); punto medio 22,75 M × 650 B ≈ 14,8 GB.
- Comprimido a 8:1-10:1: ≈ 0,45 GB a 3,6 GB (mínimo-máximo); punto medio ≈ 1,5-1,8 GB.
- Archivos de clickstream por micro-lote: 96/día × 182 = 17.472 archivos en el histórico. Eventos por lote: 125.000 / 96 ≈ 1.302 (rango 521-2.083). Tamaño por lote ≈ 0,34 MB-1,7 MB sin comprimir (rango 521 × 500 B ≈ 0,26 MB a 2.083 × 800 B ≈ 1,67 MB). Son archivos pequeños.
- El resto de fuentes es de un orden menor: el blueprint no da volúmenes de reservas, gasto ni CRM. Gasto: 3 plataformas × 182 días = 546 CSV diarios. CRM: 182 JSON diarios. FX: 1 valor por día de publicación.
- Los "50.000-200.000 eventos/día" del blueprint es el rango de eventos; no dice si incluye solo clickstream. Pregunta P2.

### H6. Convention de landing
**Medallion layers**: `landing/` guarda "archivos crudos tal cual, lifecycle de 30 días". Con 6 meses de histórico, el contenido de `landing/` de más de 30 días expira por regla; Bronze conserva el payload completo y es append-only. Consecuencia factual: el histórico solo persiste más de 30 días en Bronze, no en `landing/`. Ver T1.

### H7. Librerías Python (consultado 2026-11-13, PyPI JSON API)
Fuente de cada fila: `https://pypi.org/pypi/<paquete>/json`, consultada el 2026-11-13. La fecha de publicación de cada versión no se pudo leer (la respuesta se truncó antes de esa entrada).

| Paquete | Versión más reciente | Licencia | Python requerido |
|---|---|---|---|
| Faker | 40.54.0 | MIT | >=3.10 |
| NumPy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (campo `license_expression`) | >=3.12 |
| psycopg (3) | 3.3.9 | LGPL-3.0-only (`license_expression`) | >=3.10 |
| boto3 | 1.44.2 | Apache-2.0 | >=3.10 |
| PyArrow | 26.0.1 | Apache-2.0 (`license_expression`) | >=3.11 |

Notas: NumPy 2.5.4 exige Python >=3.12, por encima de >=3.10 de Faker/boto3/psycopg. La versión de Python de runtime de Lambda no se consultó (ver No verificado). psycopg es LGPL: el proyecto es de portfolio; no se ha evaluado su implicación y no se saca conclusión.

### H8. Tipos de cambio del BCE: hechos
Fuente: `https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html`, consultada el 2026-11-13.
- Las tasas "are usually updated at around 16:00 CET every working day, except on TARGET closing days"; proceden de una concertación diaria entre bancos centrales que normalmente ocurre sobre las 14:10 CET.
- Se publican "for information purposes only"; el BCE desaconseja usarlas para transacciones. La página enlazada no se leyó para los términos de reutilización (ver No verificado).
- Ficheros: último día `eurofxref-daily.xml` (también CSV zip, PDF, RSS); serie histórica completa `eurofxref-hist.xml` (y CSV zip); últimos 90 días `eurofxref-hist-90d.xml`; formato SDMX-ML `eurofxref-sdmx.xml`.
- Cobertura según el resultado de búsqueda (fuente secundaria, página de Latvijas Banka y la propia del BCE): histórico desde el 4 de enero de 1999; EUR/RUB dejó de publicarse tras el 1 de marzo de 2022.
- Base EUR: las tasas son unidades de divisa por 1 EUR. (Hecho conocido del formato; no verificado hoy en el XML.)
- El Data Portal del BCE (`data.ecb.europa.eu`) devolvió HTTP 503 al intentar leer su documentación de API el 2026-11-13; no hay hechos verificados sobre su URL base, claves o límites.

Real vs simulado, solo hechos: el blueprint llama a la fuente "API BCE, diario" (README.md:31). Una fuente real requiere acceso a Internet desde donde corra la ingesta y devuelve las tasas reales con sus días sin publicación reales (fines de semana y cierres TARGET). Una fuente simulada no depende de red y puede forzar los días sin publicación en fechas elegidas, pero entonces los días sin publicación y el valor de las tasas son los del generador, no los del BCE. No hay en el repo un cliente ni una fixture del BCE.

## Opciones observadas

Sin recomendación; cada opción con sus hechos y costes.

### O1. Dónde se genera el histórico de 6 meses

| Opción | Hechos a favor | Hechos en contra / costes |
|---|---|---|
| A. Backfill local (script con `--run-date` en bucle, sube a S3 o escribe a disco) | Sin tiempo máximo de ejecución; sin coste de Lambda; reproducible con el mismo `run_date`; encaja con "Postgres local en Docker" | Hay que subir ~0,45-3,6 GB comprimidos (H5) a S3 desde la máquina del owner; subir exige credenciales AWS en local, y el Apply gate impide a los agentes ejecutar comandos AWS (el owner ejecuta) |
| B. Backfill invocando la Lambda por fecha/slot | Un único camino de código para histórico y micro-lotes; ejercita la misma Lambda que el flujo vivo | 17.472 invocaciones solo de clickstream (H5); Lambda tiene tiempo máximo y límites de memoria que no se han verificado hoy; el Postgres local no es alcanzable desde Lambda (sin VPC privada, Convention No hourly-billed resources) |
| C. Mixta: histórico local, micro-lotes por Lambda | Cada herramienta donde mejor encaja | Dos caminos de código a mantener idénticos para que Idempotency se cumpla; riesgo de divergencia entre histórico y flujo vivo |

### O2. Dónde aterriza cada fuente

| Fuente | S3 `landing/` | Postgres local |
|---|---|---|
| Clickstream | Natural: micro-lotes JSON desde Lambda (README.md:27) | Fuera del blueprint |
| Reservas | Exigiría extraer del Postgres a archivos (el blueprint dice incremental por `updated_at` desde el Postgres) | Es la definición del blueprint (README.md:28); el Postgres es local y Lambda no lo alcanza (sin VPC) |
| Gasto publicitario | CSV diarios por plataforma | No indicado |
| CRM | JSON diario | No indicado |
| FX | Archivo diario descargado del BCE o generado | No indicado |

Hecho que enlaza ambas columnas: el Postgres local debe llegar a Bronze/`landing/` por algún mecanismo; el blueprint no dice si Spark lo lee por JDBC directamente (sin pasar por `landing/`) o si se extrae primero a archivos. Eso afecta a si la regla "landing: archivos crudos" aplica a Reservas (ver T2, P3).

### O3. Semilla
- (a) Una semilla por `run_date` para todo el generador; (b) semilla por `(run_date, fuente)`; (c) semilla por `(run_date, fuente, slot)` para clickstream. Costes: (a) acopla el orden de generación entre fuentes; (b)/(c) aíslan fuentes y slots pero requieren una función de derivación documentada.

### O4. Tipos de cambio
- Real: descarga de `eurofxref-hist.xml`/`-90d.xml`/`daily.xml` (H8). Simulado: serie sintética con huecos forzados. Mixta: tasas reales históricas congeladas en fixture. Coste de la real: dependencia de red y de la disponibilidad del BCE; de la simulada: no reproduce valores ni calendario reales.

## Tensiones con Conventions

- **T1. Medallion layers vs 6 meses de histórico.** `landing/` tiene lifecycle de 30 días; el criterio de "hecho" pide 6 meses de histórico y archivos en `landing/`. Un backfill que escriba 6 meses en `landing/` verá expirar lo anterior a 30 días; la Convention no dice qué hacer. No resuelto aquí.
- **T2. Medallion layers vs Reservas en Postgres.** `landing/` son "archivos crudos tal cual" y la fuente de Reservas es una base de datos con carga incremental por `updated_at`; no hay archivo a menos que se extraiga. Si la lectura es directa, Reservas no pasa por `landing/`; el criterio de "hecho" habla de "archivos en `landing/`" en general.
- **T3. No hourly-billed resources / sin VPC privada vs Lambda + Postgres local.** Lambda sin VPC no alcanza un Postgres en Docker local. Cualquier opción en que Lambda toque Reservas contradice el diseño o requiere un mecanismo no descrito.
- **T4. Idempotency vs micro-lotes y tardíos.** La Convention exige depender solo de la fecha lógica, pero un lote de 15 min tiene "hora" y el EventBridge dispara por reloj. Si el handler deriva el slot de la hora de invocación, usa `now()`. El evento EventBridge puede llevar su hora programada como entrada; no verificado.
- **T5. Apply gate vs desplegar Lambda/EventBridge.** Los agentes no pueden ejecutar comandos AWS ni `terraform apply`; la verificación de que llegan micro-lotes nuevos (criterio de "hecho") depende de la salida que aporte el owner (Verification ownership).
- **T6. Idempotency vs Bronze append-only.** Reenviar un lote (duplicados deliberados) es legítimo en Bronze, pero relanzar un día desde el generador no debe añadir duplicados nuevos: los duplicados deben ser los mismos. No es contradicción, pero exige que la inyección sea determinista (H3).
- **T7. Region.** Lambda, EventBridge y el bucket irían en `eu-west-3`. El bucket manual de state en `eu-north-1` está fuera de Region por excepción documentada; no afecta al generador.

## Preguntas para el owner

- **P1.** ¿Cuál es el destino del histórico de 6 meses frente al lifecycle de 30 días de `landing/` (T1)? Hecho: el criterio de "hecho" y la Convention coinciden en nada.
- **P2.** ¿Los 50.000-200.000 eventos/día son solo clickstream o suman todas las fuentes? Cambia H5 en un orden de magnitud para Reservas/CRM.
- **P3.** ¿Reservas pasa por `landing/` como archivos extraídos o Spark lee el Postgres directamente? (T2)
- **P4.** ¿Dónde se publica la verdad de base de atribución (qué campaña originó cada reserva) para validar los marts? El blueprint dice "atribución real" sin ubicación.
- **P5.** ¿FX real, simulado o fixture congelada? Y, si es real, ¿se acepta la dependencia de red en el generador?
- **P6.** ¿Cuántos "campos nuevos" y en qué fechas del histórico? El blueprint no fija el calendario de evolución de esquema.
- **P7.** ¿Qué divisas y qué divisa de reporte? El blueprint dice "varias divisas" sin lista.

## No verificado

1. Fechas de publicación de las versiones de Faker, NumPy, psycopg, boto3 y PyArrow (la respuesta de PyPI se truncó).
2. Versión de Python y límites (timeout, memoria, tamaño de paquete) de Lambda en `eu-west-3` hoy.
3. Si EventBridge puede pasar la hora programada al handler como entrada (T4).
4. Bytes por evento (500-800 B) y ratio de compresión (8-10:1): supuestos, no medidos; no hay generador que los mida.
5. Términos de reutilización de los datos del BCE (página "Disclaimer & Copyright" no leída).
6. Documentación de la API del Data Portal del BCE (HTTP 503 el 2026-11-13).
7. El formato exacto actual de `eurofxref-daily.xml` y que las tasas son por 1 EUR (no se descargó el archivo).
8. Comportamiento de `Faker.seed_instance` y `numpy.random.default_rng` con semillas derivadas (no consultado en documentación hoy).
9. Datos secundarios del BCE (inicio en 1999, fin de EUR/RUB) provienen de un resultado de búsqueda y no se contrastaron en la fuente primaria.
10. Volúmenes de Reservas, gasto y CRM: el blueprint no los fija.
