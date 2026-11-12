# agent-workflow — Contexto

**Tracker:** ninguno
**Status:** Done · **Owner:** javiladino

## Orientación

¿Cómo trabajan los agentes en este repo? El topic cubrió los archivos raíz (`AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore`, sesión 2) y los agentes de `.claude/agents/`, los permisos de `.claude/settings.json` y los hooks (sesión 3). Cerrado. Las reglas de proyecto que introduce viven en `CONTEXT.md` § Conventions.

## Rulings

- **Single design writer (javiladino, 2026-11-12 12:00):** Superseded por la Convention "Design write ownership" (source `reppit-orchestration`).
- **Read-only subagents (javiladino, 2026-11-12 12:00):** Superseded por la Convention "Subagent roles" (source `reppit-orchestration`).
- **AGENTS.md budget (javiladino, 2026-11-12 12:00):** Verdict: per project CONTEXT Conventions ("AGENTS.md budget"). Promovida desde este topic en la sesión 3.
- **Git workflow (javiladino, 2026-11-12 15:00):** Verdict: per project CONTEXT Conventions ("Git workflow"). Antes estaba solo en `AGENTS.md` § Git.
- **Reviewer sin Bash (javiladino, 2026-11-12 15:00):** Movida a `reppit-orchestration/context.md` § Rulings, donde se actualizó.
- **Sin implementer con nombre (javiladino, 2026-11-12 15:00):** Superseded: `executor` es el implementer que nombra `AGENTS.md` (`reppit-orchestration/context.md` § Rulings).
- **Handoffs:** sin ruling propia. Es regla de la skill `design-memory` y `AGENTS.md` la cita como tal.

## Journal (newest first)

**2026-11-12 (sesión 3):** Promovida "AGENTS.md budget" y creada la Convention "Git workflow" (sección Git quitada de `AGENTS.md`). Leídas las skills: solo `adversarial-reviewer` se espera por nombre; `session-orchestration` choca con Single design writer y no se usará. Verificados en la doc oficial el formato de agentes, la anidación (permitida por defecto: se fija a 1), `--agent`, permissions y hooks. Creados 7 agentes, `.claude/settings.json` y el hook `terraform-fmt.sh`. Pruebas: `aws --version` denegado; Stop hook silencioso con 0 FAIL y bloqueante en una copia con un FAIL; fmt hook formatea un `.tf`. Topic cerrado. Close-out: design_check 0 FAIL; Active Context al día; README coincide; 4 rulings (2 de proyecto en Conventions, 2 del topic).

**2026-11-12:** Sesión 2. Scaffold del topic. Dos Conventions nuevas aprobadas (Single design writer, Read-only subagents) y una ruling del topic (AGENTS.md budget). Escritos `AGENTS.md` (120 líneas), `CLAUDE.md`, `README.md` raíz y `.gitignore`. Sigue abierto: `.claude/agents/` (incluido `adversarial-reviewer`) y hooks en la sesión 3. Close-out: design_check 0 FAIL; Active Context al día; README coincide; 3 rulings, 2 de proyecto en Conventions y 1 en el topic.

## Document map

Los archivos raíz están fuera de `docs/design/`; sus rutas son relativas a la raíz del repo.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `/AGENTS.md` | deliverable | on-demand | Instrucciones para agentes: mapa del repo, raíz de diseño, carga L0→L3, RePPIT, cierre de sesión, nombres de las Conventions |
| `/CLAUDE.md` | deliverable | on-demand | `@AGENTS.md` y lo específico de Claude Code (skills, agente principal y subagentes) |
| `/README.md` | deliverable | on-demand | README para humanos: qué es, enlaces, estado, requisitos previstos |
| `/.gitignore` | deliverable | on-demand | Ignorados de Terraform, Python, dbt, Airflow, Spark, datos locales, secretos y Claude local; `docs/design/` se versiona entero |
| `/.claude/agents/infra-lead.md` | deliverable | on-demand | Agente principal de infraestructura (`claude --agent infra-lead`); coordina subagentes y escribe `docs/design/` |
| `/.claude/agents/adversarial-reviewer.md` | deliverable | on-demand | Revisor adversarial de solo lectura (Read, Grep, Glob) para reppit-research, reppit-propose y reppit-test |
| `/.claude/agents/aws-researcher.md` | deliverable | on-demand | Subagente de solo lectura: servicios AWS |
| `/.claude/agents/terraform-researcher.md` | deliverable | on-demand | Subagente de solo lectura: Terraform y provider AWS |
| `/.claude/agents/security-reviewer.md` | deliverable | on-demand | Subagente de solo lectura: IAM, cifrado, OIDC, secretos, PII |
| `/.claude/agents/cost-guard.md` | deliverable | on-demand | Subagente de solo lectura: coste AWS |
| `/.claude/agents/cicd-researcher.md` | deliverable | on-demand | Subagente de solo lectura: GitHub Actions y OIDC |
| `/.claude/settings.json` | deliverable | on-demand | Permisos deny/ask/allow (Apply gate, Git workflow), profundidad de subagentes 1, hooks Stop y PostToolUse |
| `/.claude/hooks/terraform-fmt.sh` | deliverable | on-demand | Hook PostToolUse: `terraform fmt` sobre el `.tf` editado |
