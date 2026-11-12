# Skyroute Marketing Lakehouse — Descripción de producto

> Fuente: `../../evidence/skyroute-blueprint.html`. Las reglas de arquitectura se citan por nombre; su veredicto vive solo en `docs/design/CONTEXT.md` § Conventions.

## Qué es

Una plataforma de datos de marketing para Skyroute, una agencia de viajes online ficticia que gasta mucho en adquisición (SEA, metabuscadores, redes sociales, afiliación). Convierte las preguntas de los Product Owners de marketing en productos de datos fiables, con definición acordada, contrato y tests. Todos los datos son sintéticos.

Cubre los cuatro ejes del puesto: **Conception** (Medallion, formato de tabla, particionado, ADRs), **Industrialisation** (Terraform, CI con GitHub Actions, dev/prod), **Exploitation / RUN** (alertas, runbooks, backfills, mantenimiento Iceberg, incidentes simulados con RCA) y **Transverse** (contratos, lineage, catálogo, glosario de KPIs).

## Productos de datos (Gold)

| Pregunta del PO | Producto | Definición a acordar |
|-----------------|----------|----------------------|
| ¿Qué canal y campaña es rentable? | `mart_roas_daily` | ROAS = ingresos atribuidos / gasto; netos de cancelación, en EUR, modelo y ventana de atribución |
| ¿Cuánto cuesta un cliente nuevo? | `mart_cac_monthly` | CAC = gasto / clientes con primera reserva confirmada en el mes |
| ¿Dónde perdemos usuarios? | `mart_funnel` | Búsqueda → ficha → checkout → reserva por sesión; look-to-book |
| ¿A quién enviamos la campaña de verano? | `mart_customer_rfm` + export de audiencia | RFM, booking window, destino preferido, consentimiento RGPD |
| ¿Qué aporta cada touchpoint? | `mart_attribution` | Last-click, linear y position-based (40/20/40) sobre el mismo recorrido |

## Fuentes simuladas

Un generador Python (Faker + reglas de negocio) produce datos coherentes entre fuentes, lo que permite calcular atribución real. Volumen objetivo: 50.000–200.000 eventos/día y ~6 meses de histórico.

| Fuente | Formato y llegada | Dificultad introducida |
|--------|-------------------|------------------------|
| Clickstream web/app | JSON, micro-lotes cada 15 min (Lambda + EventBridge) | Duplicados, eventos tardíos (hasta 72 h), campos nuevos |
| Reservas (OLTP) | Postgres local en Docker, incremental por `updated_at` | Cambios de estado, varias divisas |
| Gasto publicitario | CSV diario por plataforma (Google Ads, Meta, Criteo) | Esquemas distintos, correcciones retroactivas |
| CRM emailing | JSON diario | Bajas de consentimiento a propagar |
| Tipos de cambio | API BCE, diario | Días sin publicación: arrastrar el último valor |

## Cómo fluye el dato

Las capas y su garantía siguen **Medallion layers**, sobre **Table format**. Quién transforma cada capa lo fija **Compute split**: Spark para la ingesta, deduplicación, sesionización, MERGE y SCD2; dbt para el modelo dimensional y los marts con `contract: enforced` y `exposures`. Un DAG diario `marketing_daily` (04:00) lo encadena todo bajo **Orchestration runtime** e **Idempotency**, con un patrón write-audit-publish sobre ramas Iceberg para que un dato malo nunca llegue a `main`.

## Gobierno y operación

- Calidad en cada frontera (contrato, rama WAP, freshness, dbt tests, reconciliación, Elementary) con acción definida: bloquear, cuarentena o avisar.
- Data contracts YAML (ODCS) validados en CI, lineage OpenLineage → Marquez, catálogo OpenMetadata, Lake Formation ocultando PII al rol analista.
- RUN: seis game days provocados con `make chaos-…`, post-mortems sin culpables, backfill de 90 días con rollback por snapshot.

## Infraestructura y coste

Despliegue según **IaC only**, **Region** y **Apply gate**. El presupuesto cabe en los créditos de AWS gracias a **No hourly-billed resources**: desarrollo y orquestación en local con Docker; AWS aloja S3, Glue Catalog, Athena (workgroup con corte por consulta), Lambda y unos pocos jobs Glue.

## Stack

AWS S3 · Glue Data Catalog · Apache Iceberg · Spark/PySpark · dbt Core + Athena · Airflow 3 (Astro CLI, Cosmos) · Terraform · GitHub Actions (OIDC) · OpenLineage/Marquez · OpenMetadata · Elementary · ODCS.

## Plan

Ocho fases de ~1 semana a 10 h/semana; estado y criterio de "hecho" en `docs/design/README.md` § Fases.
