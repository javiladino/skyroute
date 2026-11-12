# foundations — Contexto

**Tracker:** ninguno
**Status:** In progress · **Owner:** javiladino

## Orientación

Fase 1 — Fundaciones (README § Fases): cuenta AWS con MFA y usuario no root, presupuesto, repo, bootstrap de Terraform (state remoto, rol OIDC para GitHub Actions) y CI básica. Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica. Restricciones: Conventions Region, IaC only, Apply gate y No hourly-billed resources. Decisión abierta que toca a esta fase: plan de cuenta AWS (README § Open decisions). Siguiente etapa: Plan (`reppit-plan`) con `infra-lead` como orquestador; Research en `working/research.md`, propuesta elegida en `working/proposal.md` § Decision.

## Rulings

- **Foundations design (javiladino, 2026-11-12 18:00):** Proposal 1 con dos roles de CI: state con SSE-S3 (sin KMS), cuenta AWS en plan Free (Paid aplazado), owner con IAM user y MFA (sin Organizations ni Identity Center), roles `ci-plan` (`sub` `pull_request`) y `ci-apply` (`sub` `environment:dev`/`environment:prod`, environments solo desde `main`). Discusión: `working/proposal.md` § Decision.

## Journal (newest first)

**2026-11-12 (Propose):** Sesión `infra-lead`. Intake con grill-me: cuenta en Free y abierta a Paid; Identity Center con Organizations como una opción. `working/proposal.md` (stage-author, Opus) con tres propuestas; revisión en paralelo (adversarial-reviewer GO-WITH-FIXES y security-reviewer, Opus; cost-guard, Sonnet) y corrección de todos los hallazgos (stage-author, Sonnet). El principal: environments solo desde `main` para que una PR no asuma el rol de apply. Recomendada P3; el owner eligió P1 con dos roles (Ruling Foundations design). Pendiente para Plan: credenciales del primer apply del bootstrap, días de lifecycle de versiones no actuales, IDs numéricos para el `sub`, permisos de Budgets y `envs/*`. Siguiente: Plan (`reppit-plan`).

**2026-11-12 (Research):** Sesión `infra-lead` en rama `infra-foundations`. Cuatro notas de área (stage-author, Sonnet) consolidadas en `working/research.md` (stage-author, Opus); una ronda de revisión (adversarial-reviewer GO-WITH-FIXES, security-reviewer, cost-guard) y corrección (stage-author, Sonnet) de 22 hallazgos. Siete tensiones con Conventions en § 4.1 y 17 ítems no verificados en § 3.5, ambos sin resolver. Gate-check de estructura: siete secciones presentes. Siguiente: Propose (`reppit-propose`), tras el visto bueno del owner. Después, datos del owner (repo creado 2026-11-12 y público; cuenta AWS existente en eu-west-3) registrados en `research.md` por stage-author (Sonnet): tensiones 1 y 3 resueltas por dato del owner; § 3.5 baja a 15 ítems. Ronda `grill-me` con el owner: Region → servicios globales (IAM, Budgets, Organizations) exentos, provider siempre en eu-west-3; Bootstrap del state → excepción única a Apply gate (el owner aplica `infra/terraform/bootstrap/` una vez en local y migra el state; crea budget, bucket, OIDC y rol de CI); Plan en PR → GitHub Actions no es un agente y publica `plan` en cada PR. Escritas en CONTEXT.md § Conventions (Region, Apply gate). Con ello quedan resueltas las tensiones 2, 4, 5 y 7 de `research.md` § 4.1; la 6 (KMS) va a Propose. Reparto de roles plan/apply: diseño, a Propose.

**2026-11-12:** Topic abierto (scaffold). Sin stage files.

## Document map

Rutas relativas a esta carpeta.

| File | Role | Load | Qué contiene |
|------|------|------|--------------|
| `working/research.md` | draft | on-demand | Stage file Research: estado del repo, hechos externos de las cuatro áreas, tensiones con Conventions, no verificado |
| `working/proposal.md` | draft | on-demand | Stage file Propose: tres propuestas revisadas, tabla de recomendación y § Decision (P1 con dos roles) |
| `working/research/terraform-layout.md` | draft | on-demand | Nota de área: layout bootstrap/modules/envs, backend S3 `use_lockfile`, bootstrap del bucket, versiones |
| `working/research/cicd-oidc.md` | draft | on-demand | Nota de área: OIDC GitHub→AWS, formatos `sub`, plan en PR y apply al fusionar, environments |
| `working/research/iam-security.md` | draft | on-demand | Nota de área: acceso del owner (IAM user / Identity Center), rol de CI, protección del bucket de state |
| `working/research/account-cost.md` | draft | on-demand | Nota de área: plan Free/Paid, servicios por región y plan, Budgets, precios eu-west-3 |
