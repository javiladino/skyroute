# reppit-orchestration — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

¿Cómo se ejecutan las etapas RePPIT con `session-orchestration`? El orquestador (la sesión principal) delega cada stage file a un subagente con escritura y verifica solo estructura y criterios; los revisores devuelven hallazgos que van a un subagente de corrección. El topic reescribe las reglas de escritura y de roles de subagentes, crea los agentes `stage-author` y `executor`, y ajusta permisos para subagentes en segundo plano.

## Rulings

- **Design write ownership (javiladino, 2026-11-12 18:00):** Verdict: per project CONTEXT Conventions ("Design write ownership"). Topic detail: la excepción de `## Decision` es deliberada; el texto es del owner y relanzar al autor solo para pegarlo no aporta nada.
- **Subagent roles (javiladino, 2026-11-12 18:00):** Verdict: per project CONTEXT Conventions ("Subagent roles"). Topic detail: los roles se cubren con `stage-author` (autor de stage files) y `executor` (implementación, tests y comandos que el revisor marque "no comprobado").
- **Skills location (javiladino, 2026-11-12 18:00):** Verdict: per project CONTEXT Conventions ("Skills location").
- **Simple shell commands (javiladino, 2026-11-12 18:00):** Verdict: per project CONTEXT Conventions ("Simple shell commands").
- **Reviewer sin Bash (javiladino, 2026-11-12 18:00):** `adversarial-reviewer` sigue con solo Read, Grep y Glob. Lo que su informe marque "no comprobado" lo ejecuta un `executor` que el orquestador lanza con los comandos exactos; sus resultados vuelven al orquestador como evidencia, no como veredicto. Sustituye a la versión de `agent-workflow`.
- **Verification ownership (javiladino, 2026-11-12 20:00):** Verdict: per project CONTEXT Conventions ("Verification ownership"). Topic detail: el owner eligió la opción (b) de las tres que estaban en README § Open decisions.
- **Implementer con nombre (javiladino, 2026-11-12 18:00):** `AGENTS.md` nombra a `executor` como implementer de `reppit-implement`.
- **Modelo de los agentes (javiladino, 2026-11-12 20:00):** los agentes de `.claude/agents/` usan `model: inherit`; el modelo de cada subagente lo fija el prompt de cada sesión (contrato 4 de `session-orchestration`).

## Journal (newest first)

**2026-11-12 (sesión corta):** Nueva Convention "Verification ownership" (opción b del owner); fuera de Open decisions y de Problemas conocidos. Revertida "Modelo de los agentes": los 9 agentes vuelven a `model: inherit`. Búsqueda de "Single design writer" y "Read-only subagents": cero apariciones en CONTEXT, AGENTS, CLAUDE y agentes. Prueba de `stage-author` en segundo plano no ejecutada: `Agent type 'stage-author' not found` (agentes no cargados en esta sesión); queda pendiente para una sesión nueva, por eso el topic sigue abierto. Close-out: design_check 0 FAIL; Active Context al día; README coincide; 1 Convention y 2 rulings del topic, con scope test.

**2026-11-12:** Sesión de mantenimiento. Topic abierto (decisión del owner: topic nuevo, no reabrir `agent-workflow`). Reescritas dos Conventions (Single design writer → Design write ownership, Read-only subagents → Subagent roles) y añadidas Skills location y Simple shell commands, con búsqueda de las redacciones antiguas. Creados `stage-author` y `executor`; `infra-lead` pasa a orquestador; todos los agentes a Sonnet 5.5. Verificada en la doc oficial la sintaxis de WebSearch, WebFetch por dominio y Edit por ruta; añadidos los allow. `AGENTS.md` y `CLAUDE.md` con nombres de Convention. Cerrado `platform-blueprint`. Queda abierto el conflicto de verificación (README Open decisions). Close-out: design_check 0 FAIL; Active Context al día; README coincide; 4 Conventions y 3 rulings del topic, todas con scope test.

## Document map

Rutas relativas a la raíz del repo; los archivos viven fuera de `docs/design/`.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `/.claude/agents/infra-lead.md` | deliverable | on-demand | Orquestador de infraestructura (contrato de `session-orchestration`) |
| `/.claude/agents/stage-author.md` | deliverable | on-demand | Autor de stage files (Read, Grep, Glob, Edit, Write, WebSearch, WebFetch) |
| `/.claude/agents/executor.md` | deliverable | on-demand | Implementer, tests y comandos "no comprobado" (más Bash, bajo el Apply gate) |
| `/.claude/agents/adversarial-reviewer.md` | deliverable | on-demand | Revisor de solo lectura; actualizado a la nueva regla del revisor |
| `/.claude/settings.json` | deliverable | on-demand | Allow de WebSearch, WebFetch por dominio, Edit por ruta y comandos de test |
| `/AGENTS.md` | deliverable | on-demand | 15 nombres de Convention y `executor` como implementer |
| `/CLAUDE.md` | deliverable | on-demand | Uso de `session-orchestration` y agentes, solo con nombres de Convention |

## Provenance

Viene de `agent-workflow` (cerrado el 2026-11-12). Hereda y sustituye sus rulings "Single design writer", "Read-only subagents", "Reviewer sin Bash" y "Sin implementer con nombre"; las de `agent-workflow` quedan como referencias a este topic.
