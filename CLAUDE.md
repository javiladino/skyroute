@AGENTS.md

# Específico de Claude Code

## Skills

- Las skills del proyecto están donde fija la Convention "Skills location". Invócalas con la herramienta Skill por su nombre (`design-memory`, `reppit-research`, …) o cuando el owner escriba `/<nombre>`.
- Carga `design-memory` antes de leer o escribir en `docs/design/`, `session-orchestration` cuando ejecutes etapas RePPIT, y la skill `reppit-*` de la etapa en curso.

## Agentes

- Los agentes del proyecto están en `.claude/agents/`. Para topics de infraestructura, arranca la sesión con `claude --agent infra-lead`.
- La sesión principal es el orquestador: lanza los subagentes con la herramienta Agent y revisa lo que devuelven. Qué escribe cada uno lo fijan las Conventions "Design write ownership" y "Subagent roles".
- Los subagentes no lanzan otros: ningún agente de `.claude/agents/` salvo `infra-lead` tiene la herramienta Agent, y `.claude/settings.json` fija `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`. Si un subagente necesita más trabajo delegado, lo devuelve al orquestador.
- Shell según la Convention "Simple shell commands"; cítala en cada brief.
