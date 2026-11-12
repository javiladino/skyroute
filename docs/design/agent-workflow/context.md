# agent-workflow — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

¿Cómo trabajan los agentes en este repo? El topic cubre los archivos raíz (`AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore`), escritos en la sesión 2, y los agentes de `.claude/agents/` y los hooks, que van en la sesión 3. Las reglas de proyecto que introduce viven en `CONTEXT.md` § Conventions.

## Rulings

- **Single design writer (javiladino, 2026-11-12 12:00):** Verdict: per project CONTEXT Conventions ("Single design writer").
- **Read-only subagents (javiladino, 2026-11-12 12:00):** Verdict: per project CONTEXT Conventions ("Read-only subagents"). Topic detail: el owner eligió la variante con excepción para los implementers de `reppit-implement`, en vez de prohibirlos.
- **AGENTS.md budget (javiladino, 2026-11-12 12:00):** `AGENTS.md` cabe en 150 líneas como máximo, en imperativo, y nombra cada Convention sin su veredicto. `CLAUDE.md` importa `@AGENTS.md` y añade solo lo específico de Claude Code.
- **Handoffs:** sin ruling propia. Es regla de la skill `design-memory` y `AGENTS.md` la cita como tal.

## Journal (newest first)

**2026-11-12:** Sesión 2. Scaffold del topic. Dos Conventions nuevas aprobadas (Single design writer, Read-only subagents) y una ruling del topic (AGENTS.md budget). Escritos `AGENTS.md` (120 líneas), `CLAUDE.md`, `README.md` raíz y `.gitignore`. Sigue abierto: `.claude/agents/` (incluido `adversarial-reviewer`) y hooks en la sesión 3. Close-out: design_check 0 FAIL; Active Context al día; README coincide; 3 rulings, 2 de proyecto en Conventions y 1 en el topic.

## Document map

Los archivos raíz están fuera de `docs/design/`; sus rutas son relativas a la raíz del repo.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `/AGENTS.md` | deliverable | on-demand | Instrucciones para agentes: mapa del repo, raíz de diseño, carga L0→L3, RePPIT, cierre de sesión, nombres de las Conventions |
| `/CLAUDE.md` | deliverable | on-demand | `@AGENTS.md` y lo específico de Claude Code (skills, agente principal y subagentes) |
| `/README.md` | deliverable | on-demand | README para humanos: qué es, enlaces, estado, requisitos previstos |
| `/.gitignore` | deliverable | on-demand | Ignorados de Terraform, Python, dbt, Airflow, Spark, datos locales, secretos y Claude local; `docs/design/` se versiona entero |
