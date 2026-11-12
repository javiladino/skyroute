# Skyroute Marketing Lakehouse Changelog

Newest first. One `##` heading per day with activity. Write outcomes, not implementation steps. This file is appended to, never rewritten, and is not loaded by default.

## 2026-11-12

### platform-blueprint — Sesión 1: base de la memoria de diseño
- Scaffold de `docs/design/` (CONTEXT, README, CHANGELOG) y del topic `platform-blueprint`; documentación en español.
- Nueve Conventions de proyecto extraídas del blueprint y aprobadas por el owner (Table format, Medallion layers, Compute split, Orchestration runtime, Region, No hourly-billed resources, IaC only, Apply gate, Idempotency). Apply gate: el owner corre `terraform plan` él mismo.
- README de diseño con las 8 fases del blueprint (sin topics) y 5 decisiones abiertas.
- Deliverable `platform-blueprint/current/project/README.md` (descripción de producto).
- Quitados del índice los `.DS_Store` versionados; `.gitignore` queda para la sesión 2.
- Falta `.claude/agents/adversarial-reviewer.md` (lo necesita reppit-propose); se crea en la sesión 2.

### Files (skyroute, rama main)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md` (new)
- `docs/design/platform-blueprint/context.md`, `current/project/README.md` (new)
- `.DS_Store` ×5 (deleted)

### agent-workflow — Sesión 2: archivos raíz del repo
- Nuevo topic `agent-workflow` (cubre esta sesión y la siguiente).
- Dos Conventions nuevas aprobadas por el owner: Single design writer y Read-only subagents (con excepción para los implementers de `reppit-implement`). Ruling del topic: AGENTS.md budget. Los traspasos en el chat se quedan como regla de la skill `design-memory`, sin ruling.
- Escritos `AGENTS.md` (120 líneas), `CLAUDE.md`, `README.md` raíz y `.gitignore`; `docs/design/` sigue versionado entero.

### Files (skyroute, rama main, sin commit)
- `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore` (new)
- `docs/design/agent-workflow/context.md` (new)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md` (modified)

### agent-workflow — Sesión 3: agentes, permisos y hooks; topic cerrado
- Promoted ruling "AGENTS.md budget" from agent-workflow to Conventions.
- Nueva Convention "Git workflow" (antes solo en `AGENTS.md` § Git, que se quita).
- Agentes en `.claude/agents/`: `infra-lead` (sesión principal), `adversarial-reviewer` (sin Bash) y cinco subagentes de solo lectura (`aws-researcher`, `terraform-researcher`, `security-reviewer`, `cost-guard`, `cicd-researcher`). Sin implementer con nombre: `reppit-implement` no lo espera.
- La doc oficial dice que los subagentes pueden anidar por defecto (hasta 3 niveles): se fija `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` y ningún subagente tiene la herramienta Agent; `CLAUDE.md` corregido.
- `.claude/settings.json`: deny de `terraform plan/apply/destroy/import/state` (también con `-chdir`), `aws` y lectura de `.env*` y `*.tfvars`; ask para commit/push; allow de fmt/validate/tflint/checkov, git de lectura y `design_check.py`. Hooks Stop (`design-check-on-stop.sh`) y PostToolUse (`terraform-fmt.sh`).
- `session-orchestration` no se usa en el proyecto (choca con Single design writer).
- Pruebas: `aws --version` denegado; Stop hook silencioso con 0 FAIL y bloqueante en una copia con un FAIL.

### Files (skyroute, rama main, sin commit)
- `.claude/agents/*.md` ×7, `.claude/settings.json`, `.claude/hooks/terraform-fmt.sh` (new)
- `AGENTS.md`, `CLAUDE.md` (modified)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `agent-workflow/context.md` (modified)

### reppit-orchestration — Adopción de session-orchestration para RePPIT
- Decisión del owner: las etapas RePPIT se ejecutan con `session-orchestration`. Va en el topic nuevo `reppit-orchestration`; `agent-workflow` sigue cerrado.
- Ruling reversal: "Single design writer" (solo el agente principal escribe en `docs/design/`) → "Design write ownership" (el orquestador escribe los archivos de proyecto, los context.md, `## Decision` y los movimientos entre carpetas; cada stage file tiene como autor al subagente de su brief).
- Ruling reversal: "Read-only subagents" (solo lectura salvo implementers) → "Subagent roles" (investigadores y revisores de solo lectura; autores y ejecutores escriben solo en las rutas de su brief; ninguno tiene Agent).
- Nuevas Conventions: "Skills location" y "Simple shell commands". `AGENTS.md` nombra 15 Conventions (120 líneas, dentro de AGENTS.md budget).
- Agentes: nuevos `stage-author` y `executor` (implementer de `reppit-implement`); `infra-lead` pasa al contrato de orquestador; "Reviewer sin Bash" actualizada (lo no comprobado lo ejecuta `executor`); todos los agentes en Sonnet 5.5.
- `settings.json`: allow de `WebSearch`, `WebFetch` por dominio de documentación oficial, `Edit(/docs/design/*/working/**)`, `pytest` y `ruff`. Los deny del Apply gate no cambian y tienen precedencia.
- Abierta: quién ejecuta la verificación (choque de `reppit-implement` y `reppit-test` con "Subagent roles").
- `platform-blueprint` cerrado.

### Files (skyroute, rama main, sin commit)
- `.claude/agents/stage-author.md`, `executor.md`, `docs/design/reppit-orchestration/context.md` (new)
- `.claude/agents/*.md` ×7, `.claude/settings.json`, `AGENTS.md`, `CLAUDE.md` (modified)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `agent-workflow/context.md`, `platform-blueprint/context.md` (modified)

### reppit-orchestration — Verificación y modelos
- Decisión del owner (opción b): nueva Convention "Verification ownership"; fila retirada de Open decisions (Accepted).
- Ruling reversal "Modelo de los agentes": antes todos los agentes con `model: sonnet` (Sonnet 5.5); ahora `model: inherit` y el modelo se fija en cada prompt de sesión (contrato 4 de `session-orchestration`).
- `AGENTS.md` nombra 16 Conventions (121 líneas).
- Prueba de `stage-author` en segundo plano no ejecutada: los agentes de `.claude/agents/` no están cargados en esta sesión (`Agent type 'stage-author' not found`). Pendiente en una sesión nueva; `reppit-orchestration` sigue abierto.

### Files (skyroute, rama main, sin commit)
- `.claude/agents/*.md` ×9, `AGENTS.md` (modified)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `reppit-orchestration/context.md` (modified)

### reppit-orchestration — Smoke test y cierre del topic
- Prueba superada: `stage-author` (Sonnet), lanzado en segundo plano, escribió `working/smoke.md` con Write sin bloqueo de permisos; archivo borrado tras comprobarlo.
- Retirado el problema conocido "agentes no cargados en la sesión que los creó". Topic `reppit-orchestration` cerrado (Done).

### Files (skyroute, rama main, sin commit)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md`, `reppit-orchestration/context.md` (modified)

### foundations — Topic abierto (Fase 1)
- Scaffold de `foundations/context.md`; Fase 1 pasa a In progress en README. Siguiente: Research.

### Files (skyroute, rama main, sin commit)
- `docs/design/foundations/context.md` (new)
- `docs/design/CONTEXT.md`, `README.md`, `CHANGELOG.md` (modified)
