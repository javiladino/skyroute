---
type: Plan
---

# foundations: Fase 1 (bootstrap, state remoto, OIDC y CI básica) Design Document

> **Fuente de la elección:** `working/proposal.md` § Decision (Proposal 1 con dos roles de CI) y Ruling "Foundations design" en `foundations/context.md`.
> **Date:** 2026-11-12 (revisado 2026-11-13: ronda de review y datos del owner)

## Current Context

- No existe `infra/`, ningún `*.tf` ni `.github/workflows/` (research § 3.0, Glob 2026-11-12); las rutas solo figuran como previstas en `AGENTS.md:23` y `AGENTS.md:31`. Todo lo de este plan es nuevo salvo `AGENTS.md`.
- `docs/design/CONTEXT.md:29`: no hay código, Terraform ni recursos AWS. La cuenta existe en eu-west-3, en plan Free (research § 1, F1–F3).
- El eje común es el bucket de state con `use_lockfile = true` (lock `.tflock` junto a la clave, DynamoDB deprecado [TL 3, TL 6]); sus permisos los necesitan los roles de CI, cuya trust policy depende del formato `sub` inmutable del token OIDC (research § 2, § 3.2).
- El repo `javiladino/skyroute` es público y se creó el 2026-11-12, así que emite `sub` `repo:javiladino@97758532/skyroute@1455233709:...` (owner 97758532, repo 1455233709; dato del owner vía `gh api repos/javiladino/skyroute`).
- `AGENTS.md:100-105` (§ Comandos de build y test) es todo TODO; la línea 103 ("Terraform estático") se rellena en este plan.
- `.gitignore` ya cubre Terraform: `.terraform/` (línea 5), `*.tfstate` y `*.tfstate.*` (6-7), `*.tfvars` (8) y `!*.tfvars.example` (9). No necesita cambios (Glob/Read 2026-11-13).
- Datos del owner (2026-11-13): IAM user `skyroute-dev`, grupo `admins` (su única policy es `AdministratorAccess`, `arn:aws:iam::aws:policy/AdministratorAccess`), consola + MFA, sin access keys, CLI con `aws login`. Existe un bucket de state manual en `eu-north-1` (get-bucket-location del owner): no se adopta; el bootstrap crea uno nuevo en eu-west-3, `skyroute-tfstate-437266392155-eu-west-3` (nombre confirmado por el owner).
- Los environments de GitHub `dev` y `prod` ya existen en el repo (creados por el owner en la UI, 2026-11-13). No son recursos AWS: quedan fuera de IaC only. Falta su configuración (ver Design Decision 7).
- checkov no está instalado localmente; el owner quiere que lo ejecute CI (2026-11-13).

## Requirements

### Functional Requirements

- Criterio de Fase 1 (`docs/design/README.md:15`): "Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica."
- `infra/terraform/bootstrap/` crea: `aws_budgets_budget` 10 USD con avisos ACTUAL 50/80/100 % y `cost_types { include_credit = false, include_refund = false }` explícitos; bucket de state NUEVO en eu-west-3 (SSE-S3, Versioning, Block Public Access, deny sin `aws:SecureTransport`, Object Ownership enforced, `prevent_destroy`, `force_destroy = false`, lifecycle con `noncurrent_version_expiration` = 90 días); proveedor OIDC; roles `ci-plan` y `ci-apply`; y adopta por bloques `import` el IAM user `skyroute-dev`, el grupo `admins`, su attachment de policy y la membresía (4 bloques).
- `infra/terraform/envs/dev` y `envs/prod`: `backend "s3"` con `use_lockfile = true`, `region = "eu-west-3"` y claves `envs/dev/terraform.tfstate` y `envs/prod/terraform.tfstate`. El bootstrap usa `bootstrap/terraform.tfstate`.
- Un runbook del owner, `docs/runbooks/foundations-bootstrap.md`, cubre los pasos que ningún agente ejecuta (Apply gate).
- `terraform-plan.yml` en `pull_request` comenta el plan en la PR y ejecuta checkov en un job de checks estáticos; `terraform-apply.yml` en `push` a `main` aplica `dev` y, con aprobación, `prod`.
- Environments `dev` y `prod` (ya creados por el owner en la UI) con deployment branches solo `main` en ambos; `prod` con revisor requerido, "Prevent self-review" desactivado y bypass de administradores desactivado; `main` con branch protection y PR requerida. Los configura el owner en la UI.

### Non-Functional Requirements

- Coste nuevo 0: SSE-S3 sin coste [IAM 15], Budgets sin acciones 0 USD [AC 13], IAM/STS sin cargo [IAM 7]. Convention No hourly-billed resources.
- Convention Region: todo recurso regional y el state en eu-west-3; provider siempre `region = "eu-west-3"`. Budgets e IAM son globales y exentos.
- Convention IaC only y Convention Apply gate: se aplican tal como están en `docs/design/CONTEXT.md` § Conventions; este plan no las reabre.
- Seguridad: una PR no puede aplicar (trust de `ci-plan` solo `pull_request`, sin escritura sobre el state salvo el `.tflock`); repo público, así que nada secreto en comentarios ni artifacts. El email del budget nunca se versiona: solo en `infra/terraform/bootstrap/terraform.tfvars` (gitignored).

## Design Decisions

### 1. Cifrado del state: SSE-S3
Se usa SSE-S3 porque:
- Coste 0 y por defecto desde 2023-01-05 [IAM 15]; sin dudas frente a No hourly-billed resources.
- Alternativa descartada: SSE-KMS con clave de cliente, ~1 USD/mes prorrateado por hora y facturado aunque esté inactiva [IAM 16] (Proposal 2, OQ P2-1).
- Trade-off: sin control de acceso por clave sobre un state en texto plano (research § 3.3).

### 2. Cuenta en Free
Se queda en Free porque el owner quiere aplazar Paid ("Es un ejercicio educativo…", § Decision).
- Alternativas: Paid (P3) o Paid forzado por Organizations (P2).
- Trade-off: Free termina a los 6 meses o al agotar créditos [AC 2, AC 3]; fila abierta `docs/design/README.md:51`.

### 3. Acceso del owner: IAM user con MFA, creado en consola e importado
Dato del owner (2026-11-13): IAM user `skyroute-dev` en el grupo `admins`, con consola + MFA y SIN access keys; la CLI se autentica con `aws login`. El bootstrap los adopta con cuatro bloques `import`: `aws_iam_user.owner` (id `skyroute-dev`), `aws_iam_group.admins` (id `admins`), `aws_iam_group_policy_attachment` y `aws_iam_user_group_membership`. El grupo tiene `AdministratorAccess` (`arn:aws:iam::aws:policy/AdministratorAccess`) como única policy: el `aws_iam_group_policy_attachment` se declara con `group = "admins"` y esa `policy_arn`. Los IDs exactos de import del attachment y de la membresía se confirman en Implement (formato del ID del attachment, `<grupo>/<policy-arn>`: no comprobado). El owner ejecuta `plan` tras los imports y espera 0 cambios sobre esos recursos; el root nunca tiene access keys [IAM 1, IAM 2].
- Encaja con la excepción que fijan las Conventions IaC only y Apply gate para los recursos previos al bootstrap.
- Alternativa descartada: Identity Center (fuerza Organizations y Paid [IAM 4, AC 7]).
- Trade-off: no hay credenciales de larga duración que robar ni rotar (sin access keys); el coste es que la sesión de `aws login` caduca y hay que repetirla. Que Terraform use esas credenciales directamente: no comprobado; se verifica en Implement/runbook.

### 4. Dos roles de CI con `sub` exactos
`ci-plan` y `ci-apply`, ambos con `aud = sts.amazonaws.com` y solo `StringEquals`:
- `ci-plan`: `sub` = `repo:javiladino@97758532/skyroute@1455233709:pull_request`. Permisos: `s3:ListBucket` en el bucket; `s3:GetObject` solo en los ARN exactos `envs/dev/terraform.tfstate` y `envs/prod/terraform.tfstate`; `s3:GetObject`/`s3:PutObject`/`s3:DeleteObject` solo en los ARN exactos de sus `.tflock` [TL 5, IAM 11]. Nunca la clave `bootstrap/`. Lectura de recursos de `envs/*` pendiente (Future Considerations).
- `ci-apply`: `sub` en `repo:javiladino@97758532/skyroute@1455233709:environment:dev` y `repo:javiladino@97758532/skyroute@1455233709:environment:prod` [CI 13]. Permisos: backend sobre las mismas dos claves y sus `.tflock` (nunca `bootstrap/`) [TL 5], más escritura de recursos de `envs/*` (pendiente).
- Ambas trust policies: `Principal.Federated` = ARN del proveedor OIDC, Action solo `sts:AssumeRoleWithWebIdentity`, y `aud` y `sub` en el mismo bloque `StringEquals`.
- Ambos roles con permissions boundary [IAM 12] y Deny explícito sobre: modificar los roles `ci-*`, el proveedor OIDC y la bucket policy del state; `iam:*` sobre `user/skyroute-dev` y `group/admins`; `iam:CreateRole` y `iam:PutRolePermissionsBoundary` sin la condición `iam:PermissionsBoundary`; `iam:DeleteRolePermissionsBoundary`; y sobre el bucket de state `s3:DeleteObjectVersion`, `s3:PutBucketVersioning`, `s3:PutBucketPublicAccessBlock`, `s3:PutLifecycleConfiguration`, `s3:PutBucketPolicy`. El mismo Deny de `iam:*` sobre user y grupo va en la boundary.
- Deny que protege la propia política `ci-boundary` (decisión del owner, 2026-11-13): `iam:CreatePolicyVersion`, `iam:SetDefaultPolicyVersion`, `iam:DeletePolicy` e `iam:DeletePolicyVersion` sobre el ARN de la política gestionada `ci-boundary`, en la boundary y en ambos roles (`ci-plan`, `ci-apply`): 3 apariciones de `iam:CreatePolicyVersion` (A4d). Sin él, un rol de CI podría reescribir su boundary.
- Condición de la boundary (elección del implementer, registrada 2026-11-13): `StringNotEquals` sobre `iam:PermissionsBoundary` = ARN de `ci-boundary` en los Deny de `iam:CreateRole` y `iam:PutRolePermissionsBoundary` (A4e).
- Comodines (decisión del owner, 2026-11-13): `Resource = "*"` solo en statements `Effect = "Deny"`; los Allow llevan ARN exactos, 0 `*` (A4, A4a).
- Ningún workflow toca `bootstrap/`: el bootstrap solo lo aplica el owner en local (Apply gate).
- Razón: cierra el hallazgo de severidad alta del rol único de P1 sin coste ni paso a Paid (§ Decision).
- Alternativa descartada: un rol `ci` con los tres `sub`; `plan -lock=false` sin escritura (pierde exclusión frente a un apply concurrente, inferencia de P2).
- La Convention Apply gate (actualizada 2026-11-13) habla de "los roles de CI" en plural y coincide con el Ruling "Foundations design"; sin conflicto.

### 5. Layout del bootstrap y backends
Root module `bootstrap/` con state local en el primer apply. Forma decidida: el agente NO crea el bloque backend de bootstrap; tras el primer apply el owner añade un `bootstrap/backend.tf` aparte (contenido en el runbook) y ejecuta `terraform init -migrate-state` [TL 9, TL 10]. Razón: con el backend presente desde el inicio, el primer `init` fallaría porque el bucket aún no existe. Consecuencia: en Implement `use_lockfile = true` aparece 2 veces (dev, prod); 3 tras el paso del owner. `envs/{dev,prod}` con backend S3 [TL 2, TL 3]. El bloque backend no admite variables [TL 7]: el nombre del bucket va como literal en los tres backends [TL 8]. Nombre confirmado por el owner: `skyroute-tfstate-437266392155-eu-west-3`.
- `.terraform.lock.hcl`: se versiona (lo genera `init`; fija hashes del provider para que CI y local usen el mismo binario). Por eso no va en `.gitignore`.

### 6. Lifecycle del bucket: 90 días
`noncurrent_version_expiration` = 90 días (decisión del owner), más `expired_object_delete_marker` y `abort_incomplete_multipart_upload`. La regla lleva `filter {}` (inferencia: el provider lo exige o avisa sin él; se confirma con `validate`). Evita crecimiento sin límite con Versioning [IAM 18].

### 7. Environments y revisor
`dev` y `prod` con deployment branches solo `main` (research § 3.2) para que un job de PR no emita `sub` `environment:*`; `prod` con revisor requerido (repo público, [CI 12]) y "Prevent self-review" desactivado (único owner: activado nadie podría aprobar). Decisión del owner (2026-11-13): los environments `dev` y `prod` ya existen, creados en la UI; no son recursos AWS, así que quedan fuera de IaC only y no se gestionan con el provider `github`. El owner sigue configurando en la UI: deployment branches solo `main` en ambos, revisor requerido en `prod`, bypass de administradores desactivado y branch protection de `main` con PR requerida. Son pasos del runbook y de la Fase 7; A10 los comprueba.

## Technical Design

### 1. Core Components

- `infra/terraform/bootstrap/`: root module único con provider `region = "eu-west-3"`; crea budget, bucket de state nuevo y sus controles, proveedor OIDC, `ci-plan`, `ci-apply`, boundary y Deny; importa user, grupo, attachment y membresía del owner.
- `infra/terraform/envs/dev/`, `envs/prod/`: root modules con solo `terraform`/`backend "s3"` y provider en esta fase (ningún recurso del lakehouse).
- Triggers sin filtros `paths` (decisión del owner, 2026-11-13): plan corre en cada PR y apply en cada push a `main`, para que la branch protection pueda exigir el check de plan. Hechos del implementador: actions fijadas por SHA (checkout v7.0.1, configure-aws-credentials v6.3.0, setup-terraform v4.0.1, github-script v9.0.0, setup-tflint v6.3.2, setup-python v7.1.0); terraform 1.17.1, tflint v0.65.0, checkov==3.4.5 vía pip.
- `.github/workflows/terraform-plan.yml`: `on: pull_request` (sin `paths`); `concurrency` por PR con cancelación de runs superados del mismo PR; job `plan` con matriz dev/prod y `pull-requests: write` en ese job (un job de comentario aparte exigiría `upload-artifact`, prohibido por A7); `permissions: {}` a nivel superior y por job `id-token: write, contents: read, pull-requests: write` [CI 7, CI 11]; `actions/checkout` con `persist-credentials: false`; asume `ci-plan`; `fmt -check`, `init`, `validate`, `plan -no-color` por entorno; sin `TF_LOG`; comentario vía `actions/github-script` o job summary si supera 65535 caracteres [CI 10]. No referencia `bootstrap/`. Incluye un job aparte `static-checks` con `permissions: contents: read` (sin `id-token`, sin credenciales AWS, sin `environment`) que ejecuta `checkov -d infra/terraform`; checkov se instala con `pip install` de una versión fijada en Implement sobre el Python del runner (así no se añade otra action; la alternativa, una action de checkov fijada por SHA, no se ha comprobado y no se usa por defecto).
- `.github/workflows/terraform-apply.yml`: `on: push` a `main` (sin `paths`); `permissions: {}` superior y permisos por job; `concurrency` con grupo `terraform-apply` y `cancel-in-progress: false` (sin cancelar runs en curso); `persist-credentials: false`; job `apply-dev` con `environment: dev`; job `apply-prod` con `environment: prod` (revisor requerido), ambos asumen `ci-apply`. No referencia `bootstrap/`.
- Errores esperados: IDs erróneos en el `sub` dan "Not authorized to perform sts:AssumeRoleWithWebIdentity" [CI 5].

### 2. Data Models

- `aws_budgets_budget`: `budget_type`, `time_unit`, `limit_amount` 10 USD; `cost_types { include_credit = false, include_refund = false }`; tres `notification` ACTUAL a 50, 80 y 100 % con `comparison_operator`, `threshold_type` y `subscriber_email_addresses` [AC 18]. Sin FORECASTED (no dispara en cuenta nueva, research § 3.4) y sin `aws_budgets_budget_action` (acciones con coste potencial). El presupuesto manual de 1 USD se queda hasta que exista el de Terraform; el owner lo borra tras verificarlo (runbook).
- Email del suscriptor: variable `sensitive = true` en `variables.tf`, valor solo en `infra/terraform/bootstrap/terraform.tfvars` (gitignored, `.gitignore:8`); se versiona `terraform.tfvars.example` con un placeholder. El email real no se escribe en ningún archivo versionado (repo público).
- Claves de state, cada una con su `<key>.tflock`: `bootstrap/terraform.tfstate`, `envs/dev/terraform.tfstate`, `envs/prod/terraform.tfstate`.
- IDs de GitHub confirmados (owner 97758532, repo 1455233709): cierran la pregunta abierta anterior.

### 3. Integration Points

Flujo (research § 5.1, § 5.2):
1. Owner (runbook): `aws login` con `skyroute-dev`; `terraform apply` en `bootstrap/` con state local (importa user, grupo, attachment y membresía; crea el bucket nuevo en eu-west-3); añade `bootstrap/backend.tf`; `terraform init -migrate-state`; verifica el budget de Terraform; borra el budget manual y el bucket manual de eu-north-1.
2. PR: GitHub Actions pide JWT (`sub` `pull_request`), asume `ci-plan`, `plan` y comenta.
3. Merge a `main`: job con `environment: dev` (`sub` `environment:dev`), asume `ci-apply`, `apply`; `prod` espera aprobación.

### 4. Files Changed

Total: 15 archivos que escribe el agente (14 nuevos, 1 modificado), más 4 que no escribe como autor: 3 `.terraform.lock.hcl` generados por `init` y `bootstrap/backend.tf` que añade el owner (19 en total). Los nombres de archivo dentro de cada root module se pueden ajustar en Implement sin cambiar el reparto.

- `infra/terraform/bootstrap/versions.tf` (NEW: does not exist yet. `required_version` y `required_providers` `hashicorp/aws`; provider `region = "eu-west-3"`; sin bloque backend)
- `infra/terraform/bootstrap/budget.tf` (NEW: does not exist yet. `aws_budgets_budget` 10 USD, `cost_types` con `include_credit = false` e `include_refund = false`, avisos ACTUAL 50/80/100 %)
- `infra/terraform/bootstrap/state_bucket.tf` (NEW: does not exist yet. bucket nuevo con `lifecycle { prevent_destroy = true }` y `force_destroy = false`, SSE-S3, Versioning, Public Access Block, Ownership Controls, bucket policy con deny `aws:SecureTransport = "false"` y deny `s3:DeleteBucket`, lifecycle 90 días con `filter {}`, `expired_object_delete_marker` y multipart)
- `infra/terraform/bootstrap/oidc.tf` (NEW: does not exist yet. `aws_iam_openid_connect_provider` para `https://token.actions.githubusercontent.com`, audiencia `sts.amazonaws.com` [CI 1, CI 2])
- `infra/terraform/bootstrap/ci_roles.tf` (NEW: does not exist yet. `ci-plan`, `ci-apply`, trust policies, políticas sobre ARN exactos de `envs/dev` y `envs/prod`, boundary y los Deny de Design Decision 4)
- `infra/terraform/bootstrap/owner_user.tf` (NEW: does not exist yet. 4 bloques `import` y los recursos `aws_iam_user.owner`, `aws_iam_group.admins`, `aws_iam_group_policy_attachment` con `policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"`, `aws_iam_user_group_membership`)
- `infra/terraform/bootstrap/variables.tf` (NEW: does not exist yet. email del budget con `sensitive = true`, nombre del bucket)
- `infra/terraform/bootstrap/terraform.tfvars.example` (NEW: does not exist yet. placeholder del email; el `terraform.tfvars` real está gitignored por `.gitignore:8` y `.gitignore:9` deja pasar el `.example`)
- `infra/terraform/envs/dev/backend.tf` (NEW: does not exist yet. `backend "s3"` con bucket literal, `use_lockfile = true`, `region = "eu-west-3"`, clave `envs/dev/terraform.tfstate`; provider eu-west-3)
- `infra/terraform/envs/prod/backend.tf` (NEW: does not exist yet. igual con clave `envs/prod/terraform.tfstate`)
- `infra/terraform/.tflint.hcl` (NEW: does not exist yet. configuración de tflint con plugin AWS; versión a fijar en Implement. Con `--chdir` tflint busca su config en el directorio indicado: que encuentre este archivo desde `infra/terraform/` no está comprobado; si no, Implement lo coloca por root module o usa `--config` y lo dice en el informe)
- `.github/workflows/terraform-plan.yml` (NEW: does not exist yet. ver Core Components; incluye el job `static-checks` con checkov; sin `paths`; `concurrency` por PR con cancelación; matriz dev/prod; actions fijadas por SHA)
- `.github/workflows/terraform-apply.yml` (NEW: does not exist yet. ver Core Components; sin `paths`; `concurrency` grupo `terraform-apply`, `cancel-in-progress: false`)
- `docs/runbooks/foundations-bootstrap.md` (NEW: does not exist yet; `docs/runbooks/` tampoco. Pasos del owner, en orden: comprobar que `skyroute-dev` existe y está en `admins` con MFA; `aws login`; crear `terraform.tfvars` desde el `.example`; `terraform init` y `apply` locales en `bootstrap/` tras revisar el plan con los 4 imports en 0 cambios; añadir `backend.tf` y `terraform init -migrate-state`; `aws budgets describe-budgets` para verificar el budget de Terraform; borrar el budget manual de 1 USD; borrar el bucket manual de state previo (nombrado en el runbook: `skyroute-tfstate-demo-437266392155-eu-north-1-an`, región `eu-north-1`, para que el paso de borrado sea ejecutable; decisión del owner, 2026-11-13); configurar en la UI los environments ya creados (deployment branches solo `main` en `dev` y `prod`, revisor requerido en `prod`, bypass de administradores desactivado) y la branch protection de `main` con PR requerida, y comprobarlos con A10; nota de exportar el state antes de cerrar la cuenta Free. Todo lo ejecuta el owner)
- `AGENTS.md` (lines 100-105: bloque de TODO de § Comandos de build y test; sustituir la línea 103 por cuatro líneas, una por comando: `terraform fmt -check -recursive infra/terraform`; `terraform -chdir=infra/terraform/<root-module> validate` (con `init -backend=false` previo, indicado en comentario); `tflint --chdir=infra/terraform/<root-module> --config=$PWD/infra/terraform/.tflint.hcl` (con `tflint --init` previo, indicado en comentario; nunca con `--recursive`; hallazgo del implementador de la Fase 6: sin `--config` absoluto, `--chdir` no encuentra la config; AGENTS.md ya lo usa así); una línea de comentario para `checkov -d infra/terraform` que indica que corre en CI (job `static-checks` de `terraform-plan.yml`), no localmente; el resto de TODO no cambia)
- Generados/owner, no autor: `infra/terraform/{bootstrap,envs/dev,envs/prod}/.terraform.lock.hcl` (generados por `init -backend=false`, versionados) e `infra/terraform/bootstrap/backend.tf` (lo añade el owner en el runbook).

`.gitignore` no cambia: ya contiene `.terraform/` (5), `*.tfstate` y `*.tfstate.*` (6-7), `*.tfvars` (8) y `!*.tfvars.example` (9). `docs/design/CONTEXT.md` no se toca (Convention "Design write ownership"). Los environments y la branch protection de GitHub no son archivos ni recursos AWS (los environments ya existen; los configura el owner en la UI, Design Decision 7).

## Implementation Plan

Fases 1–6 las implementa `executor`; cada validación es un único comando no destructivo que un agente puede ejecutar (Convention "Simple shell commands"). Fase 7 es solo del owner y de CI (Convention Apply gate): ningún agente ejecuta `terraform plan`, `terraform apply`, `terraform init -migrate-state` ni comandos `aws`.

1. **Fase 1: bootstrap base (provider, budget, bucket de state).**
   - `versions.tf`, `variables.tf`, `terraform.tfvars.example`, `budget.tf`, `state_bucket.tf` (lifecycle 90 días y protecciones incluidos). Sin bloque backend (state local).
   - Setup del agente (no es la validación): `terraform -chdir=infra/terraform/bootstrap init -backend=false`; requiere red (descarga el provider) y crea `.terraform/` (gitignored) y `.terraform.lock.hcl`.
   - Validación (agente): `terraform -chdir=infra/terraform/bootstrap validate` → "Success! The configuration is valid."
2. **Fase 2: OIDC y roles de CI** (depende de Fase 1: los ARN del bucket y las claves).
   - `oidc.tf`, `ci_roles.tf`: trust con `StringEquals` y los 3 `sub`; políticas de backend sobre ARN exactos; boundary y Deny.
   - Validación (agente): Grep `repo:javiladino@97758532/skyroute@1455233709:(pull_request|environment:(dev|prod))` en `infra/terraform/bootstrap/` → exactamente 3 coincidencias.
3. **Fase 3: IAM del owner** (independiente de Fase 2, después de Fase 1).
   - `owner_user.tf` con 4 bloques `import` (user `skyroute-dev`, grupo `admins`, attachment, membresía); el attachment usa `AdministratorAccess`; los IDs exactos de import del attachment y la membresía se confirman en Implement.
   - Validación (agente): Grep `^import\s*\{` en `infra/terraform/bootstrap/owner_user.tf` → 4 coincidencias.
4. **Fase 4: backends de `envs/dev` y `envs/prod`** (depende de Fase 1: nombre del bucket).
   - `envs/dev/backend.tf`, `envs/prod/backend.tf` con bucket literal y las claves fijadas. El `backend.tf` de bootstrap lo añade el owner (runbook), no el agente.
   - Validación (agente): Grep `use_lockfile\s*=\s*true` en `infra/terraform/envs/` → 2 coincidencias.
5. **Fase 5: workflows** (depende de Fases 2 y 4: ARN de roles y root modules).
   - `terraform-plan.yml` (con el job `static-checks` de checkov), `terraform-apply.yml` con los endurecimientos de Core Components; actions fijadas por SHA de 40 caracteres (`actions/checkout`, `hashicorp/setup-terraform` mayor v4 [CI 9], `aws-actions/configure-aws-credentials` mayor v6 [CI 8], `actions/github-script` [CI 10]); SHA exactos a fijar en Implement (último tag no confirmado en la research).
   - Validación (agente): Grep `pull_request_target` en `.github/workflows/` → 0 coincidencias.
6. **Fase 6: análisis estático, `AGENTS.md` y runbook** (depende de Fases 1–5).
   - `infra/terraform/.tflint.hcl`; rellenar `AGENTS.md:103` (un comando por línea); escribir `docs/runbooks/foundations-bootstrap.md`.
   - Validación (agente): `tflint --chdir=infra/terraform/bootstrap` (tras `tflint --init`, con red; nunca combinado con `--recursive`) → exit 0. Los otros dos root modules (`envs/dev`, `envs/prod`) se comprueban en `reppit-test` (T3). checkov NO está instalado localmente (executor, 2026-11-13): corre en CI y su evidencia es el run de Actions (Testing Strategy T4), no una validación de esta fase.
7. **Fase 7: puesta en marcha (solo owner y CI).**
   - Owner: los environments `dev`/`prod` ya existen; configura en la UI deployment branches solo `main` en ambos, revisor requerido en `prod`, bypass de administradores desactivado y branch protection de `main` con PR requerida; sigue `docs/runbooks/foundations-bootstrap.md` (`aws login`, `terraform apply` local en `bootstrap/`, `backend.tf` + `terraform init -migrate-state`, verificar el budget, borrar budget y bucket manuales).
   - CI: PR de prueba que toca `envs/dev` → comentario de plan y job `static-checks` (checkov) en verde; merge → run de `terraform-apply.yml` con `apply-dev` verde.
   - Validación: evidencia aportada por el owner (Convention Verification ownership): URL del comentario de plan y URL del run de apply.

## Testing Strategy

Contrato para `reppit-test`. No hay tests unitarios ni de integración en código: los checks son estáticos (agente) y evidencia del owner/CI. Los Grep se ejecutan con la herramienta Grep o `rg` sin pipes.

### Verify command y análisis estático (agente; `AGENTS.md:103` tras Fase 6)

| # | Comando | Esperado |
|---|---------|----------|
| T1 | `terraform fmt -check -recursive infra/terraform` | exit 0, sin salida |
| T2 | Por root module (3 comandos), tras `terraform -chdir=<dir> init -backend=false` (red; crea `.terraform/`): `terraform -chdir=infra/terraform/bootstrap validate`, ídem `envs/dev` y `envs/prod` | "Success! The configuration is valid." en los tres |
| T3 | `tflint --chdir=infra/terraform/bootstrap`, ídem `envs/dev` y `envs/prod` (tras `tflint --init`, con red). Nunca con `--recursive` | exit 0 en los tres |
| T4 | CI, no local: `checkov -d infra/terraform` en el job `static-checks` de `terraform-plan.yml` (checkov no está instalado localmente). Evidencia: URL del run de Actions aportada por el owner/CI (Convention Verification ownership) | job en verde; omisiones solo con `#checkov:skip=<ID>:<motivo>` en línea |
| T4b | Grep `checkov` en `.github/workflows/terraform-plan.yml` | ≥ 1, en un job sin `id-token: write` ni `environment:` |

### Convention Region

| # | Check | Esperado |
|---|-------|----------|
| R1 | Grep `region\s*=\s*"eu-west-3"` en `infra/terraform/` | ≥ 1 por provider y por `backend "s3"` (bootstrap, dev, prod) |
| R2 | Grep `region\s*=\s*"(?!eu-west-3)` (`-P`) en `infra/terraform/` | 0 |
| R3 | Grep `eu-north-1` en `infra/terraform/**/*.tf` (el runbook lo nombra a propósito, decisión del owner 2026-11-13) | 0 |
| R4 | Grep `skyroute-tfstate-demo` en `infra/terraform/**/*.tf` (el bucket manual no se adopta en código) | 0 |
| R5 | `grep -c skyroute-tfstate-demo-437266392155-eu-north-1-an docs/runbooks/foundations-bootstrap.md` | ≥ 1 |

### Convention IaC only

| # | Check | Esperado |
|---|-------|----------|
| I1 | Grep `use_lockfile\s*=\s*true` en `infra/terraform/` | 2 tras Implement (dev, prod); 3 cuando el owner añade `bootstrap/backend.tf` |
| I2 | Grep `dynamodb_table` en `infra/terraform/` | 0 |
| I3 | Grep `resource "aws_budgets_budget"` en `infra/terraform/bootstrap/` | 1 |
| I4 | Grep `^import\s*\{` en `infra/terraform/bootstrap/` | 4 (user, grupo, attachment, membresía; única excepción de consola) |

### Convention Apply gate y roles de CI

| # | Check | Esperado |
|---|-------|----------|
| A1 | Grep `repo:javiladino@97758532/skyroute@1455233709:(pull_request|environment:(dev|prod))` en `infra/terraform/bootstrap/` | exactamente 3 (1 en `ci-plan`, 2 en `ci-apply`) |
| A2 | Grep `StringLike` en `infra/terraform/` | 0 |
| A3 | Grep `sts.amazonaws.com` en `infra/terraform/bootstrap/` | ≥ 1 en cada trust y en el proveedor OIDC |
| A4 | Grep `Resource\s*=\s*"\*"` en `ci_roles.tf` (`grep -n 'Resource *= *"\*"' infra/terraform/bootstrap/ci_roles.tf`); el revisor comprueba que cada línea devuelta está en un statement con `Effect = "Deny"` | hoy 6 líneas, todas en Deny; el comodín solo se admite en Deny |
| A4a | Grep multilínea `Effect\s*=\s*"Allow"[^}]*Resource\s*=\s*"\*"` en `ci_roles.tf` | 0 (ningún Allow con `*` en `Resource`) |
| A4d | Grep `iam:CreatePolicyVersion` en `ci_roles.tf` (`grep -c 'iam:CreatePolicyVersion' infra/terraform/bootstrap/ci_roles.tf`); Grep `iam:SetDefaultPolicyVersion`, `iam:DeletePolicy"`, `iam:DeletePolicyVersion` (uno por patrón) | 3 (boundary, `ci-plan`, `ci-apply`); ≥ 3 cada uno de los otros |
| A4e | Grep `StringNotEquals` y `iam:PermissionsBoundary` en `ci_roles.tf` | ≥ 1 cada uno; la condición es `StringNotEquals` sobre `iam:PermissionsBoundary` = ARN de `ci-boundary` |
| A4b | Grep `(envs/(dev|prod)/terraform\.tfstate)(\.tflock)?` en `ci_roles.tf` | ≥ 8 (2 claves + 2 `.tflock` por rol) |
| A4c | Grep `bootstrap/terraform\.tfstate` en `ci_roles.tf` | 0 (los roles de CI nunca ven el state del bootstrap) |
| A5 | Grep `pull_request_target` en `.github/workflows/` | 0 |
| A5b | Grep `bootstrap` en `.github/workflows/` | 0 (ningún workflow toca el bootstrap) |
| A6 | Grep `uses:\s*\S+@(?![0-9a-f]{40})` (`-P`) en `.github/workflows/` | 0 |
| A7 | Grep `upload-artifact` en `.github/workflows/` | 0 |
| A7b | Grep `^permissions:\s*\{\}` en `.github/workflows/` | 2 (uno por workflow) |
| A7c | Grep `persist-credentials:\s*false` en `.github/workflows/` | ≥ 1 por cada `actions/checkout` (igual al número de usos de checkout) |
| A7d | Grep `^concurrency:` o `concurrency:` en `terraform-apply.yml` | ≥ 1 |
| A7f | `grep -r -c 'paths:' .github/workflows` | 0 en cada archivo (ningún trigger con filtro `paths`) |
| A7e | Grep `-no-color` en `terraform-plan.yml`; Grep `TF_LOG` en `.github/workflows/` | ≥ 1; 0 |
| A8 | Grep `environment:\s*(dev|prod)` en `terraform-apply.yml`; Grep `environment:` en `terraform-plan.yml` | 2; 0 |
| A9 | Grep `terraform (plan|apply)` en `.github/workflows/terraform-plan.yml` | solo `plan` |
| A10 | Owner (los environments ya existen; se comprueba su configuración): `gh api repos/javiladino/skyroute/environments/dev`, `gh api repos/javiladino/skyroute/environments/prod` y `.../branches/main/protection` | `deployment_branch_policy` solo `main`; prod con revisor requerido, `prevent_self_review` false y administradores sin bypass (`can_admins_bypass` false); `main` con PR requerida |

### Seguridad del state, IAM y trust (agente)

| # | Check | Esperado |
|---|-------|----------|
| S1 | Grep `prevent_destroy\s*=\s*true` y `force_destroy\s*=\s*false` en `state_bucket.tf` | 1 cada uno |
| S2 | Grep `s3:DeleteBucket` en `state_bucket.tf` | ≥ 1 (Deny en la bucket policy) |
| S3 | Grep `s3:DeleteObjectVersion`, `s3:PutBucketVersioning`, `s3:PutBucketPublicAccessBlock`, `s3:PutLifecycleConfiguration`, `s3:PutBucketPolicy` en `ci_roles.tf` (uno por patrón) | ≥ 1 cada uno, en Deny de ambos roles |
| S4 | Grep `user/skyroute-dev` y `group/admins` en `ci_roles.tf` | ≥ 3 cada uno (boundary y los dos roles) |
| S5 | Grep `iam:PermissionsBoundary`, `iam:CreateRole`, `iam:PutRolePermissionsBoundary`, `iam:DeleteRolePermissionsBoundary` en `ci_roles.tf` | ≥ 1 cada uno |
| S6 | Grep `sts:AssumeRoleWithWebIdentity` en `ci_roles.tf`; Grep `sts:AssumeRole"` | 2 (uno por trust); 0 |
| S7 | Grep `Federated\s*=\s*aws_iam_openid_connect_provider\.\w+\.arn` en `ci_roles.tf` | 2 |
| S8 | Grep multilínea `StringEquals[^}]*:aud[^}]*:sub` (y orden inverso `:sub[^}]*:aud`) en `ci_roles.tf` | 2 en total (`aud` y `sub` en el mismo bloque, uno por rol) |
| S9 | Grep `[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}` en `infra/`, `.github/` y `docs/runbooks/` | solo placeholders (por ejemplo `tu-email@example.com`); ningún email real |
| S10 | Grep `sensitive\s*=\s*true` en `variables.tf`; Grep `terraform.tfvars` en `.gitignore` | ≥ 1; la regla `*.tfvars` (línea 8) con `!*.tfvars.example` (línea 9) |

### Convention No hourly-billed resources

| # | Check | Esperado |
|---|-------|----------|
| N1 | Grep `aws_kms|aws_nat_gateway|aws_vpc|aws_vpc_endpoint|aws_lb|aws_eip|aws_instance|aws_db_instance|aws_mwaa|aws_emr|aws_redshift|aws_secretsmanager_secret|aws_cloudtrail|aws_config` en `infra/terraform/` | 0 |
| N2 | Grep `aws_budgets_budget_action` en `infra/terraform/` | 0 |

### Budget y bucket (detalle de la Decision)

| # | Check | Esperado |
|---|-------|----------|
| B1 | Grep `threshold\s*=\s*(50|80|100)\b` en `budget.tf` | 3 |
| B2 | Grep `FORECASTED` en `infra/terraform/` | 0 |
| B3 | Grep `subscriber_email_addresses` en `budget.tf` | 3 |
| B4 | Grep `noncurrent_days\s*=\s*90`, `abort_incomplete_multipart_upload` y `expired_object_delete_marker` en `state_bucket.tf` | 1 cada uno |
| B5 | Grep `aws:SecureTransport` en `state_bucket.tf` | ≥ 1 |
| B6 | Owner: `aws s3api get-bucket-encryption --bucket <state-bucket>`, `aws s3api get-bucket-versioning --bucket <state-bucket>`, `aws budgets describe-budgets --account-id <id>` | `AES256`; `Enabled`; budget de 10 USD |
| B7 | Grep `include_credit\s*=\s*false` en `budget.tf` | 1 |
| B8 | Grep `include_refund\s*=\s*false` en `budget.tf` | 1 |
| B9 | Owner: tras el apply, `terraform plan` en `bootstrap/` con los 4 imports | 0 cambios sobre user, grupo, attachment y membresía |

### Criterio de Fase 1

| # | Check | Esperado |
|---|-------|----------|
| F1 | "Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica." Evidencia del owner/CI | URL del comentario de plan en una PR de prueba y URL del run de `terraform-apply.yml` con job `apply-dev` en verde |

Archivos que no deben cambiar: ninguno fuera de Files Changed (`git diff --stat main` limitado a las 15 rutas del autor, los 3 `.terraform.lock.hcl`, `bootstrap/backend.tf` del owner y los stage files de `docs/design/foundations/working/`).

## Observability

Not applicable for this change, salvo los avisos de budget por email (ACTUAL 50/80/100 %), descritos en Data Models.

## Future Considerations

### Open Questions (owner)

Ninguna abierta para el owner.

Cerradas (2026-11-13): environments y branch protection de GitHub (los environments `dev` y `prod` ya existen; configuración en la UI por el owner, fuera de IaC only, comprobada con A10); policy del grupo `admins` (`AdministratorAccess`); nombre del bucket (`skyroute-tfstate-437266392155-eu-west-3`); checkov (corre en CI, job `static-checks`). Antes: IDs de GitHub 97758532 / 1455233709 y claves de state (`bootstrap/`, `envs/dev/`, `envs/prod/` + `terraform.tfstate`). Nombre del user (`skyroute-dev`) y email del budget (solo en `terraform.tfvars` local) ya dados por el owner.

### Precondiciones pendientes (no investigadas)

- Permisos IAM para `aws_budgets_budget` y para los recursos de `envs/*` [IAM 11]: no se inventan listas de acciones. En esta fase `envs/*` no tiene recursos, así que `ci-plan`/`ci-apply` solo llevan permisos del backend (`s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` en `.tflock` [TL 5]). La boundary [IAM 12] y los Deny se dimensionan con eso y se amplían cuando una fase posterior añada recursos.
- Emisión de JWT a PRs de fork [CI 16]: prueba del owner.
- Últimos tags/SHA de las actions [CI 8, CI 9].
- Personalización del `sub` con `ref`/`job_workflow_ref`: no comprobada.
- Bypass de administradores en el environment `prod`: inferencia, no documentado; A10 lo comprueba con el owner.
- `aws login` con Terraform y versión mínima de la AWS CLI: no comprobado; se verifica en Implement/runbook.
- Versiones locales verificadas por `executor`: tflint 0.65.0 y terraform 1.17.1; checkov no instalado (corre en CI).
- Que tflint encuentre `infra/terraform/.tflint.hcl` con `--chdir` en cada root module: no comprobado; se resuelve en Implement.

### Known Limitations

- Free termina a los 6 meses o al agotar créditos [AC 2, AC 3]; `docs/design/README.md:51` sigue abierta. Al cierre de la cuenta Free se pierden los recursos, incluido el bucket de state: el runbook indica exportar el state antes.
- Fuera de alcance: Organizations, KMS, Paid, cualquier recurso del lakehouse, `infra/terraform/modules/`.

## Dependencies

- Terraform CLI ≥ 1.11.0 (locking S3 GA [TL 4]); última citada v1.17.2 [TL 11]; local 1.17.1 (executor). Provider `hashicorp/aws` v6.73.0 citado [TL 12]. Restricción exacta de versión a fijar en Implement.
- tflint (con plugin AWS; local 0.65.0): versión a fijar en Implement. checkov (no instalado localmente): solo en CI, `pip install` de versión fijada en Implement; si `pip install` o la action de checkov es preferible, no comprobado.
- Actions: `hashicorp/setup-terraform` v4 [CI 9], `aws-actions/configure-aws-credentials` v6 [CI 8], `actions/github-script` [CI 10], `actions/checkout`; todas por SHA.

## Security Considerations

- Root con MFA y sin access keys [IAM 1, IAM 2]; owner con IAM user `skyroute-dev` + MFA, sin access keys, CLI con `aws login`.
- Datos públicos aceptados: el account id, el owner id y el repo id de GitHub quedan visibles en el repo público, en comentarios de plan y en el state. Se aceptan explícitamente: no son secretos (inferencia, no comprobado); el `sub` exacto es lo que acota la trust.
- Trust OIDC solo `StringEquals`, `aud` `sts.amazonaws.com`, 3 `sub` exactos en formato inmutable [CI 5]; `ci-apply` no confía en `pull_request`.
- Environments solo desde `main`; `prod` con revisor requerido; "Prevent self-review" desactivado: la aprobación es una pausa deliberada, no revisión de cuatro ojos.
- Bucket: Block Public Access, deny sin TLS, Ownership enforced, Versioning, lifecycle 90 días [IAM 17–20, IAM 18].
- Boundary y Deny sobre roles `ci-*`, proveedor OIDC, bucket policy del state, `user/skyroute-dev`, `group/admins` y la propia política `ci-boundary` (sin `CreatePolicyVersion`, `SetDefaultPolicyVersion`, `DeletePolicy` ni `DeletePolicyVersion`); `Resource = "*"` solo en Deny, 0 `*` en Allow; el bucket de state con `prevent_destroy`, `force_destroy = false` y Deny de borrado de bucket y versiones, y ningún workflow toca `bootstrap/`.
- Workflows: `permissions: {}` superior, permisos por job, `persist-credentials: false`, `concurrency` en apply, `plan -no-color`, sin `TF_LOG`.
- Main protegida con PR requerida y `prod` sin bypass de administradores (configurado por el owner; A10).
- Repo público: el email del budget solo en `terraform.tfvars` gitignored (nunca versionado), variables sensibles con `sensitive = true`, sin `pull_request_target` con `id-token: write` [CI 15], nunca el binario del plan como artifact.

## Rollout Strategy

1. Implement (agente): Fases 1–6, validadas con los checks estáticos locales (checkov solo en CI).
2. Owner, siguiendo `docs/runbooks/foundations-bootstrap.md` (Convention Apply gate): configuración de los environments existentes y branch protection, `aws login`, apply local del bootstrap (imports en 0 cambios), `backend.tf` + `init -migrate-state`, verificar el budget de Terraform con `aws budgets describe-budgets`, borrar el budget manual de 1 USD y el bucket manual de state previo.
3. CI: PR de prueba con plan comentado y checkov en verde; merge aplica `dev`.
4. `prod`: apply tras aprobación manual del owner en el environment.
5. Seguimiento: avisos de budget por email.

## References

- `docs/design/foundations/working/research.md` (§ 3.0–3.4, § 5, § 7)
- `docs/design/foundations/working/proposal.md` (§ Decision, Proposal 1, Proposal 3, Huecos comunes)
- `docs/design/foundations/context.md` § Rulings, "Foundations design"
- `docs/design/CONTEXT.md` § Conventions: Region, IaC only, Apply gate, No hourly-billed resources, Simple shell commands, Verification ownership, Design write ownership, Git workflow
- `docs/design/README.md:15` (Fase 1)
- `.gitignore:5-9` (reglas de Terraform ya presentes)
- Review adversarial/seguridad/coste de la ronda 1 y datos del owner, 2026-11-13
- Tarea: brief del orquestador, 2026-11-12
