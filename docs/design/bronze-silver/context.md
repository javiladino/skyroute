# bronze-silver — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 3 — Bronze y Silver con Spark + Iceberg (README § Fases): "Jobs PySpark con tests, MERGE, sesionización, SCD2, conversión de divisas. Hecho cuando relanzar un día da exactamente el mismo resultado." Entrada: el clickstream en `landing/` y las Reservas en Postgres local de `generator-landing` (Fase 2, pendiente solo del backfill del día D). Restricciones: Conventions Table format, Medallion layers, Compute split, Region, No hourly-billed resources, IaC only, Apply gate e Idempotency. Decisiones abiertas del README que tocan esta fase: dónde corre Spark, modo de escritura Iceberg por tabla, motor de checks WAP y credenciales de AWS para lo que corre en local. Rama: `docs/bronze-silver-research` (sale de `docs/generator-landing-test`). Etapa en curso: Research.

## Rulings

- **Research decisions (javiladino, 2026-11-20 10:00):** grill-me del Research (T1–T14), una línea por decisión:
  - Generador → se cambia dentro de la Fase 3: sesiones por cliente con compras enlazadas y reservas con cambios de estado, deterministas por fecha lógica; después se regenera el histórico con un backfill.
  - Dónde corre Spark → en local a diario y en Glue 5 Flex solo en demos; los jobs reciben `--run-date` y la configuración del catálogo por parámetros, iguales en los dos motores.
  - Credenciales en local → rol `skyroute-<env>-local-data` de mínimo privilegio (bucket de datos y bases `skyroute_*`), que solo asume `skyroute-dev` con MFA desde `aws login`; sesión de 1 h y variables `AWS_*` temporales en los contenedores. El rol va en el módulo y la boundary en `bootstrap/`. En Propose, aws-researcher confirma que la condición de MFA funciona con `aws login`.
  - Escritura Iceberg → Bronze con reemplazo de partición por `_ingest_date`; Silver en copy-on-write. `expire_snapshots` y `rewrite_data_files` van en `spark/jobs/maintenance/`.
  - Checks WAP → asserts propios en PySpark, con las reglas en YAML. Si un check falla, la rama no se publica.
  - `_ingested_at` → `run_date` 00:00 UTC + slot × 15 min; `_batch_id` = hash(`run_date`, `_source_file`).
  - Reservas a `landing/` → export diario e idempotente a `landing/bookings/ingest_date=…/part.json.gz` con las filas cuyo `updated_at` cae en el día lógico.
  - Athena → workgroup `skyroute-<env>` creado con Terraform: configuración forzada, corte de 100 MB por consulta y resultados en `athena-results/` con 7 días de lifecycle.
  - Permisos → una PR propia de `bootstrap/` antes de la del módulo. Acciones acotadas por nombre (`skyroute_*`, `skyroute-<env>-*`; PassRole solo a `skyroute-<env>-glue-job` con `iam:PassedToService = glue.amazonaws.com`). La revisa security-reviewer y la re-aplica el owner.
  - Histórico → Bronze es la copia duradera y debe ingerir los 182 días regenerados antes de que pasen 30 días; `landing/` mantiene 30 días.
  - Tipos de cambio → tipos de referencia del BCE (base EUR), una tarea diaria a `landing/fx/`; fines de semana y festivos toman el último día hábil. Si falla, se reintenta; nunca se inventa un tipo.
  - PII → Bronze íntegro; Silver sustituye el email por HMAC-SHA256 con la clave en SSM Parameter Store estándar y conserva el consentimiento. Lake Formation se aplaza.
  - Budget → se queda en 10 USD y las demos de Glue se lanzan a mano (unos 0,15 USD cada una; el precio en eu-west-3 lo confirma Propose). El paso a Paid queda fuera de la Fase 3.

## Journal (newest first)

**2026-11-20 (grill-me):** El owner aprobó el gate del Research y el grill-me resolvió 13 preguntas, recogidas en el Ruling Research decisions. Siguiente: Propose (stage-author Opus en `working/proposal.md`), con aws-researcher para confirmar MFA con `aws login` y el precio de Glue Flex en eu-west-3.

**2026-11-19 (Research):** stage-author (Opus) escribió `working/research.md`. Revisión en paralelo: adversarial-reviewer (Opus, GO-WITH-FIXES, 14 hallazgos), security-reviewer (Opus, 7) y cost-guard (Sonnet, 7). executor (Sonnet) ejecutó los checks locales: `.env.example` existe y está versionado (el hallazgo contrario de security era erróneo, lo confirmó el orquestador); pytest no está instalado. Un stage-author (Opus) aplicó los hallazgos: 14 tensiones (T1-T14) y una sección "No comprobado" con los checks de AWS, que son del owner. Siguiente: gate del owner y grill-me antes de Propose.

**2026-11-14:** Topic abierto (scaffold) y Research lanzado con `session-orchestration` (Opus para el documento consolidado y los revisores profundos, Sonnet para notas de área, cost-guard y executor).

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | What it holds |
|------|------|------|---------------|
| `working/research.md` | draft | on-demand | Research de la Fase 3: lo que existe hoy para Bronze y Silver (C1–C6, T1–T14, revisado y corregido) |
