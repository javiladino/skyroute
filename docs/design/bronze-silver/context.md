# bronze-silver — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 3 — Bronze y Silver con Spark + Iceberg (README § Fases): "Jobs PySpark con tests, MERGE, sesionización, SCD2, conversión de divisas. Hecho cuando relanzar un día da exactamente el mismo resultado." Entrada: el clickstream en `landing/` y las Reservas en Postgres local de `generator-landing` (Fase 2, pendiente solo del backfill del día D). Restricciones: Conventions Table format, Medallion layers, Compute split, Region, No hourly-billed resources, IaC only, Apply gate e Idempotency. Decisiones abiertas del README que tocan esta fase: dónde corre Spark, modo de escritura Iceberg por tabla, motor de checks WAP y credenciales de AWS para lo que corre en local. Rama: `docs/bronze-silver-research` (sale de `docs/generator-landing-test`). Etapa en curso: Research.

## Rulings

- **Research decisions (javiladino, 2026-11-20 10:00):** grill-me del Research (T1–T14), una línea por decisión:
  - Generador → se cambia dentro de la Fase 3: sesiones por cliente con compras enlazadas y reservas con cambios de estado, deterministas por fecha lógica; después se regenera el histórico con un backfill.
  - Dónde corre Spark → en local a diario y en Glue 5 Flex solo en demos; los jobs reciben `--run-date` y la configuración del catálogo por parámetros, iguales en los dos motores.
  - Credenciales en local → rol `skyroute-<env>-local-data` de mínimo privilegio (bucket de datos y bases `skyroute_<env>_*`, según Medallion layers enmendada el 2026-11-20), que solo asume `skyroute-dev` con MFA desde `aws login`; sesión de 1 h y variables `AWS_*` temporales en los contenedores. El rol va en el módulo y la boundary en `bootstrap/`. En Propose, aws-researcher confirma que la condición de MFA funciona con `aws login`.
  - Escritura Iceberg → Bronze con reemplazo de partición por `_ingest_date`; Silver en copy-on-write. `expire_snapshots` y `rewrite_data_files` van en `spark/jobs/maintenance/`.
  - Checks WAP → asserts propios en PySpark, con las reglas en YAML. Si un check falla, la rama no se publica.
  - `_ingested_at` → `run_date` 00:00 UTC + slot × 15 min; `_batch_id` = hash(`run_date`, `_source_file`).
  - Reservas a `landing/` → export diario e idempotente a `landing/bookings/ingest_date=…/part.json.gz`. Enmendado el 2026-11-20 en Propose: un trigger de Postgres escribe cada cambio de estado en `bookings_history` (CDC ligero) y el export lee las filas de esa tabla del día lógico, así que caben varias versiones por día.
  - Relanzar un día (Propose, 2026-11-20) → independiente del orden: relanzar D en cualquier momento, incluso después de D+5, deja Silver idéntico a una ejecución en orden.
  - Tipo de cambio por reserva (Propose, 2026-11-20) → el del día de `created_at`. Silver guarda el tipo aplicado y la divisa original.
  - Athena → workgroup `skyroute-<env>` creado con Terraform: configuración forzada, corte de 100 MB por consulta y resultados en `athena-results/` con 7 días de lifecycle.
  - Permisos → una PR propia de `bootstrap/` antes de la del módulo. Acciones acotadas por nombre (`skyroute_<env>_*`, `skyroute-<env>-*`; PassRole solo a `skyroute-<env>-glue-job` con `iam:PassedToService = glue.amazonaws.com`). La revisa security-reviewer y la re-aplica el owner.
  - Histórico → Bronze es la copia duradera y debe ingerir los 182 días regenerados antes de que pasen 30 días; `landing/` mantiene 30 días.
  - Tipos de cambio → tipos de referencia del BCE (base EUR), una tarea diaria a `landing/fx/`; fines de semana y festivos toman el último día hábil. Si falla, se reintenta; nunca se inventa un tipo.
  - PII → Bronze íntegro; Silver sustituye el email por HMAC-SHA256 con la clave en SSM Parameter Store estándar y conserva el consentimiento. Lake Formation se aplaza.
  - Budget → se queda en 10 USD y las demos de Glue se lanzan a mano (con la Proposal 2, unos 0,20 USD por demo; el owner confirmó el 2026-11-20 el precio en eu-west-3: 0,29 USD/DPU-h). El paso a Paid queda fuera de la Fase 3.

- **Plan decisions (javiladino, 2026-11-20 19:00):** el owner aceptó las 9 recomendaciones de las Open questions de `working/plan.md`:
  - `history_id` con `TRUNCATE … RESTART IDENTITY` y replay en orden determinista (test G3).
  - Clave HMAC desde un `ephemeral "random_password"` hacia `value_wo`, con `value_wo_version` para rotarla.
  - Histórico de FX con el mismo script local, pasando `--from` y `--to` sobre la serie del BCE.
  - Las fases 4–8 leen dev; prod solo cuando se cierra la fase.
  - El lifecycle de `athena-results/` va en `modules/generator-landing/bucket.tf` (la PR 2 toca ese módulo).
  - Umbral de sesión de 30 min, configurable con `--session-gap-minutes`.
  - pytest en CI con `spark-tests.yml`: Python 3.11 y sin credenciales AWS.
  - Las sesiones se escriben con MERGE y `NOT MATCHED BY SOURCE DELETE`.
  - `amount_eur` se redondea con HALF_EVEN a 2 decimales.
  - Enmienda del 2026-11-20 (Implement, fase 2): el refresh de `aws_ssm_parameter` llama a GetParameter con WithDecryption, aunque el valor sea `value_wo`. Por eso `ci-plan` y `ci-apply-<env>` reciben `ssm:GetParameter` y `kms:Decrypt` solo sobre `/skyroute/<env>/hmac-email-key`, condicionados a `kms:ViaService` de SSM y a `kms:EncryptionContext:PARAMETER_ARN`. El Deny de Decrypt de ci-plan se acota en consecuencia. Riesgo aceptado: la CI del repo puede leer la clave (las PR de forks no reciben token OIDC).
  - Enmienda del 2026-11-21 (Implement, fase 3, despliegue): el apply de la PR #28 llevó el generador nuevo también a prod (run 44899658035), porque las dos instancias comparten el módulo. El owner lo aceptó: prod se queda con el generador nuevo y su schedule sigue activo. La mezcla de formatos en `landing/` de prod caduca a los 30 días, y el histórico de prod se regenera al cierre de la fase. Las fases 4–8 siguen leyendo dev.
  - Enmienda del 2026-11-21 (Implement, fase 3): FX escribe un archivo por día natural; sábados, domingos y festivos llevan los tipos de la última publicación ≤ D con su `rate_date` real (nunca un tipo inventado).
  - Después de la revisión (2026-11-20), el owner aprobó el plan y además decidió: Python 3.11 en local con Homebrew (`python@3.11`), y `glue-temp/` con 1 día de lifecycle.

## Journal (newest first)

**2026-11-21 (Implement, fase 8):** executor (Sonnet) implementó el mantenimiento Iceberg, los 7 jobs Glue 5 Flex, `spark-tests.yml` y los comandos de AGENTS.md. Revisiones: adversarial (Opus) GO-WITH-FIXES, security-reviewer (Opus) OK con notas y cost-guard (Sonnet) APTO con notas. executor aplicó los hallazgos y añadió PyYAML porque Glue 5.0 no lo trae. El owner aplazó el log group por entorno, porque necesita cambiar bootstrap (deuda en findings). Verificación del orquestador: 126 passed, ruff, fmt y validate en dev y prod. Siguiente: PR, apply y demo del owner.

**2026-11-21 (Implement, fase 7):** executor (Sonnet) implementó el Silver de clickstream (`events` con HMAC, `sessions`). Revisión 1 (Opus): NEEDS-REVISION, porque los tardíos que cruzaban medianoche se perdían (H1). El owner decidió reescribir [D-4, D] con tope de 24 h, que un hueco > 30 min parte la sesión, que el HMAC va sobre el email normalizado y que session_key no es estable hasta D+4. Revisión 2 (Opus): GO-WITH-FIXES, aplicados (comparación sin email_hmac, check contra Bronze, fallo en cadenas largas en el borde). stage-author alineó §5, §8 y U23 de plan.md. Verificación del orquestador: 110 passed, ruff limpio. Siguiente: fase 8.

**2026-11-21 (Implement, fase 6):** executor (Sonnet) implementó el Silver FX (`fx_daily`, `bookings_eur`, U10-U12). adversarial-reviewer (Opus) dio GO-WITH-FIXES. El owner renombró el tipo a `rate_per_eur` (cotización BCE) y fijó que Silver no arrastra el fin de semana, porque lo hace el generador. executor aplicó M1, M2 y M4 y L1 a L4, y renombró el test a `test_silver_fx.py`. stage-author ajustó el §6 de plan.md. Verificación del orquestador: 92 passed (generators + spark) y ruff limpio. Pendiente: el rango de FX debe cubrir todo el rango de created_at. Siguiente: fase 7.

**2026-11-21 (Implement, fase 5):** executor (Sonnet) implementó el Silver de Reservas (`bookings_scd2`, `bookings_current`, checks YAML, U5-U9 y U21). adversarial-reviewer (Opus) dio GO-WITH-FIXES (M1-M4, L1-L5). executor aplicó M1-M4, L1, L2 y L5; M2 se resolvió con una precondición, porque el export garantiza `changed_at` dentro de D. El owner fijó `amount` en decimal(12,2) y excluyó `.claude/` de ruff. Verificación del orquestador: 32 passed, ruff limpio. L3 y L4 pasan a la fase 8. Siguiente: fase 6.

**2026-11-21 (Implement, fase 4):** executor (Sonnet) implementó el Bronze genérico en Spark/Iceberg (19 tests). adversarial-reviewer (Opus) dio GO-WITH-FIXES; el owner eligió esquema explícito, y los rangos `--from/--to` cubren la sesión MFA de 1 h. PRs #30 (código) y #31 (runbook). El owner ejecutó el runbook en dev: R=2026-11-21, rango 2026-05-23..2026-11-20, gate vence 2026-12-21. Clickstream se reanudó una vez por `ExpiredToken`. Athena: clickstream, bookings y fx con 182 días cada una. La espera del paso 7 del runbook tenía una carrera y se corrigió. Siguiente: fase 5.

**2026-11-21 (Implement, fase 3):** executor (Sonnet) implementó el generador (sesiones, versiones de reserva, trigger `bookings_history`, export, FX del BCE). El owner aprobó guardar FX también en fin de semana (enmienda del Ruling Plan decisions) y fijar `ruff.toml`. adversarial-reviewer (Opus) dio GO-WITH-FIXES; executor aplicó los hallazgos 2–6 (FX exige publicación de D o una posterior). Verificación: 52 passed y ruff limpio (re-ejecutados por el orquestador); G3 contra Postgres con md5 idéntico en dos rebuilds (578 filas); export real idéntico byte a byte, ejecutado por el owner. PR #28 fusionada y aplicada en dev y prod; la Lambda de prod también pasó al generador nuevo, y el owner lo aceptó (enmienda del Ruling Plan decisions). Siguiente: fase 4.

**2026-11-21 (Implement, fase 2):** executor (Sonnet) implementó el módulo `lakehouse`; security-reviewer encontró el refresh de SSM con WithDecryption (resuelto con la enmienda 1b, PR #25) y cost-guard dio APTO. PR #26 fusionada y aplicada en dev y prod (plan: dev 9 add / 2 change, prod 7 add / 2 change, 0 destroy; el segundo change añade `BUCKET_NAME` a la Lambda). Gate de MFA en PASS: `skyroute-dev-local-data` se asume desde `aws login` con MFA. Siguiente: fase 3.

- 2026-11-20: fase 1 (PR de bootstrap); H1 High (bases Glue compartidas) resuelto con bases por entorno.
- 2026-11-20: Plan con 8 fases (Glue Flex a 0,29 USD/DPU-h, scripts como `aws_s3_object`); revisión NEEDS-REVISION con 11 hallazgos, ya aplicados.
- 2026-11-20: Propose; 3 propuestas revisadas dos veces y el owner eligió la Proposal 2 (relanzar sin depender del orden, export desde `bookings_history`, tipo por `created_at`).
- 2026-11-20: grill-me tras el gate del Research; 13 preguntas resueltas (Ruling Research decisions).
- 2026-11-19: Research escrito y revisado (adversarial, security, cost-guard); 14 tensiones T1-T14 en `working/research.md`.
- 2026-11-14: topic abierto y Research lanzado con `session-orchestration`.

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | What it holds |
|------|------|------|---------------|
| `working/test.md` | draft | on-demand | Test de la Fase 3, por fases; fases 1 a 7 en PASS; fase 8 verificada en local, pendiente del apply y la demo en Glue (2026-11-21) |
| `working/plan.md` | draft | on-demand | Plan de la Fase 3 (Proposal 2): 8 PRs, gates del owner, tests de idempotencia U1–U23 |
| `working/proposal.md` | draft | on-demand | Propose de la Fase 3: 3 propuestas revisadas; Decision: Proposal 2 |
| `working/research.md` | draft | on-demand | Research de la Fase 3: lo que existe hoy para Bronze y Silver (C1–C6, T1–T14, revisado y corregido) |
