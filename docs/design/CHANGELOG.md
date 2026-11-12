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
