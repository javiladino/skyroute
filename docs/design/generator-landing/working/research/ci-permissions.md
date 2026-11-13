---
type: Research
---

# generator-landing: nota de área, permisos de CI

> **Fecha:** 2026-11-13. Nota de área de la etapa Research del topic `generator-landing`. Solo describe lo que existe hoy; no propone ni elige (método `reppit-research`). Review adversarial: no ejecutada en esta nota; la ejecuta el orquestador sobre el `research.md` consolidado.

## Alcance

Qué permiten hoy `ci-plan`, `ci-apply` y `ci-boundary`; dónde se definen y cómo se cambian; qué necesitarían leer (plan) y crear (apply) los recursos de la Fase 2 (bucket de datos con `landing/`, Lambda, schedule de EventBridge, rol de ejecución IAM, log groups de CloudWatch) en `envs/dev` y `envs/prod`; el riesgo de escalada por `iam:CreateRole` e `iam:PassRole`; el acotado por prefijo de nombre y por región; y las implicaciones para checkov y tflint.

Fuera de alcance: la elección entre opciones, la lista final de acciones IAM, y el diseño de los recursos de la Fase 2.

Reglas vigentes que no se reabren: Ruling "Foundations design" (dos roles de CI), Convention "Bootstrap identity" (mínimo privilegio exigido a los roles de CI y a toda identidad no humana), Convention "IaC only" y Convention "Region".

## Hechos

### H1. Qué permite `ci-boundary` hoy

Fuente: `infra/terraform/bootstrap/ci_roles.tf:12-100`.

- Allow: solo `s3:ListBucket` sobre el bucket de state (`:20-24`) y `s3:GetObject`/`PutObject`/`DeleteObject` sobre cuatro ARN exactos: `envs/dev/terraform.tfstate`, su `.tflock`, `envs/prod/terraform.tfstate` y su `.tflock` (`:25-35`). No hay ningún otro servicio en el Allow (ni Lambda, ni Scheduler, ni Logs, ni IAM, ni S3 fuera del bucket de state).
- Deny: `iam:*` sobre `user/skyroute-dev` y `group/admins` (`:36-44`); `iam:*` sobre los roles `ci-plan`, `ci-apply` y el proveedor OIDC (`:45-54`); `iam:CreateRole` e `iam:PutRolePermissionsBoundary` con `StringNotEquals iam:PermissionsBoundary = <ARN ci-boundary>` sobre `Resource = "*"` (`:55-65`); `iam:DeleteRolePermissionsBoundary` sobre `*` (`:66-71`); `iam:CreatePolicyVersion`, `SetDefaultPolicyVersion`, `DeletePolicy`, `DeletePolicyVersion` sobre el ARN de `ci-boundary` (`:72-82`); y cinco acciones S3 de protección sobre el bucket de state (`:83-97`).
- Efecto: la AWS documenta que los permisos efectivos de una entidad con boundary son la intersección entre sus políticas de identidad y la boundary, y que la boundary no concede permisos por sí sola (https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html, recuperado 2026-11-13). Con el Allow actual de la boundary (`:20-35`), cualquier Allow que se añada a `ci-plan` o `ci-apply` sobre otro servicio no tiene efecto mientras la boundary no lo incluya.

### H2. Qué permite `ci-plan` hoy

Fuente: `ci_roles.tf:104-224`.

- Rol con `permissions_boundary = ci-boundary` (`:107`). Trust: `sts:AssumeRoleWithWebIdentity`, `aud = sts.amazonaws.com` y `sub` exacto `...:pull_request` (`:109-126`, `sub` en `:121`).
- Política inline `ci-plan-backend` (`:129-224`): `s3:ListBucket` en el bucket de state (`:136-141`); `s3:GetObject` en las claves `envs/dev` y `envs/prod` del state (`:142-150`); `GetObject`/`PutObject`/`DeleteObject` en los dos `.tflock` (`:151-159`). Nunca la clave `bootstrap/` (A4c del plan: 0 coincidencias).
- Los mismos Deny que la boundary (`:160-221`).
- No tiene ninguna acción de lectura sobre S3 (fuera del state), Lambda, EventBridge Scheduler, IAM ni CloudWatch Logs. Hoy `envs/dev` y `envs/prod` no tienen recursos: solo backend y provider (`docs/design/foundations/current/plan.md:88`, `:276`).

### H3. Qué permite `ci-apply` hoy

Fuente: `ci_roles.tf:228-351`.

- Rol con `permissions_boundary = ci-boundary` (`:231`). Trust con `aud = sts.amazonaws.com` y `sub` en `environment:dev` o `environment:prod` (`:233-253`, `sub` en `:245-248`).
- Política inline `ci-apply-backend` (`:256-351`): `s3:ListBucket` en el bucket de state (`:263-268`); `s3:GetObject`/`PutObject` en las claves `envs/dev` y `envs/prod` (`:269-277`; sin `DeleteObject` sobre la clave de state); `GetObject`/`PutObject`/`DeleteObject` en los `.tflock` (`:278-286`).
- Los mismos Deny (`:287-348`). No hay permisos sobre recursos de `envs/*`.
- El plan de Fase 1 lo deja como pendiente explícito: "no se inventan listas de acciones", la boundary "se amplía cuando una fase posterior añada recursos" (`foundations/current/plan.md:276`; también `:61-62`).

### H4. Dónde se definen y cómo se cambian

- Boundary, ambos roles, sus políticas, el proveedor OIDC y el bucket de state están en `infra/terraform/bootstrap/` (`ci_roles.tf`, `oidc.tf`, `state_bucket.tf`). Cambiar los permisos de CI es cambiar `bootstrap/`.
- La Convention "Apply gate" fija que el owner aplica `bootstrap/` desde su máquina; su texto habla de aplicarlo "una vez" y de migrarlo al bucket de state (`docs/design/CONTEXT.md:45`). El runbook cubre esa aplicación inicial: apply local, `backend.tf` con clave `bootstrap/terraform.tfstate`, `init -migrate-state` (`docs/runbooks/foundations-bootstrap.md:10-34`). No encontré en el runbook una sección para re-aplicar `bootstrap/` tras un cambio posterior (ver No verificado).
- CI no puede cambiar `bootstrap/`:
  - `terraform-plan.yml` ejecuta el job `plan` con `working-directory: infra/terraform/envs/${{ matrix.env }}` y matriz `[dev, prod]` (`.github/workflows/terraform-plan.yml:25-31`); el apply usa los jobs `apply-dev` y `apply-prod` (`.github/workflows/terraform-apply.yml:22`, `:58`). La verificación A5b del plan exige 0 coincidencias de `bootstrap` en los workflows (`foundations/current/plan.md:206`).
  - Ninguno de los dos roles tiene acceso a la clave `bootstrap/terraform.tfstate` (`ci_roles.tf:30-33`, `:147-148`, `:274-275`) y ambos tienen Deny `iam:*` sobre `ci-plan`, `ci-apply` y el OIDC (`:45-54`, `:169-178`, `:296-305`), y Deny de nueva versión sobre `ci-boundary` (`:72-82`).
- Los roles se asumen con `role-to-assume: arn:aws:iam::437266392155:role/ci-plan` / `ci-apply` y `aws-region: eu-west-3` (`terraform-plan.yml:50-51`; `terraform-apply.yml:44-45`, `:80-81`).
- Consecuencia de H1 + H4: el cambio de permisos de la Fase 2 requiere un cambio simultáneo en la boundary (techo) y en la política inline de cada rol (concesión), ambos en `bootstrap/ci_roles.tf`, y un apply local del owner antes de que un PR de `envs/*` pueda planificar o aplicar los recursos nuevos.

### H5. Qué necesita `ci-plan` para planificar los recursos de Fase 2

`terraform plan` hace refresh de cada recurso del state y lee la configuración remota. Los recursos previstos son los de la Fase 2 (brief del orquestador). Lectura necesaria por servicio (nivel de familia de acciones; la lista exacta de acciones depende de la versión del provider y no se verificó, ver No verificado):

| Servicio | Recursos previstos | Lectura de refresh (familia) |
|----------|--------------------|------------------------------|
| S3 (bucket de datos) | bucket, versioning, cifrado, public access block, ownership, lifecycle, policy | `s3:GetBucket*`, `s3:GetEncryptionConfiguration`, `s3:GetLifecycleConfiguration`, `s3:GetAccelerateConfiguration`, `s3:GetReplicationConfiguration`, `s3:ListBucket` sobre el ARN del bucket de datos |
| Lambda | función (y permisos de invocación) | `lambda:GetFunction`, `GetFunctionConfiguration`, `GetFunctionCodeSigningConfig`, `GetPolicy`, `ListVersionsByFunction`, `ListTags` |
| EventBridge Scheduler | schedule (y grupo, si se usa) | `scheduler:GetSchedule`, `GetScheduleGroup`, `ListTagsForResource` |
| IAM | rol de ejecución, política inline/adjunta | `iam:GetRole`, `GetRolePolicy`, `ListRolePolicies`, `ListAttachedRolePolicies`, `ListInstanceProfilesForRole` |
| CloudWatch Logs | log group | `logs:DescribeLogGroups`, `ListTagsForResource` (o `ListTagsLogGroup`) |

Hechos adicionales:
- `ci-plan` ya lee el state de `prod` (`ci_roles.tf:146-149`); el state de recursos nuevos contendrá sus atributos.
- El `sub` de `ci-plan` es `pull_request`, que cualquier PR del repo puede emitir (`ci_roles.tf:121`; el repo es público, `foundations/current/plan.md:15`). Emisión de JWT a PR de fork: no comprobada (`plan.md:277`).
- Para `describe`/`list` de varios servicios la acción de IAM no admite restricción por recurso; el comportamiento exacto por acción no se verificó.

### H6. Qué necesita `ci-apply` para crear los recursos de Fase 2

Escritura por servicio (familia de acciones; sin lista cerrada):

| Servicio | Escritura (familia) |
|----------|---------------------|
| S3 | `s3:CreateBucket`, `s3:PutBucket*` (versioning, encryption, public access block, ownership, lifecycle, policy), `s3:PutObject` si el despliegue sube el objeto de código, y lo de lectura de H5 |
| Lambda | `lambda:CreateFunction`, `UpdateFunctionCode`, `UpdateFunctionConfiguration`, `AddPermission`, `RemovePermission`, `TagResource`, `DeleteFunction` |
| Scheduler | `scheduler:CreateSchedule`, `UpdateSchedule`, `DeleteSchedule`, `TagResource` |
| IAM | `iam:CreateRole`, `PutRolePolicy`/`AttachRolePolicy`, `DeleteRole*`, `TagRole`, `iam:PassRole` |
| Logs | `logs:CreateLogGroup`, `PutRetentionPolicy`, `DeleteLogGroup`, `TagResource` |

Hechos existentes que afectan a esta lista:
- El Deny de `ci_roles.tf:56-65` ya obliga a que todo `iam:CreateRole` de CI lleve la boundary `ci-boundary`; hoy ningún Allow de CI concede `iam:CreateRole`, de modo que el Deny nunca se ha ejercido.
- Los Deny de `ci_roles.tf:83-97` sobre el bucket de state aplican solo al ARN del bucket de state y no a un bucket de datos.
- El `Resource = "*"` está permitido solo en Deny (Ruling del owner 2026-11-13, `foundations/current/plan.md:67`; verificaciones A4 y A4a, `:199-200`). Los Allow de hoy llevan ARN exactos y 0 `*`; las acciones de lectura/lista que no aceptan ARN de recurso (por ejemplo, `logs:DescribeLogGroups`, según mi conocimiento, no verificado) chocan con esa regla (ver Opciones y Tensiones).
- La Fase 2 crea un rol de ejecución de Lambda y, si se usa EventBridge Scheduler, un rol para que el schedule invoque la Lambda: ambos se crean con `iam:CreateRole` y se pasan con `iam:PassRole`. Los servicios receptores serían `lambda.amazonaws.com` y `scheduler.amazonaws.com` (inferencia del diseño previsto; el diseño de Fase 2 no está decidido).

### H7. Riesgo de escalada por `iam:CreateRole` e `iam:PassRole`

- Una entidad con `iam:CreateRole` + `iam:PutRolePolicy`/`AttachRolePolicy` + `iam:PassRole` puede crear un rol con más permisos que ella y pasarlo a un servicio. La AWS lo advierte: hay que asegurarse de que un usuario no pase un rol con más permisos de los que se quiere que tenga (https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html, recuperado 2026-11-13).
- Defensas ya presentes en `bootstrap/`:
  - Exigir la boundary al crear roles o ponerles boundary (`ci_roles.tf:55-65`), con `iam:PermissionsBoundary` (clave de condición de ARN que comprueba que la política indicada está asociada como boundary del principal, https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html, recuperado 2026-11-13).
  - Impedir quitar la boundary (`:66-71`) y reescribir `ci-boundary` (`:72-82`).
  - Impedir tocar `ci-plan`, `ci-apply`, el OIDC y la identidad del owner (`:36-54`).
- Qué NO acota hoy ninguna defensa: el nombre o el path de los roles que CI puede crear (no hay Allow de IAM; el Deny `:55-65` usa `Resource = "*"`), ni qué roles puede pasar CI, ni a qué servicio. Un rol creado con `ci-boundary` hereda como techo el Allow de la boundary (H1), que hoy no concede acciones de servicios de la Fase 2; si la boundary se ensancha para CI, el techo de los roles creados por CI se ensancha igual, porque es la misma política `ci-boundary`.
- El rol de ejecución de la Lambda también tendría que llevar `ci-boundary` para pasar el Deny `:55-65`. La boundary actual solo permite S3 de state: con ella, un rol de ejecución no podría hacer nada útil (escribir en `landing/`, Logs). Esto es un hecho derivado de la intersección de H1, no una decisión.
- Claves de condición documentadas para acotar `iam:PassRole`: `iam:PassedToService` (operadores de string; especifica el principal de servicio al que puede pasarse el rol; solo aplica a `PassRole`; incluye solo el servicio final que asume el rol; "algunos servicios no soportan esta clave"), https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html, recuperado 2026-11-13. El ARN del recurso de `iam:PassRole` admite comodín de prefijo de nombre (`role/EC2-roles-for-XYZ-*` en el ejemplo de https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html, recuperado 2026-11-13). La misma página desaconseja controlar `PassRole` con tags y `ResourceTag` ("no tiene resultados fiables").
- `iam:PassRole` no es una llamada de API y no genera evento en CloudTrail; se audita en el evento que crea el recurso (misma página de PassRole).

### H8. Acotado por prefijo de nombre y por región

- Prefijo de nombre: los Deny actuales protegen por ARN exacto (`ci_roles.tf:41-42`, `:50-52`, `:81`), no por prefijo. Los ARN de IAM llevan el nombre (y path) del rol, por lo que `Resource = arn:aws:iam::<cuenta>:role/<prefijo>-*` es expresable; el ejemplo oficial lo hace para `PassRole`.
- Convention Region: todo recurso regional en `eu-west-3`; IAM y Budgets, globales, están exentos (`docs/design/CONTEXT.md:42`). El provider usa `eu-west-3` y los workflows `aws-region: eu-west-3` (`terraform-plan.yml:13`, `:51`; `terraform-apply.yml:45`).
- `aws:RequestedRegion`: clave global que compara la región llamada en la petición con la indicada en la política. Los servicios globales como IAM tienen un único endpoint situado en us-east-1, de modo que una política que deniegue todo salvo una región distinta a us-east-1 hace fallar las llamadas a IAM; el workaround documentado es `NotAction` con `Deny`. La clave controla el endpoint invocado, no el impacto de la operación: para S3, `s3:CreateBucket` en otra región se controla con `s3:LocationConstraint` (https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html, sección aws:RequestedRegion, recuperado 2026-11-13).
- Hoy ninguna política de CI usa `aws:RequestedRegion` (Grep en `infra/terraform`: 0 coincidencias; tampoco hay `iam:PassRole`, y `iam:CreateRole` solo aparece en los tres Deny, `ci_roles.tf:58`, `:182`, `:309`). El único acotado de región actual es el provider y el `aws-region` de los workflows.
- Prefijo de recursos del state: los ARN exactos del state son literales, sin prefijo (`ci_roles.tf:30-33`).

### H9. checkov y tflint

- checkov corre en el job `static-checks` de `terraform-plan.yml` sobre `infra/terraform` completo, es decir incluye `bootstrap/` y los `envs/*` (`terraform-plan.yml:127-131`; versión 3.4.5, `--framework terraform`). El job tiene `permissions: contents: read` y no asume ningún rol AWS (`:114-115`).
- Omisiones existentes, siempre en línea con `#checkov:skip=<ID>:<motivo>`: CKV_AWS_273 y 274 en `owner_user.tf:26`, `:37` (Convention "Bootstrap identity"); CKV_AWS_145, 144, 18 y CKV2_AWS_62 en `state_bucket.tf:5-8`. La omisión por recurso es el patrón vigente; la Convention "Bootstrap identity" dice que nunca se omite en todo el repo (`CONTEXT.md:54`).
- La política de `ci_roles.tf` se escribe con `jsonencode(...)` (`:16`, `:133`, `:260`), no con `aws_iam_policy_document`. Qué reglas de checkov de IAM evalúan ese formato: no verificado.
- tflint: la config está en `infra/terraform/.tflint.hcl` (preset `recommended` del plugin terraform; plugin `aws` 0.50.0, `:5-14`). En CI solo corre sobre `envs/dev` y `envs/prod`, no sobre `bootstrap/` (`terraform-plan.yml:138-145`).
- Las reglas de checkov específicas de S3, Lambda, Logs e IAM que podrían saltar con los recursos de Fase 2 no se ejecutaron: checkov no está instalado localmente y el owner quiere que corra en CI (`foundations/current/plan.md:20`). Lista orientativa de IDs en No verificado.
- La omisión CKV_AWS_145 (`state_bucket.tf:5`) cita la Convention "No hourly-billed resources": la ausencia de KMS ya se omite por recurso en el repo.

## Opciones observadas

Solo se describen; no se recomienda ninguna. Cada eje es independiente de los demás.

### O1. Dónde crece el techo (boundary)

- **O1a.** Ampliar `ci-boundary` con Allow por servicio de la Fase 2 (S3 del bucket de datos, Lambda, Scheduler, Logs, IAM acotado) y ampliar las dos políticas inline en la misma medida. Cambia `bootstrap/`; efecto: la boundary es también el techo de los roles que CI crea (H1, H7).
- **O1b.** Boundary distinta para los roles que CI crea (p. ej. `workload-boundary`) y `ci-boundary` solo para los roles de CI. Obliga a cambiar la condición `iam:PermissionsBoundary` de los Deny `ci_roles.tf:55-65` (hoy fija `ci-boundary`) y los Deny sobre la política (`:72-82`), que protegen solo `ci-boundary`. Añade una política gestionada nueva a `bootstrap/`.
- **O1c.** Un Allow condicionado en `ci-apply` (`iam:CreateRole` solo con la boundary del workload y solo sobre `role/<prefijo>-*`) y los Deny actuales sin cambio.

### O2. Cómo se acota IAM (CreateRole y PassRole)

- Prefijo o path de nombre en el `Resource` de `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy`, `iam:DeleteRole*`, `iam:TagRole` y `iam:PassRole` (H8). El prefijo sirve de contrato con el Terraform de `envs/*` (nombres de roles).
- `iam:PassRole` con `Resource` por prefijo y `Condition` `StringEquals iam:PassedToService` (`lambda.amazonaws.com`, `scheduler.amazonaws.com`) (H7).
- Condición `iam:PermissionsBoundary` en el Allow de `iam:CreateRole`/`iam:PutRolePermissionsBoundary` (además del Deny que ya existe, `ci_roles.tf:55-65`), o solo el Deny actual.
- Acotar qué políticas pueden adjuntarse a los roles creados (`iam:PolicyARN` en `AttachRolePolicy`; la clave no se verificó) o permitir solo políticas inline (`PutRolePolicy`).
- Deny nuevo que proteja `role/<prefijo>-*` contra el borrado de su boundary: ya cubierto por `iam:DeleteRolePermissionsBoundary` sobre `*` (`ci_roles.tf:66-71`).

### O3. Cómo se acotan S3, Lambda, Scheduler y Logs

- ARN por prefijo de nombre (`skyroute-<env>-*`) para bucket, función, schedule y log group; el nombre incluye el entorno para que `ci-apply` de dev pueda diferenciarse de prod (ambos entornos asumen el mismo rol `ci-apply`, `ci_roles.tf:245-248`; un solo rol cubre los dos entornos).
- Dos juegos de ARN dentro del mismo rol (dev y prod) o, fuera del Ruling "Foundations design", roles separados por entorno (el Ruling fija dos roles, `ci-plan` y `ci-apply`; no se reabre).
- Acciones de lista/describe sin ARN de recurso (p. ej. `Describe*` de Logs, `s3:ListAllMyBuckets`): `Resource = "*"` con Allow, o limitarlas por `aws:RequestedRegion`, o prescindir de ellas si el provider no las exige (no verificado). La regla vigente permite `*` solo en Deny (`foundations/current/plan.md:67`).
- Condición `aws:RequestedRegion = eu-west-3` en los Allow regionales; IAM, global, se queda fuera de esa condición (H8) o usa `NotAction` con Deny.
- Separar quién lee y quién escribe: lectura (`Get*`, `List*`, `Describe*`) en `ci-plan`, escritura solo en `ci-apply`, ambas dentro de la boundary.

### O4. Cómo se aplica el cambio en `bootstrap/`

- **O4a.** El owner re-aplica `bootstrap/` en local una vez por cada ampliación de permisos (Convention "Apply gate": el owner aplica el bootstrap desde su máquina). La Fase 2 y las siguientes podrían requerir varias ampliaciones; cada una es un apply local del owner.
- **O4b.** Ampliar todos los permisos de CI de la Fase 2 en un único cambio de `bootstrap/` antes de crear los recursos (un solo apply local por fase).
- **O4c.** Hoy los roles de CI no tocan `bootstrap/` (H4). Cualquier mecanismo en que CI aplique `bootstrap/` choca con el texto de la Convention "Apply gate" y con la verificación A5b; se lista porque existe como patrón general, no como opción abierta bajo las Conventions actuales.

### O5. checkov y tflint

- Omisiones por recurso con `#checkov:skip=<ID>:<motivo>` (patrón vigente en `state_bucket.tf:5-8` y `owner_user.tf:26`, `:37`) para reglas sobre KMS, replicación, logging y DLQ/VPC de Lambda que no encajan con las Conventions.
- Cumplir la regla en vez de omitirla cuando no entra en conflicto con una Convention (retención de logs, X-Ray, concurrencia reservada, etc.; lista en No verificado).
- Extender `tflint` en CI a `bootstrap/` (hoy solo `envs/dev` y `envs/prod`, `terraform-plan.yml:142`) o dejarlo como está.
- Escribir las políticas de la Fase 2 con `aws_iam_policy_document` o con `jsonencode` (el patrón actual, `ci_roles.tf:16`).

## Tensiones con Conventions

1. **Apply gate vs. re-aplicar `bootstrap/`.** La Convention habla de que el owner aplica el bootstrap "una vez" (`CONTEXT.md:45`); la Fase 2 obliga a un segundo apply local (H4). El texto no distingue entre aplicación inicial y reaplicaciones. El runbook cubre solo la inicial (`foundations-bootstrap.md:10-34`).
2. **Bootstrap identity (mínimo privilegio en CI) vs. lectura sin ARN.** La Convention exige mínimo privilegio a los roles de CI (`CONTEXT.md:54`); el refresh de varios servicios puede requerir acciones que no admiten ARN de recurso, y la regla de foundations permite `Resource = "*"` solo en Deny (`foundations/current/plan.md:67`, A4/A4a `:199-200`). Si una acción lo requiere hay tensión entre ambas; qué acciones concretas lo exigen no está comprobado.
3. **Bootstrap identity vs. `iam:CreateRole` en CI.** Conceder a CI crear roles con política propia es la capacidad de mayor riesgo de H7; la Convention exige mínimo privilegio y el Ruling mantiene dos roles que cubren dev y prod (un mismo rol para ambos entornos, `ci_roles.tf:245-248`), de modo que el acotado por entorno solo puede ir en el nombre del recurso.
4. **Region vs. IAM global.** `aws:RequestedRegion = eu-west-3` no se puede aplicar tal cual a IAM (endpoint único en us-east-1, H8). La Convention exime a IAM de la regla de región (`CONTEXT.md:42`).
5. **IaC only / Apply gate vs. nuevos roles.** Los roles que crea el Terraform de `envs/*` son recursos IaC aplicados por CI al merge (permitido), pero deben cumplir el Deny `ci_roles.tf:55-65` (llevar `ci-boundary`) o el cambio que lo modifique pasa por bootstrap (O1b).
6. **No hourly-billed resources vs. reglas checkov habituales.** Algunas reglas de checkov para S3, Lambda y Logs piden KMS (CKV_AWS_145, 158, 173 en mi conocimiento, no verificado); `aws_kms` está vetado por la verificación N1 (`foundations/current/plan.md:237`). El patrón vigente es la omisión por recurso con motivo (`state_bucket.tf:5`).
7. **Simple shell commands / Apply gate vs. verificar permisos.** Ningún agente ejecuta `plan`, `apply` ni comandos AWS (`CONTEXT.md:45`), así que la suficiencia de los permisos de CI solo se comprueba con el run de CI o con salida que aporte el owner (Convention "Verification ownership", `CONTEXT.md:53`).

## Preguntas para el owner

1. ¿La Convention "Apply gate" ("una vez") incluye re-aplicaciones del bootstrap por ampliación de permisos de CI, o hace falta aclarar su texto? ¿Se prefiere un apply por fase (O4b) o por ampliación (O4a)?
2. ¿Los roles que crea CI (el rol de ejecución de la Lambda y el del schedule) comparten la boundary `ci-boundary` (O1a) o usan una boundary propia (O1b)? Hoy el Deny exige exactamente `ci-boundary` (`ci_roles.tf:61-63`).
3. ¿Qué prefijo de nombre llevan los recursos y los roles de la Fase 2 (p. ej. `skyroute-<env>-...`)? No existe hoy ningún prefijo definido en el repo para recursos de `envs/*`.
4. ¿Se acepta `Resource = "*"` en un Allow de solo lectura (acciones sin ARN de recurso) si la lectura lo exige, o la regla "0 `*` en Allow" (`foundations/current/plan.md:67`) se mantiene y se prescinde de esas acciones?
5. ¿Los dos entornos (dev y prod) comparten un mismo juego de ARN/prefijos en `ci-apply`, o se diferencian por nombre (`...-dev-*`, `...-prod-*`)? El rol es uno solo (`ci_roles.tf:245-248`).
6. ¿Se permite que `ci-plan` (sub `pull_request`) lea configuración de Lambda y IAM? Hoy ese sub puede emitirlo cualquier PR del repo público (H5); el comportamiento ante forks está por comprobar (`plan.md:277`).
7. ¿checkov y tflint: se prefiere omitir por recurso o cumplir las reglas, y se amplía tflint a `bootstrap/` (O5)?

## No verificado

1. Lista exacta de acciones de lectura que el provider `hashicorp/aws` v6.x usa en el refresh de S3, Lambda, Scheduler, IAM y Logs (H5, H6): las tablas son familias de acciones por conocimiento general, no leídas de la documentación del provider ni de un plan real.
2. Qué acciones de lista/describe no admiten restricción por recurso (p. ej. Logs `Describe*`): no consultado en la Service Authorization Reference (la página `list_awsidentityandaccessmanagementiam.html` devolvió solo el título en WebFetch).
3. Comportamiento exacto de `StringNotEquals` sobre `iam:PermissionsBoundary` cuando la clave no está en la petición (el Deny `ci_roles.tf:55-65` depende de que, al crear un rol sin boundary, el Deny aplique): no consultado en la doc de operadores de condición.
4. Qué claves de condición admite `iam:CreateRole` en la Service Authorization Reference y si `iam:PolicyARN` acota `AttachRolePolicy`: no confirmado.
5. Si Lambda y EventBridge Scheduler soportan `iam:PassedToService` (la doc dice que "algunos servicios no soportan esta clave"): no confirmado.
6. Cómo se comporta la clave `aws:RequestedRegion` con Lambda, Scheduler y Logs frente a la creación de recursos (las llamadas regionales sí llevan la región; las de IAM van a us-east-1): solo leído de la doc general de condition keys, no probado.
7. Qué reglas de checkov saltarían con los recursos de la Fase 2: IDs orientativos de conocimiento previo, no ejecutados (S3: CKV_AWS_18, 144, 145; Lambda: CKV_AWS_50, 115, 116, 117, 173, 272; Logs: CKV_AWS_158, 338; IAM: CKV_AWS_287, 288, 289, 290, 355).
8. Qué reglas de checkov de IAM evalúan una política escrita con `jsonencode` en un `aws_iam_policy` / `aws_iam_role_policy` (H9).
9. Si el runbook tiene una sección para re-aplicar `bootstrap/` tras cambios: solo vi las líneas 3-34 y 62-68 (coincidencias de Grep, limitado a 50 resultados); no leí el archivo completo.
10. Tamaño máximo de una política gestionada y de políticas inline de un rol frente al crecimiento de `ci-boundary` y de las políticas de `ci_roles.tf`: no consultado.
11. Emisión del JWT a PR desde forks (hereda `plan.md:277`): no comprobado.
12. Que `terraform-apply.yml` no contenga referencias a `bootstrap/` más allá de lo que mostró Grep (0 coincidencias de `bootstrap` en los workflows, resultado del Grep de esta sesión; contenido completo del archivo no leído).
13. Estado real del bootstrap aplicado en la cuenta (políticas desplegadas frente al `.tf`): no se ejecutó ningún comando AWS (Convention "Apply gate"); las referencias son al código.
