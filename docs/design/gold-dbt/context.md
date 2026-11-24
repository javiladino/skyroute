# gold-dbt — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 4 — Gold con dbt (README § Fases): "Staging, modelo dimensional, atribución en tres modelos, ROAS, funnel, RFM, tests, contratos, exposures, docs. Hecho cuando el glosario de KPIs coincide con el SQL." Entrada: las tablas Silver de `bronze-silver` (Fase 3) en `skyroute_dev_silver`, leídas en dev. Restricciones: Conventions Table format, Medallion layers, Compute split, Region, No hourly-billed resources, IaC only, Apply gate e Idempotency. Etapa en curso: Research (abierta el 2026-11-23 mientras `bronze-silver` espera su coste en Cost Explorer).

## Rulings

- **Research decisions (javiladino, 2026-11-23):** grill-me de las 10 preguntas de `working/research.md` § 8, una línea por decisión:
  - Gasto publicitario y canal → entran: seed dbt `campaigns.csv` (`campaign_id`, `channel`, `start_date`) y gasto diario del generador a `landing/ad_spend/`, llevado a Bronze y Silver con Spark como `fx` (ROAS es el KPI central; Compute split).
  - Recorridos multi-campaña → sí: 1–4 touchpoints con campaña propia, deterministas por fecha lógica, repartidos en los días previos; la `campaign_id` de la reserva es la del último touch (sin esto los tres modelos de atribución coinciden).
  - Ventana de atribución → 7 días hacia atrás; ingreso atribuido solo de reservas `confirmed` según `bookings_scd2` a la fecha lógica; relanzar un día lo recalcula (Idempotency).
  - Ruta y fecha de viaje → se añaden en el generador (`origin`, `destination`, `travel_date`) y viajan por Postgres, `bookings_history`, `landing/`, Bronze y Silver (Compute split).
  - Funnel → eventos nuevos `product_view` y `begin_checkout`, en secuencia `search` → `product_view` → `add_to_cart` → `begin_checkout` → `purchase` con abandono determinista.
  - Sesión en Gold → `sessions.session_key`; touchpoint = sesión con la campaña de su primer evento (unida en Gold desde `events`); los modelos de sesión recalculan D-4..D y la atribución lee D-7..D (Idempotency).
  - CRM y bajas → fuera de la Fase 4; el RFM usa el consentimiento de Silver; la CRM queda como deuda para la Fase 7.
  - Identidad de dbt → rol nuevo `skyroute-<env>-local-dbt` (MFA desde `aws login`, 1 h): Silver solo lectura, Gold lectura y escritura, Athena en `skyroute-<env>` (enmendada el 2026-11-23 en Plan: workgroup propio `skyroute-<env>-dbt`, ver Plan decisions). Una PR de `bootstrap/` (boundaries con `gold/`) va antes de la del módulo; base gold en Terraform.
  - dbt en CI → solo `dbt parse`/`dbt ls` (y lint) sin AWS; `dbt build` contra dev lo ejecuta el owner en local como evidencia; el slim CI contra dev queda como deuda.
  - Prod → Gold solo en dev durante la fase; `dbt build` en prod al cierre, tras regenerar su histórico. La infraestructura (base, rol, boundaries) se crea en los dos entornos.
  - Todos los cambios del generador entran en un único cambio y un único backfill del histórico.

- **Bronze rebuild exception (javiladino, 2026-11-23):** excepción de un solo uso a Medallion layers e Idempotency ("Bronze append-only"), que siguen en vigor: para el backfill único de la Fase 4 se permite `DROP TABLE … PURGE` de las tablas Bronze y Silver una vez en dev y una vez en prod al cierre de la fase, con lista cerrada de tablas, `--confirm-prod` y runbook. Ejecuta el DROP el rol `skyroute-<env>-local-data`; en prod se crea temporalmente (Ruling Plan decisions). Motivo: los `event_id` deterministas (`keys.py:40`) harían que reingerir sin borrar duplicara filas en Bronze y abortara `silver.events`.

- **Plan decisions (javiladino, 2026-11-23):** tras security-reviewer, cost-guard y adversarial-reviewer sobre `working/plan.md`:
  - Workgroup de dbt → propio `skyroute-<env>-dbt`, con el mismo corte de 100 MB y `enforce_workgroup_configuration = true`; `local-dbt` solo tiene Athena sobre ese ARN (enmienda la línea "Identidad de dbt").
  - Rebuild de prod → rol `skyroute-prod-local-data` temporal: una PR lo activa (`create_local_data_role = true`) y otra lo retira, ambas aplicadas por CI; `rebuild_tables` verifica la identidad con `sts`, exige escribir el nombre del entorno y tiene `--dry-run`.
  - Backfill → en Spark local (0 USD de cómputo; Ruling de la Fase 3: local a diario, Glue solo en demos); Glue solo para un día de demo. Tope de alarma de 1 USD para dev.
  - `ad_spend` → fuente diaria local como `bookings` y `fx`; no se toca la Lambda.
  - Enmienda del 2026-11-23 (Implement, antes de la fase 1): el schedule del generador de prod se pausa por IaC (`envs/prod/main.tf`, `schedule_enabled = false`, queda `DISABLED` sin destruirse) hasta el rebuild de prod de la fase 7, cuyo runbook lo reactiva. Sustituye, para la Fase 4, la decisión de `bronze-silver` de mantenerlo activo. La PR de la fase 1 no se fusiona hasta que la pausa esté aplicada en prod.

## Document map

| Documento | Ruta | Carga |
|-----------|------|-------|
| Research | `working/research.md` | always |
| Proposal (elegida P1) | `working/proposal.md` | always |
| Plan | `working/plan.md` | always |
| Test (por fase; 0a, 0b, 0c, 1 y 2 PASS) | `working/test.md` | always |
