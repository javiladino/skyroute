# generator-landing — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 2 — Generador y landing (README § Fases): "Simulador OTA coherente, Lambda + EventBridge, Postgres local, archivos en `landing/`. Hecho cuando hay 6 meses de histórico y llegan micro-lotes nuevos." Qué simula el generador y qué entra en `landing/`: `platform-blueprint/current/project/README.md` § Fuentes simuladas. Restricciones: Conventions Region, IaC only, Apply gate, No hourly-billed resources, Medallion layers, Idempotency y Bootstrap identity; Ruling Foundations design (`foundations/context.md`). Hechos de partida: `ci-apply` hoy solo tiene permisos sobre el backend del state, y cualquier recurso de esta fase obliga a ampliarlos dentro de la boundary `ci-boundary`; la cuenta sigue en plan Free, que se cierra a los 6 meses o al agotar los créditos. Rama: `docs/generator-landing-plan`. Etapa en curso: Plan hecho y aprobado (Ruling Plan decisions); siguiente Implement.

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
  - Schedule (T13/T21): ENABLED en prod y DISABLED en dev, según una variable. Topes: concurrencia reservada de 1 (en suspenso hasta que AWS suba la cuota; ver Ruling Implement decisions), RetryPolicy acotada, logs con 14 días de retención y una alarma de Invocations que avisa por SNS al email.
  - Plan Free (T12/T14): la cuenta sigue en Free. Antes de Plan, el owner aporta la salida de `aws freetier get-account-plan-state` y `aws budgets describe-budget`. Region se prueba con el primer apply a dev.

- **Propose decisions (javiladino, 2026-11-13 23:00):** Precisan el Ruling Research decisions; la discusión está en `working/proposal.md`.
  - Lock (precisa "Plan en PR"): `-lock=false` es obligatorio en `ci-plan`, y `ci-plan` pierde `PutObject`/`DeleteObject` sobre el `.tflock`.
  - Boundary (precisa "Boundary"): hay una boundary de workload por entorno (`workload-boundary-dev`, `workload-boundary-prod`) con ARN `skyroute-<env>-*`, y cada `ci-apply-<env>` solo puede crear o adjuntar la de su entorno.
  - Propuesta elegida: la Propuesta 1 (un módulo `modules/generator-landing`, zip con stdlib, arm64, roles `ci-apply-dev`/`ci-apply-prod` en archivos separados). Plan parte de ella.

- **Plan decisions (javiladino, 2026-11-13):** El owner aceptó todas las opciones por defecto de `working/plan.md` § Future Considerations y dio el visto bueno al plan.
  - Transición: los roles nuevos se crean antes de destruir `ci-apply`, en dos re-applies del owner (Fases 5 y 8). Solo hay ventana sin rol de apply en la vuelta atrás.
  - Alcance: solo lo de la Propuesta 1 (clickstream en `landing/` y Reservas en Postgres local). Las otras fuentes quedan fuera (OQ8).
  - OQ6: `ci-boundary` común, ampliada con los ARN de los dos entornos.
  - OQ10: `ci-plan` recibe `lambda:GetFunction`, solo sobre `function:skyroute-*-generator`.
  - OQ11: `aws_s3_account_public_access_block` en `bootstrap/`.
  - OQ1/OQ4: generador solo con stdlib, con duplicados y tardíos sembrados por la semilla.
  - OQ2: tramos de 1 día con `backfill_timeout` de 300 s.
  - OQ3: la alarma salta con más de 120 Invocations en 1 h.
  - OQ5: `ALARM_EMAIL` como variable de repositorio.
  - OQ7: SQL generado con stdlib y cargado con `psql` dentro del contenedor.
  - OQ9: D es la fecha del primer slot del schedule de prod, que el owner registra tras la Fase 9.
  - PC2: slots UTC `00`..`95`.
  - Checks: PC6 (cuota de concurrencia) la aporta el owner antes de la Fase 9. PC1 y PC5 se comprueban en el primer apply a dev, y PC3 en la PR-T1.

- **Implement decisions (javiladino, 2026-11-14):** Enmiendan el Ruling Research decisions (línea Schedule) durante Implement.
  - Concurrencia (PC6): la cuota "Concurrent executions" (L-B99A9384) de la cuenta en eu-west-3 es 10, y AWS exige dejar 10 sin reservar. Opción C: la Fase 9 se despliega sin `reserved_concurrent_executions`. En paralelo, `bootstrap/` pide por Terraform (`aws_servicequotas_service_quota`) subir la cuota a 1.000, y el owner la aplica en un re-apply. Cuando AWS la apruebe, una PR vuelve a poner la concurrencia reservada de 1. Mientras tanto, los topes son el timeout, la RetryPolicy del Scheduler, la alarma de Invocations y la cuota de 10 de la cuenta. Un backfill puede solaparse con el schedule de prod; las escrituras son idempotentes.
  - `description` de `ci-boundary`: se conserva el texto original ("ci-plan, ci-apply"), porque cambiarla fuerza el replacement de la boundary (PR #13).

## Journal (newest first)

**2026-11-14 (Implement, Fases 1-8):** Cada fase de código la implementó un executor (Sonnet) y el orquestador volvió a ejecutar su verify.
- **PRs:** #7/#9 generador y Postgres (#7 se fusionó en la rama del plan y #9 lo recuperó en `main`), #8 `-lock=false`, #10 bootstrap, #11 workflow de apply, #12 retirada de `ci-apply` y #13 fix de la `description`.
- **Fase 4:** security-reviewer (Opus) dio "listo con fixes". El owner aceptó tres: el riesgo residual de `PutBucketPolicy`, quitar `UpdateAssumeRolePolicy` y denegar `sns:Subscribe` salvo `email`.
- **Fase 5 (owner):** 7/2/0. **Fase 6:** run 43574299596, con "No changes" en dev y en prod.
- **Fase 8 (owner):** el primer plan reemplazaba `ci-boundary` y no se aplicó. Tras la PR #13 dio 0/4/2 y T17 quedó cerrada.
- **PC6:** la cuota de Lambda es 10 (Ruling Implement decisions, opción C).
- **Estado:** en curso, la PR de la cuota (`lambda_quota.tf`). `plan.md` y `test.md` están actualizados.

Siguiente: re-apply de la cuota, Fase 9, Fase 10 y la PR-Q.

**2026-11-13 (Plan):** stage-author (Opus) escribió `working/plan.md`: 10 fases, con las 5, 8 y 10 a cargo del owner. Revisión en paralelo: adversarial-reviewer (Opus, NEEDS-REVISION, 13 hallazgos), security-reviewer (Opus, 11 hallazgos) y cost-guard (Sonnet, de 0,02 a 0,3 USD/mes). executor (Sonnet) comprobó con `gh api` que los environments `dev` y `prod` solo admiten despliegues desde `main` y tienen `can_admins_bypass: false`; el hallazgo high de seguridad no se sostiene. Un stage-author (Sonnet) aplicó los 28 hallazgos. El owner resolvió dos choques (transición y alcance), aceptó todas las opciones por defecto y aprobó el plan (Ruling Plan decisions). Desviación anotada: `aws:SourceArn` del Scheduler apunta al schedule group, como pide la guía de AWS. Triage: `plan.md`, `proposal.md` y `research.md` quedan en `working/`. Siguiente: Implement.

**2026-11-13 (Propose):** stage-author (Opus) escribió `working/proposal.md` con 3 propuestas. Revisión en paralelo: adversarial-reviewer (Opus, GO-WITH-FIXES, 13 hallazgos), security-reviewer (Opus, 18 hallazgos) y cost-guard (Sonnet, coste de 0,05 a 0,9 USD/mes y los topes de timeout y memoria de la Lambda). El owner resolvió dos puntos que tocaban el Ruling (Ruling Propose decisions: lock y boundary por entorno). Un stage-author (Sonnet) aplicó todo, y otro (Sonnet) arregló una fila de una tabla. El owner eligió la Propuesta 1; el orquestador la registró en `## Decision`. Triage: `proposal.md` y `research.md` quedan en `working/` como entrada de Plan. Pendiente para el cierre del ciclo: enmendar el Ruling Foundations design (de dos a tres roles de CI y las boundaries de workload). Siguiente: Plan.

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
| `working/plan.md` | draft | on-demand | Plan de la Fase 2 (Propuesta 1), aprobado: 10 fases (las 5, 8 y 10 las ejecuta el owner), Files Changed, checks TS-*, OQ1-OQ11 y PC1-PC7 resueltas en el Ruling Plan decisions |
| `working/proposal.md` | draft | on-demand | Propose de la Fase 2: 3 propuestas revisadas y corregidas, skips de checkov, recomendación; `## Decision`: Propuesta 1 |
| `working/research.md` | draft | on-demand | Research de la Fase 2: criterio C1-C6, hechos (a)/(b)/(c), secretos, PII, coste, 5 componentes, tensiones T1-T22, preguntas al owner, no verificado |
| `working/research/generator-data.md` | reference | on-demand | Nota de área: 5 fuentes, coherencia entre ids, determinismo por fecha lógica, volumen de 6 meses, librerías, BCE |
| `working/research/lambda-eventbridge.md` | reference | on-demand | Nota de área: Scheduler frente a reglas, runtime y empaquetado, logs, coste, plan Free, pausas |
| `working/research/postgres-local.md` | reference | on-demand | Nota de área: Postgres en Docker, extracción por `updated_at`, coexistencia con Astro/Marquez/OpenMetadata |
| `working/research/landing-s3.md` | reference | on-demand | Nota de área: bucket y claves de `landing/`, lifecycle de 30 días frente al histórico, versioning, cifrado, coste S3 |
| `working/research/ci-permissions.md` | reference | on-demand | Nota de área: `ci-plan`/`ci-apply`/`ci-boundary` hoy, permisos que piden los recursos nuevos, riesgo de PassRole/CreateRole |
