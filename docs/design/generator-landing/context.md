# generator-landing — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 2 — Generador y landing (README § Fases): "Simulador OTA coherente, Lambda + EventBridge, Postgres local, archivos en `landing/`. Hecho cuando hay 6 meses de histórico y llegan micro-lotes nuevos." Qué simula el generador y qué entra en `landing/`: `platform-blueprint/current/project/README.md` § Fuentes simuladas. Restricciones: Conventions Region, IaC only, Apply gate, No hourly-billed resources, Medallion layers, Idempotency y Bootstrap identity; Ruling Foundations design (`foundations/context.md`). Hechos de partida: `ci-apply` hoy solo tiene permisos sobre el backend del state, y cualquier recurso de esta fase obliga a ampliarlos dentro de la boundary `ci-boundary`; la cuenta sigue en plan Free, que se cierra a los 6 meses o al agotar los créditos. Rama: `docs/generator-landing-research`. Etapa en curso: Research.

## Rulings

- **Research decisions (javiladino, 2026-11-13 20:00):** Decididas en grill-me tras Research; Propose las aplica y no las reabre. La discusión está en `working/research.md` (las T de cada línea).
  - Histórico (T1): regenerable bajo demanda. El generador es determinista por fecha lógica y se mantienen los 30 días de `landing/`. La Fase 2 está hecha cuando un backfill deja 182 días en `landing/` y el schedule añade micro-lotes.
  - Backfill: lo hace la misma Lambda, con el payload `{from, to}`. La invoca el owner, y no se crean credenciales nuevas.
  - Reservas (T6): el mismo generador siembra Postgres local con ids coherentes con el clickstream. La extracción a `landing/` se aplaza (README § Open decisions).
  - Bootstrap (T2): Convention Apply gate aclarada. El owner re-aplica `bootstrap/` en cada cambio y el runbook gana una sección de re-apply.
  - Prod (T17): se corrige en la Fase 2, antes de ampliar permisos. `ci-apply` se separa en `ci-apply-dev` y `ci-apply-prod`. Esto enmienda el Ruling Foundations design (`foundations/context.md`) al cerrar el ciclo. El owner pone `can_admins_bypass: false` en el environment `dev`.
  - Boundary (T3/T18): `workload-boundary` propia, sin state. Los roles de workload van con path `/workload/` y prefijo `skyroute-`, y `iam:PassRole` se limita con `iam:PassedToService` a lambda y scheduler.
  - Plan en PR (T19): riesgo aceptado y acotado. `ci-plan` es de solo lectura y no tiene acciones de datos. Propose valora `-lock=false`.
  - Tiempo lógico (T7/T8/T20): `scheduled-time` redondeado a 15 min da `(run_date, slot)`, y el backfill usa los mismos campos. Los eventos tardíos van en el slot donde llegan. El backfill termina en D-1 y el schedule empieza en D. `updated_at` lo pone el generador.
  - Bucket (T9/T10): uno por entorno, con SSE-S3, TLS-only, bloqueo de acceso público y sin versioning. Los skips de checkov van por recurso y con su motivo.
  - Schedule (T13/T21): ENABLED en prod y DISABLED en dev, según una variable. Topes: concurrencia reservada de 1, RetryPolicy acotada, logs con 14 días de retención y una alarma de Invocations que avisa por SNS al email.
  - Plan Free (T12/T14): la cuenta sigue en Free. Antes de Plan, el owner aporta la salida de `aws freetier get-account-plan-state` y `aws budgets describe-budget`. Region se prueba con el primer apply a dev.

## Journal (newest first)

**2026-11-13 (acciones del owner):** El owner puso `can_admins_bypass: false` en el environment `dev`; el orquestador lo verificó con `gh api`. El owner aportó dos salidas, que executor guardó en `evidence/`. Plan Free: ACTIVE, 170,55 USD de créditos, vence el 2027-01-22. Budget: `IncludeCredit: false`, así que las alertas miden el coste antes de aplicar créditos (V23 verificado). La parte de T21 que dependía de los créditos queda resuelta; la de un schedule a 0 USD sigue en pie. Nueva decisión abierta en el README: paso a Paid antes de que venza el plan.

**2026-11-13 (grill-me y cierre):** El owner dio el visto bueno a Research y resolvió 10 decisiones (Ruling Research decisions). Aprobó aclarar la Convention Apply gate, porque bootstrap se re-aplica en cada cambio. Se abre una decisión de proyecto: las credenciales para lo que corre en local (README § Open decisions). `findings.md` se crea con 3 entradas. Triage: `working/research.md` y sus 5 notas quedan en `working/`, en uso, como entrada de Propose. Cierre: `design_check.py`, 0 FAIL, 0 WARN. Pendiente para el cierre del ciclo: enmendar el Ruling Foundations design (dos roles a tres). Siguiente: Propose.

**2026-11-13 (Research):** Cinco notas de área (stage-author, Sonnet) consolidadas en `working/research.md` (stage-author, Opus). Una ronda de revisión: adversarial-reviewer (Opus, GO-WITH-FIXES), security-reviewer (Opus) y cost-guard (Sonnet). executor (Sonnet) ejecutó los comandos marcados como no comprobados. Un stage-author (Sonnet) aplicó los 31 hallazgos y quedan 22 tensiones, 39 preguntas y 22 puntos sin verificar. El orquestador comprobó con `ci_roles.tf:244-286` y con `gh api …/environments/dev` que `ci-apply` acepta `environment:dev` y puede escribir el state de prod, y que `dev` tiene `can_admins_bypass: true`. Es un hecho de la Fase 1 y queda como tensión T17 (Apply gate). Siguiente: gate del owner y grill-me con las decisiones abiertas antes de Propose.

**2026-11-13:** Topic abierto (scaffold) en la rama `docs/generator-landing-research`.

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `evidence/freetier-plan-state.json` | reference | on-demand | Salida de `aws freetier get-account-plan-state` aportada por el owner el 2026-11-13: plan Free ACTIVE, 170,55 USD, vence el 2027-01-22 |
| `evidence/describe-budget-costtypes.json` | reference | on-demand | Salida de `aws budgets describe-budget` de `skyroute-monthly-10usd` con `--query` (sin notificaciones ni email), aportada por el owner el 2026-11-13: CostTypes con `IncludeCredit: false` |
| `working/research.md` | draft | on-demand | Research de la Fase 2: criterio C1-C6, hechos (a)/(b)/(c), secretos, PII, coste, 5 componentes, tensiones T1-T22, preguntas al owner, no verificado |
| `working/research/generator-data.md` | reference | on-demand | Nota de área: 5 fuentes, coherencia entre ids, determinismo por fecha lógica, volumen de 6 meses, librerías, BCE |
| `working/research/lambda-eventbridge.md` | reference | on-demand | Nota de área: Scheduler frente a reglas, runtime y empaquetado, logs, coste, plan Free, pausas |
| `working/research/postgres-local.md` | reference | on-demand | Nota de área: Postgres en Docker, extracción por `updated_at`, coexistencia con Astro/Marquez/OpenMetadata |
| `working/research/landing-s3.md` | reference | on-demand | Nota de área: bucket y claves de `landing/`, lifecycle de 30 días frente al histórico, versioning, cifrado, coste S3 |
| `working/research/ci-permissions.md` | reference | on-demand | Nota de área: `ci-plan`/`ci-apply`/`ci-boundary` hoy, permisos que piden los recursos nuevos, riesgo de PassRole/CreateRole |
