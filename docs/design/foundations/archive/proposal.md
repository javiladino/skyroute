---
type: Proposal
---

# foundations: Solution Proposals

> **Task:** proponer el diseño de la Fase 1 (acceso del owner, plan de cuenta, bootstrap de Terraform con state remoto, rol(es) OIDC de CI y CI básica).
> **Date:** 2026-11-12
> **Research source:** `docs/design/foundations/working/research.md`; § 3.1–3.4, § 4, § 4.1 (tensiones 2–7), § 6.
> **Review:** una ronda adversarial/seguridad/coste aplicada (hallazgos A1–A8, S1–S10, C1–C7 integrados); sin segunda ronda.

## Context

**Request:** elegir cómo accede el owner, en qué plan queda la cuenta, cómo se cifra y protege el state y cuántos roles OIDC usa CI, para que la Fase 1 cierre.

**Success criteria:**
1. Fase 1 (`docs/design/README.md:15`): "Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica."
2. Convention Region.
3. Convention IaC only.
4. Convention Apply gate.
5. Convention No hourly-billed resources.

(Texto de cada Convention en `docs/design/CONTEXT.md` § Conventions; aquí se citan por nombre y se aplican, no se reabren.)

**Datos del owner (decididos, 2026-11-12):** la cuenta existe en eu-west-3 y está hoy en plan Free; el owner está abierto a Paid; Identity Center con Organizations debe aparecer como una de las opciones, no en todas; el repo `javiladino/skyroute` es público y se creó el 2026-11-12 (research § 1, F1–F3).

**Key constraints from the research:**
- No existe `infra/`, ningún `*.tf` ni `.github/workflows/`; todo es nuevo (research § 3.0).
- Backend S3 con `use_lockfile = true`: lock `.tflock` junto al state; DynamoDB deprecado (§ 3.1, [TL 3, TL 6]). El bloque backend no admite variables; configuración parcial con `-backend-config` (§ 3.1, [TL 7, TL 8]).
- Bootstrap: root module con state local y luego `backend "s3"` + `init -migrate-state` [TL 9, TL 10]; encaja con la excepción única de la Convention Apply gate (tensión 4, § 4.1).
- Permisos mínimos del backend: `s3:ListBucket` en el bucket, Get/Put en el state, Get/Put/Delete en `.tflock`; más `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey` si hay `kms_key_id` [TL 5, IAM 11]. `s3:ListBucket` literal sin verificar (§ 3.5 ítem 1). Los permisos para crear recursos del proyecto (incluido Budgets) no se investigaron [IAM 11], § 4.
- El state es texto plano y guarda secretos de la configuración (§ 3.3). SSE-S3 es el cifrado por defecto sin coste; SSE-KMS con clave de cliente cuesta 1 USD/mes "prorrateado por hora" y se factura aunque esté inactiva [IAM 15, IAM 16]; precio en eu-west-3 no verificado (§ 3.5 ítem 11).
- HashiCorp recomienda "highly" Bucket Versioning [IAM 11]; Block Public Access, deny sin `aws:SecureTransport`, Object Ownership "Bucket owner enforced" [IAM 17–20].
- OIDC: emisor `token.actions.githubusercontent.com`, `aud = sts.amazonaws.com` [CI 1]; IAM rechaza una trust policy sin `:sub` o con `:sub` solo comodín (§ 3.2). Un job con environment emite `sub` de environment, no de rama [CI 13].
- El repo emite el formato `sub` inmutable `repo:OWNER@OWNER-ID/REPO@REPO-ID:...` por haberse creado después del 2026-07-15; una trust policy con el formato antiguo falla con "Not authorized to perform sts:AssumeRoleWithWebIdentity" (§ 3.2, [CI 5], nota de § 6). Los IDs numéricos no están en la research.
- Revisores requeridos en environments: disponibles en repos públicos en Free/Pro/Team; se ignoran si el repo pasa a privado en Free (tensión 3 resuelta por F2; [CI 12]).
- Identity Center con instancia de organización crea una organización, pasa la cuenta a Paid y expira los créditos de free tier [IAM 4, AC 7]; la instancia de cuenta no da acceso a cuentas AWS [IAM 5]. Mejora a Paid irreversible [AC 4]. Free termina a los 6 meses o al agotar créditos, con cierre/suspensión [AC 2, AC 3]. Decisión abierta: `docs/design/README.md:51` "Plan de cuenta AWS (créditos Free Tier desde julio 2025)", Plan Free / Plan Paid con presupuesto y alertas, Proposed.
- Budgets sin acciones cuesta 0 USD; API global `budgets.amazonaws.com` sin fila eu-west-3 (tensión 2; [AC 13, AC 15]); avisos FORECASTED no se disparan en cuenta nueva (§ 3.4).
- Orden: el bucket (o el state local) precede al budget, aunque la Convention IaC only lo llama "primer recurso" (tensión 7, inferencia de la research).

**Lo que la research no cubre (común a las tres propuestas):** permisos IAM para `aws_budgets_budget` y demás recursos del bootstrap; IDs numéricos de owner y repo; emisión de JWT a PRs de fork [CI 16]; últimos tags de las actions [CI 8, CI 9]; precio de Identity Center (404, [IAM 7]).

## Proposal 1: Mínimo coste y mínimo cambio de cuenta

### Overview
Se queda en plan Free, el owner entra con un IAM user con MFA, el bucket de state usa SSE-S3 y CI asume un único rol OIDC cuya trust policy acepta solo tres `sub` exactos. Es la vía con menos piezas y sin ningún cargo nuevo; su coste es que el rol que corre `plan` en una PR tiene los mismos permisos que el que aplica.

**Ejes:** (a) SSE-S3; (b) Free; (c) IAM user con MFA; (d) un rol.

### Key Changes
| Component | Change |
|-----------|--------|
| `infra/terraform/bootstrap/` | New: root module con state local (luego `backend "s3"` + `init -migrate-state`, [TL 9]); provider con `region = "eu-west-3"`. Crea `aws_budgets_budget` 10 USD con avisos ACTUAL 50/80/100 % (sin acciones, [AC 13, AC 18]), bucket de state con SSE-S3 [IAM 15], Versioning [IAM 11, IAM 18], Block Public Access [IAM 17], deny `aws:SecureTransport = "false"` [IAM 19], Object Ownership enforced [IAM 20]; proveedor OIDC [CI 1, CI 2]; un rol `ci` |
| Trust policy de `ci` | `aud = sts.amazonaws.com`; `StringEquals` en `token.actions.githubusercontent.com:sub` con la lista: `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:pull_request`, `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:environment:dev`, `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:environment:prod` (formato inmutable, § 3.2, [CI 4, CI 5, CI 13]). Sin `ref:refs/heads/main`: los jobs de apply declaran environment y por eso emiten `sub` de environment [CI 13] |
| Políticas de `ci` | Permisos del backend [TL 5, IAM 11] más los de los recursos de `envs/dev` y `envs/prod` (no investigados, [IAM 11]) |
| Acceso del owner | IAM user con MFA [IAM 3]; root sin access keys y con MFA [IAM 1, IAM 2]. Quién lo crea: Open Question 1 |
| `infra/terraform/envs/{dev,prod}/` | New: `backend "s3"` con `use_lockfile = true` y `region = "eu-west-3"` [TL 2, TL 3]; claves distintas por entorno |
| `.github/workflows/terraform-plan.yml` | New: `pull_request`; `permissions: id-token: write, contents: read, pull-requests: write` [CI 7, CI 11]; fmt, init, validate, plan; comentario vía `actions/github-script` o job summary si supera 65535 caracteres [CI 10] |
| `.github/workflows/terraform-apply.yml` | New: `push` a `main`; job `apply-dev` con `environment: dev`; job `apply-prod` con `environment: prod` y revisor requerido (repo público, [CI 12]) |
| Environments `dev` y `prod` | New: "deployment branches: solo `main`" en ambos (reglas de ramas de despliegue, research § 3.2), para que un job de una PR que declare `environment: dev` no pueda emitir el `sub` `environment:dev` [CI 13]. Opcional: personalizar el `sub` para incluir `ref` / `job_workflow_ref` (no comprobado: la research no documenta esa personalización) |
| Budget (detalle) | `aws_budgets_budget` de 10 USD, avisos ACTUAL a 50, 80 y 100 %, cada `notification` con `subscriber_email_addresses` (al menos un suscriptor, [AC 18]). Los avisos FORECASTED no se disparan en cuenta nueva (research § 3.4), por eso solo ACTUAL |
| Lifecycle del bucket de state | New: `aws_s3_bucket_lifecycle_configuration` con `noncurrent_version_expiration` (días: Open Question 5), limpieza de delete markers expirados y `abort_incomplete_multipart_upload`; opcional Deny `s3:DeleteObject` sobre la clave del state. Evita crecimiento sin límite con Versioning (inferencia; no hay precio S3 en la research) |
| Permisos de `ci` (límites) | Permissions boundary [IAM 12] y Deny explícito sobre modificar los roles `ci-*`, el proveedor OIDC y la bucket policy del state, para que un apply comprometido no amplíe sus propios permisos. Permisos de Budgets y `envs/*`: no investigados [IAM 11], Open Question 4 |
| Endurecimiento de workflows | Ningún workflow con `id-token: write` usa `pull_request_target` [CI 15]; actions fijadas por SHA de commit [CI 8]. Repo público: el comentario de plan y cualquier artifact son públicos; sin secretos en `*.tf`/`tfvars`, variables sensibles con `sensitive = true`, y no subir nunca el binario del plan como artifact |
| Cuenta AWS | No change: sigue en Free |

### Trade-offs
| Benefit | Risk |
|---------|------|
| Coste nuevo 0: SSE-S3 sin coste [IAM 15], Budgets sin acciones 0 USD [AC 13], IAM/STS sin cargo [IAM 7] | El plan Free termina a los 6 meses o al agotar créditos y la cuenta se cierra o suspende [AC 2, AC 3]; la Fase 1 no lo resuelve, solo lo aplaza |
| Versioning protege el state frente a borrados y corrupción [IAM 11, IAM 18] | Sin lifecycle, las versiones no actuales crecen sin límite; con lifecycle, el plazo elegido limita cuánto se puede restaurar (Open Question 5) |
| Ninguna duda frente a No hourly-billed resources: no hay clave KMS (tensión 6) | El state en texto plano con secretos (§ 3.3) solo queda cifrado con clave gestionada por AWS; sin control de acceso separado por clave |
| Un rol, una trust policy: menos piezas que mantener | **Severidad alta.** La trust acepta el `sub` `pull_request` y el rol tiene permisos de apply: una PR que modifique el workflow podría ejecutar `apply` con esos permisos; la aprobación de prod protege el environment, no el rol. Agravante por asimetría: el repo es público y la emisión de JWT a PRs de fork no está documentada [CI 16] (no comprobado), así que no se puede descartar que un fork obtenga ese `sub` |
| Environments con "deployment branches: solo `main`" acotan el `sub` `environment:*` a ramas permitidas (research § 3.2) | No protege el `sub` `pull_request`, que en P1 sigue con permisos de apply; el control depende de la configuración en GitHub, no de AWS |
| `sub` exactos con `StringEquals`, sin comodín (IAM lo exige, § 3.2) | Si los IDs `<OWNER-ID>`/`<REPO-ID>` son erróneos, falla con "Not authorized to perform sts:AssumeRoleWithWebIdentity" [CI 5] |
| IAM user no requiere Organizations ni cambia el plan [IAM 3, IAM 10] | Credenciales de larga duración [IAM 3]; AWS prefiere credenciales temporales [IAM 1] |

### Validation
1. File check: `infra/terraform/bootstrap/*.tf` contiene `region = "eu-west-3"` en el provider y `use_lockfile = true` en todo `backend "s3"` (Grep `region\s*=\s*"eu-west-3"` y `use_lockfile\s*=\s*true` en `infra/terraform/`).
2. File check: ningún `*.tf` contiene `aws_kms_key`, `aws_nat_gateway` ni `aws_vpc` (Grep).
3. File check: la trust policy contiene exactamente tres valores `:sub`, todos con `@<id numérico>` en owner y repo, y ningún `*`. Grep `repo:javiladino@[0-9]+/skyroute@[0-9]+:(pull_request|environment:(dev|prod))` en `infra/terraform/bootstrap/`: esperado 3 coincidencias; Grep `sub"?\s*[:=].*\*` en el mismo directorio: esperado 0.
3b. File check: ningún `StringLike` en `infra/terraform/` (Grep `StringLike`: esperado 0).
3c. Owner: `gh api repos/javiladino/skyroute/environments/dev` y `.../environments/prod` muestran `deployment_branch_policy` con solo `main`.
3d. File check: sin `pull_request_target` en `.github/workflows/` (Grep: 0), y cada `uses:` con SHA de 40 caracteres (Grep `uses:\s*\S+@(?![0-9a-f]{40})` con `-P`: esperado 0). Grep `sensitive\s*=\s*true` en variables con secretos y 0 coincidencias de `upload-artifact` con ficheros `tfplan`.
3e. File check: en `aws_budgets_budget` aparecen `threshold = 50`, `80` y `100` (Grep `threshold\s*=\s*(50|80|100)\b`: 3 coincidencias por budget), `limit_amount\s*=\s*"?10` y `subscriber_email_addresses`; 0 coincidencias de `FORECASTED`.
3f. File check: existe `aws_s3_bucket_lifecycle_configuration` con `noncurrent_version_expiration` y `abort_incomplete_multipart_upload` (Grep).
4. CI: `terraform fmt -check -recursive` y `terraform validate` en `terraform-plan.yml` (los corre CI o el owner, nunca un agente, Convention Apply gate).
5. Owner tras el bootstrap: `aws s3api get-bucket-encryption --bucket <state-bucket>` devuelve `AES256`; `aws s3api get-bucket-versioning` devuelve `Enabled`; `aws budgets describe-budgets --account-id <id>` lista el budget de 10 USD (solo el owner ejecuta comandos AWS).
6. Criterio de Fase 1: una PR de prueba en `envs/dev` muestra el comentario de plan; tras el merge, el run de `terraform-apply.yml` termina en verde en el job `apply-dev`.

### Open Questions
1. ¿El IAM user del owner lo crea el bootstrap de Terraform? IaC only dice "nada se crea a mano"; si el owner lo crea en consola choca con la Convention, y si lo crea el bootstrap, el owner necesita credenciales previas para el primer apply (nunca access keys del root [IAM 1]; ver "Huecos comunes"). La research no lo trata.
2. ¿Qué pasa al acabar el plan Free? Sin decisión, el proyecto pierde la cuenta [AC 2, AC 3]; queda abierta la fila de `README.md:51`.
3. IDs numéricos `<OWNER-ID>` y `<REPO-ID>`: la research no los da; el owner los obtiene de GitHub (p. ej. `gh api repos/javiladino/skyroute --jq '.id, .owner.id'`).
4. Permisos IAM concretos de `ci` para Budgets y para `envs/*`: no investigados [IAM 11]; hasta que se definan, la permissions boundary y los Deny de Key Changes no se pueden dimensionar.
5. ¿Cuántos días de `noncurrent_version_expiration`? Decisión del owner: más días, más capacidad de restaurar el state y más almacenamiento (sin precio en la research).
6. Credenciales del primer apply del bootstrap y gaps de CI comunes: ver "Huecos comunes" en Recommendation.

## Proposal 2: Postura gestionada (Paid + Organizations + Identity Center)

### Overview
Activa IAM Identity Center con instancia de organización, lo que crea una Organization y pasa la cuenta a Paid [IAM 4, AC 7]; el owner entra con credenciales temporales de permission set. El state se cifra con SSE-KMS y clave de cliente, y CI usa dos roles: uno de solo lectura para `plan` en PR y otro para `apply` que solo confía en los environments. Maximiza la separación de privilegios a cambio de un cargo fijo por la clave y de perder los créditos de free tier.

**Ejes:** (a) SSE-KMS con clave de cliente; (b) Paid (forzado por Organizations); (c) Identity Center, instancia de organización; (d) dos roles.

### Key Changes
| Component | Change |
|-----------|--------|
| `infra/terraform/bootstrap/` | New: como Proposal 1, más `aws_kms_key` en eu-west-3 [IAM 15] y bucket con `kms_key_id`; dos roles `ci-plan` y `ci-apply` |
| Organization + Identity Center | New: instancia de organización [IAM 4]; permission set con sesión 1 h por defecto, máx. 12 h [IAM 8]; owner con `aws configure sso` [IAM 9]. Disponible en eu-west-3 [IAM 6] (endpoint sin verificar, § 3.5 ítem 8). Si se gestiona por Terraform o no: Open Question 2 |
| Trust de `ci-plan` | `StringEquals` `:sub` = `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:pull_request` [CI 4, CI 5]; `aud = sts.amazonaws.com` |
| Políticas de `ci-plan` | `s3:ListBucket`, Get en state, Get/Put/Delete en `.tflock` (plan toma el lock) [TL 5, IAM 11]; `kms:Decrypt` y, por el lock, `kms:Encrypt`/`kms:GenerateDataKey` (inferencia: [IAM 11] lista esos permisos para el backend con `kms_key_id`, no los atribuye al lock); lectura de recursos de `envs/*` (no investigada). El Put/Delete queda limitado al ARN exacto `<key>.tflock`, sin comodín. Alternativa: `plan -lock=false` sin escritura alguna (ver Trade-offs) |
| Trust de `ci-apply` | `StringEquals` `:sub` en la lista `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:environment:dev`, `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:environment:prod` [CI 13] |
| Políticas de `ci-apply` | Backend completo [TL 5], KMS [IAM 11], escritura de recursos de `envs/*`; permissions boundary [IAM 12] y Deny explícito sobre modificar los roles `ci-*`, el proveedor OIDC y la bucket policy del state. Permisos de Budgets y `envs/*` no investigados [IAM 11] |
| Environments `dev` y `prod` | New: "deployment branches: solo `main`" en ambos (research § 3.2) para que una PR no obtenga el `sub` `environment:*` [CI 13]; sub customization con `ref`/`job_workflow_ref` opcional (no comprobado) |
| Budget y lifecycle | `aws_budgets_budget` de 10 USD, avisos ACTUAL 50/80/100 % con `subscriber_email_addresses` [AC 18] (FORECASTED no dispara en cuenta nueva, research § 3.4); `aws_s3_bucket_lifecycle_configuration` con `noncurrent_version_expiration` (Open Question P1-5), delete markers expirados y `abort_incomplete_multipart_upload`; opcional Deny `s3:DeleteObject` sobre la clave del state |
| Workflows | Como Proposal 1 (incluido: sin `pull_request_target` con `id-token: write`, actions por SHA [CI 8], sin secretos en `*.tf`, nunca el plan binario como artifact); `terraform-plan.yml` usa el ARN de `ci-plan`, `terraform-apply.yml` el de `ci-apply`; environment `prod` con revisor requerido (ver "Huecos comunes" sobre "Prevent self-review") |

### Trade-offs
| Benefit | Risk |
|---------|------|
| Credenciales temporales para el owner, como prefiere AWS [IAM 1, IAM 8] | Activarlo pasa la cuenta a Paid y expira los créditos de free tier de inmediato [IAM 4, AC 7]; Paid es irreversible [AC 4] |
| Paid evita el cierre a los 6 meses [AC 2, AC 3, AC 5] | Pago por uso de lo que supere los créditos [AC 5]; con Organizations los créditos de free tier expiran de inmediato [IAM 4, AC 7], de modo que el colchón de créditos desaparece desde el día 1 (el plazo de 12 meses de [AC 12] deja de ser relevante; cálculo exacto no en la research) |
| Spend limit (desde 20 USD, avisos 50/75/90 % [AC 6]) como control adicional | Solo existe en la experiencia de alta nueva [AC 6]; esta cuenta está en eu-west-3, lo que apunta a la experiencia avanzada [AC 10] (inferencia), así que probablemente no aplica; igual que en P3. Comprobación del owner en Billing |
| SSE-KMS: control de acceso al state por política de clave, además del bucket (§ 3.3) | Clave ~1 USD/mes "prorrateado por hora", facturada aunque esté inactiva [IAM 16]: posible choque con No hourly-billed resources (Open Question 1); precio en eu-west-3 no comprobado (§ 3.5 ítem 11). Opción Bucket Key para reducir llamadas a KMS: no comprobado, no está en la research |
| `ci-plan` no tiene escritura sobre el state y `ci-apply` no confía en `pull_request`; con "deployment branches: solo `main`" en los environments, una PR tampoco obtiene el `sub` `environment:*` (research § 3.2, [CI 13]) | Dos trust policies y dos políticas que mantener; si `<OWNER-ID>/<REPO-ID>` son erróneos, fallan ambas [CI 5]. El control del environment es de GitHub, no de AWS; sin él, un job de PR con `environment: dev` asumiría `ci-apply` |
| `ci-plan` con Put/Delete solo en el ARN exacto `<key>.tflock` | `plan` necesita el lock con escritura; la alternativa `plan -lock=false` elimina la escritura pero pierde la exclusión frente a un apply concurrente (inferencia) |
| Organizations deja preparada una estructura multi-cuenta | La experiencia nueva no soporta Organizations ni Identity Center [AC 9]; para la experiencia avanzada no hay lista de servicios [AC 11]; no se sabe en cuál se creó la cuenta |

### Validation
1. Validaciones 1, 3 (con 3b–3f), 4 y 6 de Proposal 1, con la regla 2 cambiada: debe existir exactamente un `aws_kms_key` y ningún `aws_nat_gateway`/`aws_vpc`. Excepción en 3: la trust de `ci-plan` y la de `ci-apply` suman 3 coincidencias del patrón `sub` (1 + 2). Presupuesto de 10 USD, umbrales 50/80/100 y `subscriber_email_addresses` se comprueban con el Grep de 3e [AC 18]; lifecycle con 3f; environments con 3c.
2. File check: la trust de `ci-plan` contiene solo `:pull_request`; la de `ci-apply` solo `:environment:dev` y `:environment:prod` (Grep por rol).
3. File check: la política de `ci-plan` no contiene `s3:PutObject` sobre la clave del state; solo sobre el ARN exacto `<key>.tflock`, sin `*` (Grep `tflock` y `Resource.*\*`).
4. Owner: `aws s3api get-bucket-encryption` devuelve `aws:kms` con el ARN de la clave; `aws organizations describe-organization` responde; `aws sso login` y `aws sts get-caller-identity` con el perfil SSO (solo el owner).
5. CI (prueba negativa no destructiva, la ejecuta solo CI): un paso temporal en una PR de prueba, con credenciales de `ci-plan`, ejecuta `aws s3api put-object --bucket <state-bucket> --key <state-key> --body /dev/null` y se espera `AccessDenied`; el paso se retira antes del merge. Riesgo: si el permiso estuviera mal y el `put-object` tuviera éxito, sobrescribiría el state (Versioning permitiría restaurarlo [IAM 18]); alternativa de menor riesgo, no comprobada: usar una clave de prueba distinta con la misma política. No se ejecuta `terraform apply` desde la PR (Convention Apply gate).

### Open Questions
1. **¿Una clave KMS cae bajo No hourly-billed resources?** A favor: la research documenta que se prorratea por hora y se factura aunque esté inactiva [IAM 16], que es la letra de la Convention ("cobre por hora estando inactivo"). En contra: los ejemplos de la Convention (NAT Gateway, MWAA, Redshift, EMR) son cómputo o red, y la cuota es una tarifa mensual fija; la research registra la tensión sin evaluarla (tensión 6). Es un juicio del owner; si dice que sí, esta propuesta cambia el eje (a) a SSE-S3.
2. Organization e Identity Center: ¿los crea el bootstrap de Terraform o el owner en consola? IaC only no admite lo segundo; la research no documenta recursos Terraform para ello.
3. ¿En qué experiencia de alta se creó la cuenta? Si fue la nueva, Organizations e Identity Center no están soportados [AC 9].
4. "Prevent self-review" con un único owner: aplica a las tres propuestas; se trata en "Huecos comunes".
5. Lifecycle de versiones no actuales (días): igual que Open Question P1-5.

## Proposal 3: Intermedia (Paid sin Organizations, IAM user, roles separados)

### Overview
Pasa la cuenta a Paid para que no se cierre a los 6 meses, pero sin Organizations, de modo que no se activa la expiración inmediata de créditos que provoca Identity Center [IAM 4]. El owner usa un IAM user con MFA, el state va con SSE-S3 y CI separa `ci-plan` y `ci-apply` como en Proposal 2. Toma la separación de privilegios de CI de la postura gestionada y el coste cero de la mínima.

**Ejes:** (a) SSE-S3; (b) Paid; (c) IAM user con MFA; (d) dos roles.

### Key Changes
| Component | Change |
|-----------|--------|
| `infra/terraform/bootstrap/` | Como Proposal 1 (SSE-S3, sin `aws_kms_key`), pero con dos roles `ci-plan` y `ci-apply` |
| Trust de `ci-plan` | `StringEquals` `:sub` = `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:pull_request` [CI 4, CI 5] |
| Trust de `ci-apply` | `StringEquals` `:sub` en `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:environment:dev` y `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:environment:prod` [CI 13] |
| Environments `dev` y `prod` | New: "deployment branches: solo `main`" en ambos (research § 3.2), para que una PR no obtenga el `sub` `environment:*` y asuma `ci-apply` [CI 13]; sub customization con `ref`/`job_workflow_ref` opcional (no comprobado) |
| Políticas | `ci-plan`: `s3:ListBucket`, Get en state, Get/Put/Delete solo en el ARN exacto `<key>.tflock` (sin comodín; alternativa `plan -lock=false` sin escritura, ver Trade-offs de P2), lectura de recursos; `ci-apply`: backend completo [TL 5, IAM 11] y escritura de recursos (no investigada), con permissions boundary [IAM 12] y Deny explícito sobre modificar los roles `ci-*`, el proveedor OIDC y la bucket policy del state. Permisos de Budgets y `envs/*` no investigados [IAM 11] |
| Budget y lifecycle | `aws_budgets_budget` de 10 USD, avisos ACTUAL 50/80/100 % con `subscriber_email_addresses` [AC 18] (FORECASTED no dispara en cuenta nueva, research § 3.4); `aws_s3_bucket_lifecycle_configuration` con `noncurrent_version_expiration` (Open Question P1-5), delete markers expirados y `abort_incomplete_multipart_upload`; opcional Deny `s3:DeleteObject` sobre la clave del state |
| Cuenta AWS | Modified: mejora a Paid (paso del owner en Billing; irreversible [AC 4]); queda fuera de Terraform, Open Question 1 |
| Workflows | Como Proposal 2, con las mismas reglas de P1 (sin `pull_request_target` con `id-token: write`, actions por SHA [CI 8], sin secretos en `*.tf`, nunca el plan binario como artifact; repo público) |

### Trade-offs
| Benefit | Risk |
|---------|------|
| Paid: sin cierre a los 6 meses y acceso a todos los servicios [AC 2, AC 5] | Irreversible [AC 4]; pago por uso de lo que supere los créditos [AC 5]; los créditos restantes caducan a 12 meses de la creación [AC 12] |
| Sin Organizations no se dispara la expiración inmediata de créditos de [IAM 4] | No reconciliado: [AC 12] (caducidad a 12 meses) y [IAM 4] (expiración al crear la organización) no están conciliados en la research para una mejora a Paid sin Organizations; no comprobado qué pasa con los créditos al mejorar. El owner mantiene credenciales de larga duración [IAM 3] |
| Coste nuevo 0 por cifrado y Budgets [IAM 15, AC 13]; ninguna duda con No hourly-billed resources | Sin control de acceso por clave KMS al state en texto plano (§ 3.3) |
| La PR no puede aplicar: `ci-plan` sin escritura sobre el state, `ci-apply` no confía en `pull_request` y los environments solo despliegan desde `main` (research § 3.2, [CI 13]) | Dos trust policies que mantener, mismo riesgo de IDs que Proposals 1 y 2 [CI 5]; el control de ramas es de GitHub, no de AWS. `ci-plan` escribe el lock: ARN exacto `<key>.tflock` o `plan -lock=false` (trade-off de P2) |
| Spend limit desde 20 USD con avisos 50/75/90 % [AC 6] | Probablemente no aplica: solo existe en la experiencia nueva [AC 6] y la cuenta está en eu-west-3, lo que apunta a la experiencia avanzada [AC 10] (inferencia); igual que en P2. No debe contarse como beneficio hasta que el owner lo compruebe en Billing |

### Validation
1. Validaciones 1–4 y 6 de Proposal 1, incluidas 3b–3f (trust con 3 `sub` repartidos 1 + 2 entre los dos roles; budget de 10 USD, umbrales 50/80/100 y `subscriber_email_addresses` por Grep [AC 18]; lifecycle; environments con `deployment_branch_policy` en `main`; sin `StringLike`).
2. Validaciones 2, 3 y 5 de Proposal 2 (la 5 es la prueba negativa por `put-object`, ejecutada solo por CI).
3. Owner: `aws s3api get-bucket-encryption` devuelve `AES256`; la consola de Billing muestra plan Paid (solo el owner).

### Open Questions
1. La mejora a Paid es una acción de cuenta, no un recurso Terraform según la research; ¿queda fuera de IaC only como el IAM user o el owner la trata como excepción? La research no lo aclara.
2. ¿Cuándo mejorar a Paid? Antes de agotar créditos o de los 6 meses [AC 2]; el momento exacto es decisión del owner.
3. Mismas que Proposal 1, preguntas 1, 3, 4, 5 y 6.
4. ¿Qué ocurre con los créditos al mejorar a Paid sin Organizations? [AC 12] e [IAM 4] no lo concilian; el owner puede comprobarlo en Billing antes de mejorar.

## Recommendation

| Criteria | Proposal 1: Mínimo coste | Proposal 2: Postura gestionada | Proposal 3: Intermedia |
|----------|-----------|-----------|-----------|
| Fase 1: "Hecho cuando un PR muestra un plan de Terraform y el merge lo aplica." | Cumple: `terraform-plan.yml` comenta el plan [CI 10]; `apply-dev` en push a `main` | Cumple, igual | Cumple, igual |
| Convention Region | Cumple: provider y backend en eu-west-3; Budgets es global y exento [AC 15] | Cumple; la clave KMS va en eu-west-3 [IAM 15]; Identity Center en eu-west-3 [IAM 6] (endpoint sin verificar) | Cumple, como P1 |
| Convention IaC only | Pendiente parcial: budget, bucket, OIDC y rol por Terraform; abierto quién crea el IAM user (OQ P1-1) | Riesgo mayor: Organization e Identity Center sin vía Terraform documentada (OQ P2-2) | Pendiente: como P1 (IAM user, OQ P1-1) más la mejora a Paid fuera de Terraform (OQ P3-1) |
| Convention Apply gate | Cumple con reservas: plan en PR, apply en merge, prod con revisor (repo público, [CI 12]); pero el rol único confía en `pull_request` con permisos de apply (severidad alta), lo que choca con el espíritu de que solo el merge aplica; la Convention nombra "el rol de CI" en singular | Cumple; dos roles frente a "el rol de CI" en singular (pendiente del owner, ver nota); la PR no puede aplicar si los environments despliegan solo desde `main` (validación 3c) | Igual que P2: pendiente del owner la lectura del singular |
| Convention No hourly-billed resources | Cumple sin duda: ningún recurso con cargo por hora | Juicio del owner: clave KMS prorrateada por hora e inactiva facturada [IAM 16] (OQ P2-1) | Cumple sin duda |
| Coste mensual nuevo | 0 por cifrado y Budgets [IAM 15, AC 13] | ~1 USD/mes por clave [IAM 16] (precio en eu-west-3 no comprobado); Paid y créditos expirados de inmediato [IAM 4, AC 7] | 0 por cifrado y Budgets; Paid cobra lo que exceda créditos [AC 5]; caducidad de créditos no conciliada ([AC 12] frente a [IAM 4]) |
| Seguridad de CI | Rol único: la PR (incluido, sin comprobar, un fork [CI 16]) asume permisos de apply en un repo público; severidad alta | PR sin escritura al state; apply solo desde `main` vía environment; owner con credenciales temporales | Igual que P2 en CI; owner con credenciales largas [IAM 3] (MFA y credenciales temporales por CLI, ver Huecos comunes) |
| Continuidad de la cuenta | Free: cierre/suspensión a 6 meses o al agotar créditos [AC 2, AC 3] | Paid | Paid |
| Reversibilidad | Alta: nada irreversible | Baja: Paid irreversible [AC 4], créditos expiran [IAM 4] | Media: Paid irreversible [AC 4]; resto reversible |
| Complejidad | Baja: un rol, sin Organizations | Alta: Organization, Identity Center, KMS, dos roles | Media: dos roles |

**Cuándo elegir cada una.** Proposal 1 si el owner quiere aplazar la decisión de `README.md:51` y aceptar que la PR asuma el rol de apply durante la Fase 1. Proposal 2 si el owner prioriza mostrar una postura multi-cuenta con credenciales temporales y acepta perder los créditos de free tier y resolver la Open Question de KMS. Proposal 3 si quiere continuidad de cuenta y separación plan/apply sin cargos nuevos.

**Huecos comunes.** Ninguna propuesta resuelve con la research:
- IDs numéricos del `sub` inmutable: acción del owner `gh api repos/javiladino/skyroute --jq '.id, .owner.id'` (no comprobado).
- Permisos IAM de Budgets y de `envs/*` [IAM 11]; hasta definirlos no se dimensionan la permissions boundary [IAM 12] ni los Deny.
- Emisión de JWT a PRs de fork [CI 16]: prueba del owner con un fork (no comprobado).
- Orden budget/bucket frente a "primer recurso" (tensión 7) y Region frente a Budgets global (tensión 2), que las tres tratan como servicio exento según la propia Convention Region.
- Credenciales del primer apply del bootstrap: nunca access keys del root [IAM 1]. Opciones: IAM user con MFA en consola y credenciales temporales por CLI (`aws sts get-session-token --serial-number <mfa-arn> --token-code <código>`, ejecutado por el owner), o un rol que exija `aws:MultiFactorAuthPresent`. Comprobación del owner: `aws iam get-account-summary` (root con MFA y sin access keys).
- "Prevent self-review" con un único owner: dejarlo desactivado (activado nadie podría aprobar prod). La aprobación del environment es una pausa deliberada, no revisión de cuatro ojos. Desactivar el bypass de administradores en las reglas del environment (inferencia: la research no documenta ese ajuste).
- Repo público: el comentario de plan y cualquier artifact son públicos; sin secretos en `*.tf`/`tfvars`, `sensitive = true`, nunca el plan binario como artifact.
- Experiencia de alta (nueva o avanzada) y spend limit: comprobación del owner en Billing [AC 6, AC 9, AC 10].
- Nota: la Convention Apply gate dice que el bootstrap crea "el rol de CI"; P2 y P3 crean dos, y eso lo tiene que confirmar el owner, no esta propuesta.

**Recomendación:** Proposal 3 (sin cambio tras la revisión), porque evita que una PR asuma permisos de apply (P1, severidad alta) y que la cuenta caduque [AC 2], sin el juicio sobre KMS ni la pérdida inmediata de créditos de P2 [IAM 4, AC 7]. Cumple sin duda Region y No hourly-billed resources, pero no queda limpia en otras dos Conventions: IaC only tiene pendiente la mejora a Paid fuera de Terraform (OQ P3-1) y el IAM user (OQ P1-1), y Apply gate depende de que el owner acepte dos roles frente al singular "el rol de CI". Condiciones adicionales de P3: la mejora a Paid es irreversible [AC 4]; la caducidad de créditos no está conciliada ([AC 12] frente a [IAM 4]); el spend limit probablemente no aplica; y la protección de apply depende de "deployment branches: solo `main`" en los environments. La elección es del owner.

## Decision

- **Chosen:** Proposal 1: Mínimo coste y mínimo cambio de cuenta, modificada con los dos roles de CI de Proposal 3: `ci-plan` (trust `sub` `repo:javiladino@<OWNER-ID>/skyroute@<REPO-ID>:pull_request`, sin escritura sobre el state salvo el `.tflock`) y `ci-apply` (trust `sub` `...:environment:dev` y `...:environment:prod`, environments con deployment branches solo `main`). Resto como P1: SSE-S3, cuenta en Free, IAM user con MFA.
- **Reason (the user's):** "Quiero aplazar el paso a Paid. Es un ejercicio educativo que voy a utilizar para demostrar conocimientos en una entrevista de trabajo como data engineer." Sobre los roles, elegido en el gate: "P1 con dos roles", para cerrar el hallazgo de severidad alta del rol único sin coste ni paso a Paid.
- **Date:** 2026-11-12
