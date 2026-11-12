@AGENTS.md

# Específico de Claude Code

## Skills

- Las skills del proyecto están en `.claude/skills/`. Invócalas con la herramienta Skill por su nombre (`design-memory`, `reppit-research`, …) o cuando el owner escriba `/<nombre>`.
- Carga `design-memory` antes de leer o escribir en `docs/design/`, y la skill `reppit-*` de la etapa en curso antes de escribir su stage file.

## Agente principal y subagentes

- El agente principal (la sesión con la que habla el owner) coordina: lanza los subagentes con la herramienta Agent, revisa lo que devuelven y es el único que escribe en `docs/design/` (Convention "Single design writer").
- Lo que puede editar cada subagente lo fija la Convention "Read-only subagents".
- Los subagentes no pueden lanzar otros subagentes. Si un subagente necesita más trabajo delegado, lo devuelve al agente principal, que decide.
- No lances subagentes si la tarea cabe en la sesión principal.
