---
type: Research note
---

# Research note: account-cost (topic foundations)

## Header

- **Topic:** foundations (Fase 1: cuenta, presupuesto, bootstrap Terraform, OIDC, CI).
- **Área:** account-cost. Una de las cuatro notas de la etapa Research; un autor posterior las consolida.
- **Fecha:** 2026-11-12.
- **Alcance:** documentar lo que existe hoy en fuentes oficiales de AWS y HashiCorp sobre el plan de cuenta, la disponibilidad de los servicios del blueprint, AWS Budgets y los precios de eu-west-3 que tocan las Conventions. No decide ni recomienda. Decisión que informa: `docs/design/README.md` § Open decisions, fila "Plan de cuenta AWS (créditos Free Tier desde julio 2025)", estado Proposed (opciones: Plan Free; Plan Paid con presupuesto y alertas).
- **Conventions citadas (por nombre, `docs/design/CONTEXT.md` § Conventions):** IaC only, Region, No hourly-billed resources, Apply gate, Simple shell commands, Design write ownership.
- **Revisión adversarial:** no ejecutada por este autor (nota de área; la revisión corresponde a la consolidación).
- **Método:** WebFetch/WebSearch sobre docs.aws.amazon.com, aws.amazon.com, pricing.us-east-1.amazonaws.com (API pública de precios de AWS) y el código fuente del provider en GitHub. Ningún comando AWS ni Terraform (Apply gate).

## Hallazgos

Cada hallazgo cita fuente y fecha. Toda fuente: "consultado 2026-11-12".

### A. Plan Free vs plan Paid

1. **Créditos.** Cuentas nuevas reciben 100 USD al crear la cuenta, sea cual sea el plan, y hasta 100 USD más completando actividades; el plan Free y el Paid ofrecen lo mismo en créditos. Fuente: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html (consultado 2026-11-12). Fuente adicional: https://aws.amazon.com/free/free-tier-faqs/ ("up to $200 in AWS credits, $100 upon sign-up and up to $100 more", consultado 2026-11-12).
2. **Duración del plan Free.** Termina a los seis meses o al agotar los créditos, lo que ocurra antes. El FAQ añade que no se puede ampliar más allá de 6 meses. Fuentes: free-tier-plans.html y free-tier-faqs (consultado 2026-11-12).
3. **Al vencer el plan Free.** La página de docs dice que la cuenta se cierra automáticamente, se pierde acceso a recursos y datos, AWS conserva el contenido 90 días y luego borra la cuenta y todos sus recursos; para mantener el acceso se puede pasar al plan Paid dentro de esos 90 días y los créditos restantes se aplican a facturas futuras. El FAQ dice "AWS suspends your account", retiene datos 90 días y borra la cuenta si no se mejora en ese plazo. Fuentes: free-tier-plans.html y free-tier-faqs (consultado 2026-11-12). Los dos documentos usan verbos distintos (cierra / suspende) para el mismo evento.
4. **Ruta de mejora Free a Paid.** Consola: "Upgrade plan" en Billing (docs de billing); en la experiencia nueva: AWS Settings, Billing, Upgrade, método de pago. Es irreversible ("You cannot reverse the upgrade process"); el FAQ confirma que no se puede bajar de Paid a Free. Al mejorar se mantienen los créditos restantes, se accede a Always Free y a pruebas de corta duración, y se puede crear un spend limit. Fuentes: free-tier-plans.html; https://docs.aws.amazon.com/accounts/latest/reference/upgrade-account.html; free-tier-faqs (consultado 2026-11-12).
5. **Plan Paid.** Acceso a todos los servicios y funciones; pago por uso estándar por lo que supere los créditos o por servicios donde los créditos no aplican; elegible para otros créditos promocionales. Free no es elegible para otros créditos (p. ej. AWS Activate). Fuente: free-tier-plans.html (consultado 2026-11-12).
6. **Spend limit del plan Paid.** El FAQ indica que en el plan Paid se puede fijar un límite mensual "starting at $20", con avisos al 50, 75 y 90 %. Fuente: free-tier-faqs (consultado 2026-11-12). La tabla de opciones de alta lo marca como disponible solo en "Sign up for AWS (new)" y no en "advanced": https://docs.aws.amazon.com/accounts/latest/reference/sign-up-for-aws.html (consultado 2026-11-12).
7. **Mejora automática a Paid.** Una cuenta Free pasa automáticamente a Paid si se une a AWS Organizations, crea un landing zone de Control Tower, entra en APN, crea un contrato de Professional Services, firma un Enterprise Agreement, compra una suscripción Skill Builder Team o se designa HIPAA/SEC. Fuente: free-tier-plans.html (consultado 2026-11-12).
8. **Servicios restringidos en Free.** Free no incluye servicios y funciones que podrían agotar los créditos o requieren compra de hardware (ejemplos citados: Savings Plans, Reserved Instances, ciertas ofertas de Marketplace). La lista concreta de servicios por plan está en la página de servicios soportados (hallazgo 9). Fuente: free-tier-plans.html. La página https://aws.amazon.com/free/ solo marca expresamente Bedrock AgentCore como "Paid plan exclusive" y no da lista completa (consultado 2026-11-12).
9. **Dos experiencias de alta con listas de servicios.** La referencia "Supported AWS services for Sign up for AWS (new)" separa: (a) servicios del Free Tier de la experiencia nueva; (b) servicios solo del plan Paid; (c) servicios no soportados en la experiencia nueva salvo que se activen funciones avanzadas. Fuente: https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html (consultado 2026-11-12).
   - Solo plan Paid (lista (b)): ARC, CodeGuru Profiler, Data Firehose, DocumentDB, EMR, Kinesis, Kinesis Data Streams, Kinesis Video Streams, MSK, MemoryDB, Neptune, Personalize, Redshift, Textract, Transcribe, Translate, Data Exchange, End User Messaging SMS y Social, Fault Injection Service, Firewall Manager, Network Firewall, Security Agent, Storage Gateway, DevOps Agent, S3 Glacier Deep Archive.
   - No soportados en la experiencia nueva (lista (c)), entre otros: AWS Organizations, IAM Identity Center, Amazon Managed Workflows for Apache Airflow, Control Tower, Security Hub, GuardDuty, Transit Gateway, IAM Access Analyzer (excepto validación de políticas).
   - La página indica que el Free Tier de la experiencia nueva no soporta funciones multi-Region ni cross-Region.
10. **Región en la experiencia nueva.** Al crear el proyecto, AWS asigna una Region según el país de la dirección de contacto: us-east-2, eu-north-1 (Estocolmo; Francia está en esa lista) o ap-southeast-2. La Region no se puede cambiar; para elegir Region hay que usar "Sign up for AWS (advanced)" o activar funciones avanzadas. Fuentes: https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html y sign-up-for-aws.html (consultado 2026-11-12). eu-west-3 no figura entre las Regions asignables de la experiencia nueva. La Convention Region fija eu-west-3.
11. **Experiencia avanzada.** Los docs de billing "Choosing a plan" (planes Free y Paid) se enlazan desde la columna "advanced" de la tabla de gestión de cuentas (fila "Upgrade your account": "Free Tier plans"). Fuente: sign-up-for-aws.html (consultado 2026-11-12). El documento revisado no incluye una lista de servicios por plan específica para la experiencia avanzada; la lista del hallazgo 9 es la de la experiencia nueva.
12. **Incoherencia interna en el FAQ.** La misma página dice que los créditos expiran a los 6 meses (FAQ general y avanzado) y a los 12 meses (FAQ del plan Paid). Fuente: free-tier-faqs (consultado 2026-11-12). Sin resolver en este documento.

### B. AWS Budgets

13. **Coste.** Monitorizar presupuestos y recibir notificaciones es gratis. Presupuestos con acciones: los dos primeros por mes son gratis; cada adicional cuesta 0,10 USD/día. Informes de presupuesto por correo: 0,01 USD cada uno. Fuente: https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/ (consultado 2026-11-12).
14. **Tipos y notificaciones.** Tipos: coste, uso, utilización/cobertura de RI y Savings Plans. Un presupuesto de coste mensual con importe fijo puede avisar por gasto real (actual) y previsto (forecasted). Las notificaciones pueden ir a un tema SNS, a una dirección de correo o a ambos. Los datos se actualizan hasta tres veces al día, normalmente cada 8 a 12 horas, y puede haber retraso entre el cargo y el aviso. Fuente: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-managing-costs.html (consultado 2026-11-12).
15. **Servicio global, endpoint y Region.** La API de Budgets figura en "Billing and Cost Management endpoints" con endpoint `budgets.amazonaws.com` (y `budgets.us-east-1.api.aws`) listado para us-east-1, us-west-2 y ca-central-1; todas las filas apuntan al mismo endpoint. Cost Explorer solo tiene endpoint en us-east-1. Budgets no tiene endpoint propio en eu-west-3. Fuente: https://docs.aws.amazon.com/general/latest/gr/billing.html (consultado 2026-11-12). Un tema SNS usado como destino es un recurso regional de SNS (SNS está en eu-west-3, ver tabla); la página de doc que fija la política del tema es https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-sns-policy.html (no leída en esta nota).
16. **Cost Explorer.** Al crear el primer presupuesto, AWS Budgets activa Cost Explorer si no estaba activado; el gráfico puede tardar hasta 24 h. Fuente: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-create.html (consultado 2026-11-12).
17. **Disponibilidad por plan.** AWS Budgets y AWS Billing and Cost Management figuran en la lista de servicios del Free Tier de la experiencia nueva (hallazgo 9). Fuente: supported-services-sign-up-new.html (consultado 2026-11-12).
18. **Recurso Terraform `aws_budgets_budget`** (argumentos tomados del fichero de documentación del provider `hashicorp/aws` en https://github.com/hashicorp/terraform-provider-aws, `website/docs/r/budgets_budget.html.markdown`, rama main, consultado 2026-11-12; la página renderizada de registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/budgets_budget no devolvió contenido legible al recuperarla):
    - Requeridos: `budget_type` (coste o uso), `time_unit` (`MONTHLY`, `QUARTERLY`, `ANNUALLY`, `DAILY`).
    - Opcionales: `account_id`, `auto_adjust_data`, `billing_view_arn`, `cost_filter` (conflicto con `filter_expression`), `cost_types` (conflicto con `metrics`), `filter_expression`, `limit_amount`, `limit_unit` (p. ej. USD), `metrics`, `name`, `name_prefix`, `notification` (repetible), `planned_limit`, `tags`, `time_period_end`, `time_period_start` (formato `2017-01-01_12:00`).
    - Bloque `notification`: `comparison_operator` (`LESS_THAN`, `EQUAL_TO`, `GREATER_THAN`), `notification_type` (`ACTUAL` o `FORECASTED`), `threshold`, `threshold_type` (`PERCENTAGE` o `ABSOLUTE_VALUE`) son requeridos; `subscriber_email_addresses` y `subscriber_sns_topic_arns` son opcionales, pero hace falta al menos uno de los dos.
    - Un presupuesto de 10 USD mensual con avisos al 50/80/100 % se expresa con `budget_type = "COST"`, `limit_amount = "10"`, `limit_unit = "USD"`, `time_unit = "MONTHLY"` y un bloque `notification` por umbral y tipo (`ACTUAL` y/o `FORECASTED`). Esta combinación es la forma que admiten los argumentos anteriores; los valores concretos los fija la Convention IaC only.
    - La fuente incluye un ejemplo "simple dollar budget" (presupuesto de coste con límite fijo en USD); el resumen obtenido no reproduce su código completo, así que el valor literal `"COST"` de `budget_type` no se ha verificado.

### C. Precios en eu-west-3 (Paris) que tocan las Conventions

19. **Glue ETL.** 0,44 USD por DPU-hora estándar (usage type `EUW3-ETL-DPU-Hour`) y 0,29 USD por DPU-hora Flex (`EUW3-ETL-Flex-DPU-Hour`). Fuente: API de precios de AWS, https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSGlue/current/eu-west-3/index.json (consultado 2026-11-12). La página https://aws.amazon.com/glue/pricing/ confirma 0,44 y 0,29 sin dar Region y facturación por segundo; no indica mínimo de facturación para Glue 2.0+.
20. **Glue Data Catalog.** Almacenamiento: 1 USD por 100.000 objetos al mes; solicitudes: 1 USD por millón. Primer millón de objetos y primer millón de solicitudes al mes gratis (SKU globales). Fuentes: API de precios (misma URL) y aws.amazon.com/glue/pricing (consultado 2026-11-12).
21. **Athena.** 7,00 USD por TB escaneado en EU (Paris), usage type `EUW3-DataScannedInTB`. Fuente: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonAthena/current/eu-west-3/index.json (consultado 2026-11-12). La página https://aws.amazon.com/athena/pricing/ no muestra precios por Region (su ejemplo usa 5 USD/TB, de otra Region).
22. **S3.** No verificado: la página https://aws.amazon.com/s3/pricing/ no expone precios de Paris al recuperarla, y la API de precios de S3 para eu-west-3 devolvió el SKU de `EUW3-Requests-Tier1` (PUT/COPY/POST/LIST, `JSTCNSNFYXFKBECA`) sin valor de precio, y no mostró los SKUs de almacenamiento Standard ni GET. Los precios de almacenamiento y solicitudes de S3 en eu-west-3 quedan sin cifra en esta nota.

## Tabla de servicios

Servicios que el blueprint usa (`docs/design/platform-blueprint/current/project/README.md` § Infraestructura y coste, § Stack, § Fuentes simuladas, y Conventions IaC only). "Free" y "Paid": presencia en las listas de la página de servicios soportados de la experiencia nueva (https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html). "eu-west-3": fila "Europe (Paris) eu-west-3" en la página de endpoints de AWS General Reference. Todas consultadas 2026-11-12.

| Servicio | eu-west-3 | Plan Free | Plan Paid | Fuente eu-west-3 |
|----------|-----------|-----------|-----------|------------------|
| Amazon S3 (incluye state de Terraform) | Sí (`s3.eu-west-3.amazonaws.com`) | Sí (S3 Access Grants no soportado) | Sí (incluye lo del Free más Glacier Deep Archive) | https://docs.aws.amazon.com/general/latest/gr/s3.html |
| AWS Glue (Data Catalog y jobs) | Sí (`glue.eu-west-3.amazonaws.com`) | Sí | Sí | https://docs.aws.amazon.com/general/latest/gr/glue.html |
| Amazon Athena | Sí (`athena.eu-west-3.amazonaws.com`) | Sí | Sí | https://docs.aws.amazon.com/general/latest/gr/athena.html |
| AWS Lambda | Sí (`lambda.eu-west-3.amazonaws.com`) | Sí (Lambda@Edge no soportado) | Sí | https://docs.aws.amazon.com/general/latest/gr/lambda-service.html |
| Amazon EventBridge | Sí (`events.eu-west-3.amazonaws.com`) | Sí | Sí | https://docs.aws.amazon.com/general/latest/gr/ev.html |
| Amazon SNS | Sí (`sns.eu-west-3.amazonaws.com`) | Sí | Sí | https://docs.aws.amazon.com/general/latest/gr/sns.html |
| Amazon CloudWatch | Sí (`monitoring.eu-west-3.amazonaws.com`) | Sí (CloudWatch Logs también listado) | Sí | https://docs.aws.amazon.com/general/latest/gr/cw_region.html |
| AWS Lake Formation | Sí (`lakeformation.eu-west-3.amazonaws.com`) | Sí | Sí | https://docs.aws.amazon.com/general/latest/gr/lake-formation.html |
| AWS IAM (incluye proveedor OIDC de GitHub) | Servicio global; no se consultó endpoint regional | Sí | Sí | No consultada (ver Fuentes) |
| AWS STS (AssumeRoleWithWebIdentity desde CI) | Endpoint regional no consultado | Sí | Sí | No consultada (ver Fuentes) |
| AWS Budgets | No: API con endpoint `budgets.amazonaws.com` (us-east-1, us-west-2, ca-central-1 listadas), sin fila eu-west-3 | Sí | Sí | https://docs.aws.amazon.com/general/latest/gr/billing.html |
| Airflow (MWAA) | No se aprovisiona (Convention Orchestration runtime). Dato informativo: "Amazon Managed Workflows for Apache Airflow" figura como no soportado en la experiencia nueva; "Amazon MWAA Serverless" figura en el Free Tier | n/a | n/a | https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html |

Servicios del blueprint que NO están disponibles en eu-west-3 según las fuentes: ninguno de los de la tabla con endpoint regional. Budgets es global (hallazgo 15), por tanto sin fila de Paris. Servicios del blueprint que NO están en el plan Free: ninguno. Condicionante transversal: la experiencia nueva asigna Region automáticamente y eu-west-3 no está entre las Regions asignables (hallazgo 10).

## Estado del repo

Comprobado con Glob el 2026-11-12:

- `**/*.tf`: sin resultados. No existe código Terraform ni el `aws_budgets_budget` que exige la Convention IaC only.
- `docs/design/foundations/`: contiene `context.md`, `working/research/terraform-layout.md` y `working/research/cicd-oidc.md` (notas de otras áreas; no leídas por este autor).
- `docs/design/CONTEXT.md` § Conventions, IaC only: "El primer recurso es un `aws_budgets_budget` de 10 USD con alertas al 50/80/100 %" (línea 44). Region: línea 42. No hourly-billed resources: línea 43. Apply gate: línea 45.
- `docs/design/CONTEXT.md` línea 29: "No hay código, Terraform ni recursos AWS."
- Blueprint `docs/design/platform-blueprint/current/project/README.md` línea 45: el presupuesto cabe en los créditos de AWS gracias a No hourly-billed resources; AWS aloja S3, Glue Catalog, Athena (workgroup con corte por consulta), Lambda y unos pocos jobs Glue.
- No hay en el repo ninguna referencia a cuenta AWS, plan Free/Paid ni sign-up; la decisión sigue como Proposed en el README de diseño (según el brief; el README de diseño no se ha releído en esta nota).

## Fuentes

Todas consultadas 2026-11-12.

- https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html
- https://aws.amazon.com/free/free-tier-faqs/
- https://aws.amazon.com/free/
- https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html
- https://docs.aws.amazon.com/accounts/latest/reference/bcm-lite-free-tier.html
- https://docs.aws.amazon.com/accounts/latest/reference/upgrade-account.html
- https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html
- https://docs.aws.amazon.com/accounts/latest/reference/sign-up-for-aws.html
- https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/
- https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-managing-costs.html
- https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/budgets-create.html
- https://docs.aws.amazon.com/general/latest/gr/billing.html
- https://docs.aws.amazon.com/general/latest/gr/{s3,glue,athena,lambda-service,ev,sns,cw_region,lake-formation}.html (una página por servicio, listadas en la tabla)
- https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{AWSGlue,AmazonAthena,AmazonS3}/current/eu-west-3/index.json
- https://aws.amazon.com/glue/pricing/, https://aws.amazon.com/athena/pricing/, https://aws.amazon.com/s3/pricing/
- https://github.com/hashicorp/terraform-provider-aws (`website/docs/r/budgets_budget.html.markdown`, main) para los argumentos de `aws_budgets_budget`

Hechos no verificados o con limitación:

- Argumentos de `aws_budgets_budget`: tomados del fichero del provider en GitHub, no de la página renderizada de registry.terraform.io (no recuperable).
- Precio de S3 (almacenamiento Standard, PUT, GET) en eu-west-3: sin cifra (hallazgo 22).
- Endpoints regionales de IAM y STS no consultados; la fila de la tabla lo refleja.
- Si el Terraform provider enruta las llamadas de Budgets al endpoint de us-east-1 al usar `region = "eu-west-3"`: no consultado.
- `budgets-sns-policy.html` (política del tema SNS para Budgets) no leída.
- Valor exacto del límite de destinatarios por notificación: no consultado.
- La lista de servicios del plan Free/Paid es la de la experiencia nueva (hallazgo 9); para la experiencia avanzada no se localizó una lista equivalente.
- El README de diseño (`docs/design/README.md`) y los demás ficheros del topic no se leyeron; la decisión abierta se cita del brief.
