---
type: Research
topic: generator-landing
area: lambda-eventbridge
---

# Área: Lambda + EventBridge (clickstream cada 15 min)

Nota de área para consolidar en `research.md`. Fecha de obtención de todas las fuentes: 2026-11-13. Toda cifra vale solo para esa fecha.

## Alcance

Qué cubre: cómo se dispara y ejecuta, en AWS, el micro-lote de clickstream cada 15 min (README de platform-blueprint § Fuentes simuladas: "JSON, micro-lotes cada 15 min (Lambda + EventBridge)"). Hoy no existe nada en AWS para esto; no hay código del handler ni Terraform.

Temas: EventBridge Scheduler frente a reglas de EventBridge; runtime de Lambda y empaquetado con Faker; datos del evento que sirven para la idempotencia por ventana; retención de CloudWatch Logs; disponibilidad en eu-west-3; coste de 96 invocaciones/día × 2 entornos; hechos del plan Free de la cuenta; opciones para pausar un schedule.

Fuera de alcance: el diseño del simulador, el esquema del evento y el contenido del lote (otras áreas del topic); cualquier propuesta. Esta nota describe, no recomienda.

Conventions que tocan el área (se citan por nombre, sin copiar su veredicto): Region, No hourly-billed resources, IaC only, Apply gate, Idempotency, Simple shell commands. El criterio de hecho de la Fase 2 es "6 meses de histórico y llegan micro-lotes nuevos".

Método: lectura de documentación oficial de AWS con WebFetch/WebSearch. No se ejecutó ningún comando AWS ni Terraform (Apply gate).

## Hechos

Cada hecho lleva su fuente y la fecha de obtención (2026-11-13). Una marca [parcial] indica que la herramienta de lectura no devolvió el texto exacto y el hecho se apoya en un resumen de búsqueda.

### H1. EventBridge Scheduler frente a reglas programadas

- H1.1. La documentación de EventBridge llama a las reglas programadas "legacy" y recomienda Scheduler para invocar destinos por calendario. Fuente: https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html (2026-11-13).
- H1.2. Reglas programadas: expresiones `cron(...)` de 6 campos y `rate(value unit)`; los ejemplos de la doc se expresan en UTC+0; `cron` más rápido que 1 minuto no está soportado; `cron(0/15 * * * ? *)` figura como "Run every 15 minutes". Misma fuente.
- H1.3. Scheduler soporta `rate`, `cron` y `at` (una vez). Para los recurrentes se indica la zona horaria en que se evalúa la expresión; por defecto UTC. Fuente: https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html (2026-11-13).
- H1.4. Scheduler usa la base IANA de zonas horarias y ajusta el horario de verano: al adelantar el reloj, una invocación cron que cae en una hora inexistente se omite; al atrasarlo, corre una sola vez. En UTC no hay ajuste. Misma fuente.
- H1.5. Precisión: "60 second precision"; una programación a las 1:00 invoca entre 1:00:00 y 1:00:59 si no hay ventana flexible. Misma fuente.
- H1.6. Un `rate` empieza tras `StartDate`; si no se da `StartDate`, el schedule empieza a invocar de inmediato al crearse. `rate(15 minutes)` es el ejemplo de la doc. Misma fuente. La cadencia siguiente respecto a la hora de creación no está descrita en esa página (ver No verificado).
- H1.7. Ventana flexible: `FlexibleTimeWindow` con `Mode` `OFF` o `FLEXIBLE` (+ `MaximumWindowInMinutes`); en modo flexible, Scheduler invoca dentro de la ventana "after the scheduled time". `Mode` es obligatorio en `CreateSchedule`. Fuentes: https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-flexible-time-windows.html y https://docs.aws.amazon.com/scheduler/latest/APIReference/API_CreateSchedule.html (2026-11-13).
- H1.8. Entrega: "at-least-once event delivery to targets". Fuente: https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html (2026-11-13).
- H1.9. Reintentos: `RetryPolicy` con `MaximumEventAgeInSeconds` (60 a 86400) y `MaximumRetryAttempts` (0 a 185), con backoff exponencial hasta agotar el número de intentos o la edad máxima. Fuente: https://docs.aws.amazon.com/scheduler/latest/APIReference/API_RetryPolicy.html (2026-11-13). Los valores por defecto no aparecen en esa página (ver No verificado).
- H1.10. DLQ: cola SQS estándar (FIFO no soportada); se entrega un "dead-letter event" con detalles de la invocación; el rol de ejecución necesita `sqs:SendMessage`; los atributos incluyen `SCHEDULED_TIME`, `EXECUTION_ID`, `RETRY_ATTEMPTS` y `EXHAUSTED_RETRY_CONDITION` (solo si el error es reintentable). Fuente: https://docs.aws.amazon.com/scheduler/latest/UserGuide/configuring-schedule-dlq.html (2026-11-13).
- H1.11. Rol de ejecución (IAM) del schedule: confianza con principal de servicio `scheduler.amazonaws.com` y `sts:AssumeRole`; la doc recomienda salvaguardas contra confused deputy (claves de condición); para destino Lambda, permiso `lambda:InvokeFunction`. Fuente: https://docs.aws.amazon.com/scheduler/latest/UserGuide/setting-up.html (2026-11-13). Scheduler no usa roles vinculados a servicio ni políticas basadas en recurso: https://docs.aws.amazon.com/scheduler/latest/UserGuide/security_iam_service-with-iam.html (2026-11-13).
- H1.12. Lambda es destino plantillado (`Invoke`). El payload admite atributos de contexto que Scheduler sustituye al invocar: `<aws.scheduler.scheduled-time>` ("The time you specified for the schedule to invoke its target", p. ej. `2022-03-22T18:59:43Z`), `<aws.scheduler.schedule-arn>`, `<aws.scheduler.execution-id>` (id único "for each attempted invocation") y `<aws.scheduler.attempt-number>`. Fuentes: https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-templated.html y https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-context-attributes.html (2026-11-13).
- H1.13. `CreateSchedule` acepta `ClientToken` (idempotencia de la petición de creación), `State` (`ENABLED | DISABLED`), `StartDate`, `EndDate`, `ScheduleExpressionTimezone`. Fuente: API_CreateSchedule (URL en H1.7).

### H2. Runtime, arquitectura y empaquetado de Lambda

- H2.1. Runtimes de Python en la tabla "Supported runtimes": `python3.15` (public preview, sin SLA, "Not scheduled"), `python3.14` y `python3.13` (deprecación 2029-06-30), `python3.12` (2028-10-31), `python3.11` (AL2, 2027-06-30). `python3.10` figura ya como deprecado (2026-10-31). La doc indica que Lambda publica runtimes gestionados al llegar a LTS y que Python 3.15 se espera en noviembre de 2026. Fuente: https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html (2026-11-13).
- H2.2. "All supported Lambda runtimes support both x86_64 and arm64". arm64 está en "most AWS Regions"; la doc remite a la página de precios para la lista por región. Fuentes: lambda-runtimes (H2.1) y https://docs.aws.amazon.com/lambda/latest/dg/foundation-arch.html (2026-11-13).
- H2.3. Migrar a arm64 exige que cada dependencia y capa tenga versión arm64; el código subido debe ser compatible con la arquitectura elegida. Fuente: foundation-arch (H2.2).
- H2.4. Empaquetado zip: las dependencias van en la raíz del zip o en una capa; la doc recomienda empaquetar todas las dependencias del código, incluido boto3. Para paquetes con binarios, se usan wheels con `pip install --platform manylinux_2_28_x86_64` o `manylinux_2_28_aarch64` (Python 3.12 y posteriores) y `--only-binary=:all:`. Fuente: https://docs.aws.amazon.com/lambda/latest/dg/python-package.html (2026-11-13).
- H2.5. Límites de tamaño: zip 50 MB (subida directa por API/SDK), 250 MB descomprimido incluyendo capas; hasta 5 capas por función; imagen de contenedor hasta 10 GB sin comprimir; `/tmp` 512 a 10.240 MB; memoria 128 a 10.240 MB; timeout 900 s; payload asíncrono 1 MB. Fuente: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html (2026-11-13). Un zip mayor de 50 MB se sube vía S3 (python-package, H2.4).
- H2.6. Imagen de contenedor: requiere un repositorio Amazon ECR en la misma región que la función; hay imágenes base de AWS para Python 3.11 a 3.15; el tipo de paquete (zip o imagen) no se puede cambiar en una función existente. Fuente: https://docs.aws.amazon.com/lambda/latest/dg/python-image.html y python-package (2026-11-13).
- H2.7. Las funciones recién creadas en cuentas nuevas tienen cuotas de concurrencia y memoria reducidas (se suben automáticamente según el uso). Fuente: gettingstarted-limits (H2.5).
- H2.8. El tamaño de Faker y de sus datos de localización dentro de un zip no se midió (ver No verificado).

### H3. Datos del evento para idempotencia por ventana (hechos, sin diseño)

- H3.1. El instante lógico de la ventana está disponible en el evento como `<aws.scheduler.scheduled-time>` si se incluye en el `Input` del target (H1.12). El `execution-id` y el `attempt-number` cambian en cada intento; el `scheduled-time` es el momento programado, no el de entrega (H1.12, H1.10 `SCHEDULED_TIME`).
- H3.2. La entrega es at-least-once (H1.8), así que una misma ventana puede llegar más de una vez al handler.
- H3.3. La Convention Idempotency exige depender solo de la fecha lógica y no de `now()`. La Convention Medallion layers fija `landing/` como "archivos crudos tal cual" y Bronze con `_batch_id` y `_source_file`.
- H3.4. El comportamiento de reintentos de Lambda ante una invocación asíncrona no se obtuvo en esta pasada (ver No verificado).

### H4. CloudWatch Logs

- H4.1. Lambda envía logs por defecto al grupo `/aws/lambda/<function-name>`; el rol de ejecución necesita `logs:CreateLogGroup`, `logs:CreateLogStream` y `logs:PutLogEvents` (la política gestionada `AWSLambdaBasicExecutionRole` los incluye). Lambda no cobra por logs; se aplica la tarifa de CloudWatch Logs. Fuente: https://docs.aws.amazon.com/lambda/latest/dg/monitoring-cloudwatchlogs.html (2026-11-13).
- H4.2. "By default, log data is stored in CloudWatch Logs indefinitely"; la retención se configura por grupo. Fuente: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html (2026-11-13).
- H4.3. Valores de retención válidos en la política de cuenta: 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288 y 3653 días, o `NEVER_EXPIRE`; la política de cuenta exige mínimo 30 días y sustituye la retención del grupo. Misma fuente. La retención por grupo admite valores menores (la lista completa de valores por grupo no se obtuvo; ver No verificado).
- H4.4. Los eventos vencidos no se borran al instante: normalmente hasta 72 h después. Misma fuente.
- H4.5. Nivel gratuito de CloudWatch Logs: 5 GB al mes (ingesta, almacenamiento y consultas). La página de precios no mostró tarifa de París; el ejemplo en US East usa 0,50 USD/GB de ingesta estándar. Fuente: https://aws.amazon.com/cloudwatch/pricing/ (2026-11-13) [parcial: se leyeron los primeros 100.000 de 154.064 caracteres].

### H5. Disponibilidad en eu-west-3

- H5.1. EventBridge Scheduler tiene endpoint en Europe (Paris) `eu-west-3`: `scheduler.eu-west-3.amazonaws.com` y `scheduler.eu-west-3.api.aws`. Fuente: https://docs.aws.amazon.com/general/latest/gr/eventbridgescheduler.html (2026-11-13).
- H5.2. Cuotas de Scheduler en eu-west-3: cae en "Each of the other supported Regions": 500 TPS de invocaciones (las excedentes se retrasan, no se pierden), 250 req/s en Create/Delete/Get/UpdateSchedule, 10.000.000 schedules y 500 grupos de schedules. Misma fuente. Estas cifras son muy superiores al uso previsto (2 schedules).
- H5.3. Lambda en eu-west-3: existe la línea de facturación `EUW3-Lambda-GB-Second-ARM` (Vantage), lo que sugiere arm64 en París; la doc oficial de arquitectura remite a la página de precios para confirmarlo. Fuentes: https://cur.vantage.sh/aws/awslambda/euw3-lambda-provisioned-concurrency (resultado de búsqueda, indirecto) y foundation-arch (H2.2). No se confirmó en la página oficial (ver No verificado).

### H6. Coste de 96 invocaciones/día × 2 entornos

Aritmética (invocaciones, no depende de precios):

- 96 invocaciones/día = 24 h × 4 por hora.
- Por entorno: 96 × 30 = 2.880 al mes (96 × 31 = 2.976).
- Dos entornos (dev y prod): 192/día; 192 × 30 = 5.760 al mes; 192 × 31 = 5.952 al mes.
- Seis meses (180 días): 192 × 180 = 34.560 invocaciones; un año: 192 × 365 = 70.080.

Precios y nivel gratuito (US East como referencia; la tarifa de París no se obtuvo):

- Scheduler: 1,00 USD por millón de invocaciones; nivel gratuito de 14.000.000 de invocaciones al mes, calculado entre todas las regiones salvo GovCloud, sin acumulación. Fuente: https://aws.amazon.com/eventbridge/pricing/ (2026-11-13). Cálculo: 5.760 de 14.000.000 es el 0,04 % del nivel gratuito; sin él, 5.760 × 1,00 USD / 1.000.000 = 0,00576 USD al mes.
- Lambda: nivel gratuito de 1.000.000 de peticiones y 400.000 GB-s al mes; 0,20 USD por millón de peticiones; 0,0000166667 USD/GB-s en x86 (US East); 512 MB de almacenamiento efímero sin coste. Fuente: https://aws.amazon.com/lambda/pricing/ (2026-11-13). La tarifa Arm de US East citada por fuentes de terceros es 0,0000133334 USD/GB-s (el valor Arm no se pudo leer en la página oficial).
- Peticiones Lambda: 5.760 de 1.000.000 gratuitas; sin nivel gratuito, 5.760 × 0,20 / 1.000.000 = 0,001152 USD al mes.
- Duración Lambda (escenario hipotético, la duración y la memoria reales no están medidas): 512 MB (0,5 GB) × 30 s = 15 GB-s por invocación; 15 × 5.760 = 86.400 GB-s al mes, frente a 400.000 GB-s gratuitos (21,6 %). Sin nivel gratuito: 86.400 × 0,0000166667 = 1,44 USD (x86) o 86.400 × 0,0000133334 = 1,15 USD (Arm), ambos con tarifa de US East.
- Logs (escenario hipotético): 20 KB por invocación × 5.760 = 115.200 KB, unos 0,11 GB al mes, frente a 5 GB gratuitos; a 0,50 USD/GB (US East), unos 0,06 USD sin nivel gratuito.
- SQS (si hubiera DLQ): no se obtuvo su tarifa (ver No verificado).

### H7. Plan Free de la cuenta

- H7.1. El plan Free dura hasta seis meses o hasta agotar los créditos, lo que ocurra primero. Créditos: 100 USD al abrir la cuenta y hasta 100 USD más por actividades. Fuente: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html y https://aws.amazon.com/free/ (2026-11-13).
- H7.2. Al terminar el plan Free, "your account closes automatically, and you lose access to your resources and data"; AWS retiene el contenido 90 días antes de borrar de forma permanente la cuenta y sus recursos; se puede pasar a plan de pago (pay-as-you-go) dentro de esos 90 días, y los créditos restantes se aplican a facturas futuras. Misma fuente.
- H7.3. El plan Free incluye "select AWS services"; los servicios que podrían gastar créditos rápido (Savings Plans, Reserved Instances, etc.) requieren plan de pago. Misma fuente. El plan Free se convierte automáticamente en plan de pago si la cuenta se une a AWS Organizations, entre otros supuestos. Misma fuente.
- H7.4. Lista de servicios del Free Tier de "Sign up for AWS (new)": incluye AWS Lambda (sin Lambda@Edge), Amazon EventBridge, Amazon Simple Storage Service (sin S3 Access Grants), Amazon CloudWatch, Amazon CloudWatch Logs, AWS Glue, Amazon Athena, Amazon Simple Queue Service, AWS Lake Formation; no figuran Amazon EMR ni Amazon Managed Workflows for Apache Airflow (este último en "no soportados"). Fuente: https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html (2026-11-13). La lista dice "Amazon EventBridge", sin nombrar Scheduler por separado.
- H7.5. La SCP gestionada del Free Tier de ese tipo de cuenta incluye `lambda:*` y `scheduler:*` en su lista de acciones permitidas (`NotAction` de un Deny). Fuente: https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html (2026-11-13), sección "Service control policies for the Free Tier for projects".
- H7.6. La misma página contiene, en el apartado de límites de gasto ("spend limits"), una política que niega `lambda:CreateFunction`, `scheduler:CreateSchedule`, `sqs:CreateQueue` y `glue:CreateJob`, y otra que niega `lambda:InvokeFunction`, `lambda:PutFunctionConcurrency` e `InvokeAsync`, aplicadas "as it nears the spend limit". No se confirmó si la cuenta del proyecto tiene un spend limit configurado. Misma fuente.
- H7.7. Regiones de las cuentas creadas con "Sign up for AWS (new)": AWS asigna la región del proyecto según el país de contacto: `us-east-2`, `eu-north-1` o `ap-southeast-2`; la doc dice que "any Regional resources that you create will be hosted in that Region" y que las funciones multirregión o entre regiones no están soportadas. Fuente: https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html (2026-11-13). No está confirmado que la cuenta del proyecto sea de ese tipo; las Conventions mencionan un bucket manual en `eu-north-1` y que la cuenta sigue en plan Free.
- H7.8. Lambda y S3 figuran en https://aws.amazon.com/free/compute/ (Lambda: "always free service on the Free and Paid plan", 1.000.000 peticiones y hasta 400.000 GB-s al mes) y S3 como "Available on both plans" en https://aws.amazon.com/free/ (2026-11-13). EventBridge Scheduler no se nombra en esas páginas.

### H8. Un schedule de 15 min sigue gastando y opciones para pausarlo (hechos)

- H8.1. Un schedule recurrente no depende de que alguien lo use: sigue invocando a su destino mientras esté habilitado y entre `StartDate` y `EndDate` (H1.3, H1.6, H1.13). Cada invocación del Lambda consume peticiones y GB-s (H6); con el nivel gratuito vigente el consumo estimado cae dentro de las cuotas gratuitas, y lo que exceda se descuenta de los créditos del plan Free (H7.1). Los créditos y el nivel gratuito del plan Free se consumen aunque nadie mire los datos.
- H8.2. Pausar vía el propio schedule: `State` = `DISABLED` en `CreateSchedule`/`UpdateSchedule` (H1.13).
- H8.3. Acotar en el tiempo: `EndDate` ("the date, in UTC, before which the schedule can invoke its target") o `StartDate` futura (H1.13).
- H8.4. Borrar el schedule (`DeleteSchedule`); un schedule `at` ya ejecutado sigue contando en la cuota hasta borrarse (schedule-types, H1.3).
- H8.5. Pausar vía Lambda: concurrencia reservada 0 "stops your Event Function from processing any events until you remove the limit"; la configuración no tiene coste. Fuente: https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html (2026-11-13). Con ese ajuste, el schedule sigue disparando y las invocaciones se rechazan; el efecto sobre reintentos y DLQ de Scheduler no se verificó.
- H8.6. Cambiar la cadencia (otra expresión `rate` o `cron`) es una actualización del schedule (`UpdateSchedule`, H1.13); reduce el número de invocaciones sin detenerlas.
- H8.7. Toda modificación anterior es un cambio de recurso AWS: por IaC only y Apply gate, solo se aplica por Terraform desde CI (dev al fusionar; prod con aprobación manual). Ver Tensiones.
- H8.8. Si la cuenta Free se cierra (H7.2), se pierde el acceso a los recursos; AWS conserva el contenido 90 días.

## Opciones observadas (sin recomendación)

Se listan las alternativas que la documentación permite, con lo que cada una implica según los hechos. No se elige ninguna.

| Decisión | Opción | Hechos asociados |
|----------|--------|------------------|
| Disparador | EventBridge Scheduler | H1.1 a H1.13: zonas IANA, ventana flexible, `RetryPolicy`, DLQ, atributos de contexto con `scheduled-time`; es la opción que la doc recomienda frente a las reglas. |
| Disparador | Regla programada de EventBridge (legacy) | H1.1, H1.2: `cron(0/15 * * * ? *)` o `rate(15 minutes)` en UTC; la doc la marca legacy; no se obtuvo qué instante lógico lleva el evento de una regla (ver No verificado). |
| Expresión | `rate(15 minutes)` | H1.6: empieza en `StartDate` o al crearse; la alineación con los cuartos de hora no está documentada. |
| Expresión | `cron(0/15 * * * ? *)` | H1.2, H1.3: minutos 0, 15, 30, 45 de cada hora, en la zona indicada (UTC por defecto). |
| Zona | UTC | H1.4: sin ajuste de horario de verano. |
| Zona | `Europe/Paris` | H1.4: en un cron de 15 min, al adelantar el reloj se omiten las invocaciones de la hora inexistente. |
| Ventana | `OFF` | H1.5: invocación en el minuto programado. |
| Ventana | `FLEXIBLE` | H1.7: dispersa la invocación dentro de la ventana; el instante real difiere del programado, `scheduled-time` sigue siendo el programado (H1.12). |
| Fallos | Sin DLQ | H1.9: reintentos hasta el tope y se descarta el evento. |
| Fallos | DLQ SQS estándar | H1.10: requiere una cola SQS y `sqs:SendMessage` en el rol; SQS figura en el Free Tier de cuentas nuevas (H7.4); su tarifa no se obtuvo. |
| Arquitectura | x86_64 | H2.2: tarifa de duración mayor en US East (H6); wheels `manylinux_2_28_x86_64`. |
| Arquitectura | arm64 | H2.2, H2.3, H6: tarifa menor en US East; exige wheels `manylinux_2_28_aarch64`; disponibilidad en eu-west-3 sin confirmar en página oficial (H5.3). |
| Runtime | `python3.13` / `python3.14` | H2.1: GA, deprecación 2029-06-30. |
| Runtime | `python3.12` | H2.1: deprecación 2028-10-31. |
| Runtime | `python3.15` | H2.1: en public preview, sin SLA. |
| Empaquetado | Zip con dependencias | H2.4, H2.5: límite 50 MB subida directa y 250 MB descomprimido; sin ECR. |
| Empaquetado | Zip + capa | H2.4, H2.5: la capa cuenta en el límite de 250 MB; máximo 5 capas; la capa debe ser compatible con la arquitectura (H2.3). |
| Empaquetado | Imagen de contenedor | H2.5, H2.6: hasta 10 GB; requiere repositorio ECR en la misma región; no se puede cambiar el tipo en una función existente; el coste de ECR no se obtuvo. |
| Retención de logs | Grupo de log gestionado por Terraform con `retention_in_days` | H4.2, H4.3: el valor de retención se fija por grupo; sin ello, indefinida. |
| Retención de logs | Política de retención de cuenta | H4.3: mínimo 30 días y sustituye el valor del grupo; aplica a todos los grupos o a un prefijo. |
| Pausa | `State = DISABLED` | H8.2. |
| Pausa | `EndDate` / `StartDate` | H8.3. |
| Pausa | Borrar el schedule | H8.4. |
| Pausa | Concurrencia reservada 0 | H8.5: el schedule sigue disparando; efecto en reintentos sin verificar. |
| Pausa | Reducir la cadencia | H8.6. |
| Fin del plan Free | Pasar a plan de pago dentro de 90 días | H7.2. |
| Fin del plan Free | Dejar que la cuenta se cierre | H7.2, H8.8. |

## Tensiones con Conventions

Se registran sin resolver.

- T1. Region frente a las regiones de las cuentas "Sign up for AWS (new)". La Convention Region fija `eu-west-3`. La doc de AWS dice que en cuentas creadas con ese tipo de alta, los recursos regionales se alojan en la región asignada (`us-east-2`, `eu-north-1` o `ap-southeast-2`) y que el multirregión no está soportado (H7.7). Scheduler existe en `eu-west-3` (H5.1), pero no se sabe si la cuenta del proyecto puede crear recursos allí. Depende de cómo se abrió la cuenta (ver Preguntas Q1). El bucket manual en `eu-north-1` que cita Apply gate es coherente con una cuenta asignada a esa región, pero no lo prueba.
- T2. Apply gate e IaC only frente a pausar o reanudar el schedule. Cualquier pausa (`DISABLED`, `EndDate`, borrar, concurrencia 0) es un cambio de recurso AWS (H8.7). Ningún agente ejecuta `terraform apply` ni comandos AWS; `apply` en dev ocurre desde CI al fusionar y prod requiere aprobación manual. Una pausa urgente por consola o CLI contradice IaC only. Esta nota no indica qué camino se usará.
- T3. No hourly-billed resources frente al gasto por uso de un schedule permanente. Lambda, Scheduler y CloudWatch Logs cobran por uso (H6), no por hora estando inactivos, así que no incumplen la Convention. Pero el schedule de 15 min consume invocaciones y créditos aunque nadie use los datos (H8.1), y la Convention no cubre el coste por uso. No es un conflicto literal; se deja anotado como zona sin regla.
- T4. Idempotency frente a la entrega at-least-once. Scheduler entrega "at-least-once" (H1.8) y reintenta (H1.9), de modo que la misma ventana puede llegar más de una vez. La Convention Idempotency exige que relanzar dé el mismo resultado y prohíbe `now()`. El atributo `scheduled-time` existe (H1.12), pero el mecanismo para escribir en `landing/` sin duplicar archivos (claves S3, escritura condicional) no se investigó en esta área (ver No verificado). Medallion layers fija `landing/` como crudo y append-only en Bronze, lo que traslada la deduplicación a etapas posteriores.
- T5. Region frente a servicios "globales" de la cuenta de proyecto. La página de regiones indica que CloudWatch Logs está disponible en `us-east-1` (H7.7, línea final de la lista de consideraciones). Se registra por si afecta a la retención de logs en `eu-west-3`; no se verificó su alcance.
- T6. El plan Free y el criterio de hecho "6 meses de histórico". El plan Free dura hasta seis meses o hasta agotar créditos (H7.1) y al cerrarse se pierde el acceso (H7.2). El criterio de hecho de la Fase 2 pide seis meses de histórico y micro-lotes nuevos. La ventana del plan puede cerrarse antes de que acabe el proyecto. Se registra como hecho de calendario, sin resolver.

## Preguntas para el owner

- Q1. ¿La cuenta se abrió con "Sign up for AWS (new)" o con "Sign up for AWS (advanced)"? En la primera, la región del proyecto la asigna AWS y puede no ser `eu-west-3` (T1). Hace falta saberlo antes de planificar cualquier recurso regional; el owner puede comprobarlo en https://settings.aws.com (Project, Additional Info) según la doc.
- Q2. ¿Hay un spend limit configurado en la cuenta? Las políticas de spend limit niegan `lambda:CreateFunction` y `scheduler:CreateSchedule` al acercarse al límite (H7.6).
- Q3. ¿Qué fecha de apertura tiene la cuenta y cuánto crédito queda? Determina el calendario del plan Free (H7.1, T6). No es un dato que esta investigación pueda obtener (Apply gate).
- Q4. ¿Qué debe ocurrir con el schedule cuando nadie usa el proyecto: seguir corriendo, pausarse o borrarse? Las opciones están en H8; la elección es del owner.
- Q5. ¿Se acepta como evidencia de la configuración del schedule la salida de `terraform plan` en CI o el owner aportará capturas? (Verification ownership; el orquestador no puede ejecutar comandos AWS.)
- Q6. ¿Qué duración y memoria se espera para el handler (escala de 96 lotes/día con histórico de 6 meses)? Los costes de H6 usan un escenario hipotético de 512 MB y 30 s.
- Q7. ¿Hay objetivo de arquitectura (x86_64 o arm64) y de runtime (GA frente a preview)? No es una decisión de esta etapa.

## No verificado

1. Valores por defecto de `MaximumRetryAttempts` y `MaximumEventAgeInSeconds` en Scheduler: la página de la guía no se pudo leer; la API solo da los rangos (H1.9).
2. Si el destino plantillado de Lambda invoca de forma síncrona o asíncrona, y por tanto cuántos reintentos adicionales añade Lambda por su cuenta.
3. Cómo se alinea la cadencia de `rate(15 minutes)` con la hora de creación del schedule, más allá de "empieza tras `StartDate` o de inmediato" (H1.6).
4. Qué instante lógico lleva el evento de una regla programada de EventBridge (no se leyó la estructura del evento de regla).
5. Tarifa de Lambda (peticiones, GB-s x86 y Arm) en eu-west-3; solo se obtuvieron cifras de US East y el valor Arm de fuentes de terceros (H6).
6. Disponibilidad de arm64 en eu-west-3 según la página oficial de precios de Lambda (H5.3).
7. Tarifa de CloudWatch Logs en eu-west-3 y el resto de la página de precios (se leyeron 100.000 de 154.064 caracteres).
8. Tamaño real de Faker (y sus datos de localización) empaquetado en zip frente al límite de 250 MB (H2.8).
9. Valores de retención por grupo de log permitidos por la API `PutRetentionPolicy` (solo se obtuvo la lista de la política de cuenta, H4.3).
10. Comportamiento de las claves S3 deterministas y de las escrituras condicionales para la idempotencia por ventana (fuera de esta pasada; área S3/landing).
11. Si la cuenta del proyecto es "Sign up for AWS (new)" y si tiene spend limit (Q1, Q2).
12. Si "Amazon EventBridge" en la lista de servicios del Free Tier incluye Scheduler (la lista no lo nombra por separado, H7.4; la SCP sí incluye `scheduler:*`, H7.5).
13. Efecto de la concurrencia reservada 0 sobre los reintentos y la DLQ de Scheduler (H8.5).
14. Alcance de la afirmación "Amazon CloudWatch Logs are available in us-east-1" de la página de regiones de proyectos (T5).
15. Tarifa de SQS y de ECR (opciones DLQ e imagen de contenedor).
16. Revisión adversarial: esta nota de área no pasó por el `adversarial-reviewer`; la hará el consolidador.
