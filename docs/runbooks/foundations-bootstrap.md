# Runbook: puesta en marcha de foundations

Pasos que ejecuta solo el owner. Ningún agente corre `terraform plan`, `terraform apply`, `terraform init -migrate-state` ni comandos `aws` (Convention Apply gate).

## Precondiciones

- El IAM user `skyroute-dev` existe, está en el grupo `admins` y tiene MFA.
- Los environments `dev` y `prod` del repo ya existen en la UI de GitHub.

## 1. Bootstrap local

1. `aws login` con `skyroute-dev`.
2. En `infra/terraform/bootstrap/`, copia `terraform.tfvars.example` a `terraform.tfvars` (gitignored) y pon tu email real en `budget_email` (el ejemplo usa el placeholder `tu-email@example.com`; nunca lo subas).
3. `terraform init`.
4. `terraform plan` y revisa: los 4 imports (user, grupo, attachment, membresía) deben salir en 0 cambios.
5. `terraform apply`. El state queda local; crea el bucket de state en eu-west-3, OIDC, roles de CI y el budget.

## 2. Migrar el state al bucket remoto

1. Crea `infra/terraform/bootstrap/backend.tf`:

   ```hcl
   terraform {
     backend "s3" {
       bucket       = "skyroute-tfstate-437266392155-eu-west-3"
       key          = "bootstrap/terraform.tfstate"
       region       = "eu-west-3"
       use_lockfile = true
     }
   }
   ```

2. `terraform init -migrate-state` y responde `yes`.
3. Compara `terraform state list` con el remoto y, si coincide, borra `terraform.tfstate` y `terraform.tfstate.backup` locales en `infra/terraform/bootstrap/`: contienen el email en claro.

## 3. Verificar y limpiar

1. Verifica el budget de Terraform: `aws budgets describe-budgets --account-id <account-id>`.
2. Borra el budget manual de 1 USD (consola).
3. Borra el bucket manual de state previo: `skyroute-tfstate-demo-437266392155-eu-north-1-an`, región `eu-north-1` (creado a mano, vacío, fuera de la Convention Region, no adoptado por Terraform). Solo el owner ejecuta estos comandos, uno por línea:

   ```bash
   # owner-only: debe salir vacío
   aws s3api list-object-versions --bucket skyroute-tfstate-demo-437266392155-eu-north-1-an --region eu-north-1
   ```

   ```bash
   # owner-only
   aws s3api delete-bucket --bucket skyroute-tfstate-demo-437266392155-eu-north-1-an --region eu-north-1
   ```

## 4. Configurar GitHub (UI)

En los environments `dev` y `prod`:

- Deployment branches: solo `main`.
- Bypass de administradores: desactivado.
- Solo en `prod`: required reviewer, con "Prevent self-review" desactivado (único owner: activado, nadie podría aprobar).

En Settings > Branches, branch protection de `main` con pull request requerida.

Comprueba la configuración con la verificación A10 del plan de foundations.

## 5. Prueba de CI

1. Abre un PR de prueba que toque `infra/terraform/envs/dev`: debe aparecer el comentario de plan y el job `static-checks` (checkov) en verde.
2. Al hacer merge, `terraform-apply.yml` aplica `dev` (`apply-dev` en verde).
3. Guarda la URL del comentario de plan y la del run de apply como evidencia.

## Re-apply de bootstrap

Sustituye `ci-apply` por `ci-apply-dev` y `ci-apply-prod` y crea las boundaries de workload `workload-boundary-dev` y `workload-boundary-prod`. Lo ejecuta solo el owner, con su identidad (`skyroute-dev`, Convention Bootstrap identity); ningún paso depende de un rol de CI. Se hace en dos re-applies, creando antes de destruir.

Notas del environment `prod` (S-H18): exige reviewers y restringe las ramas de despliegue a `main`; los `sub` de los roles de CI son de ID inmutable (`repo:javiladino@97758532/skyroute@1455233709:environment:<env>`) y cada rol acepta solo el de su entorno. Comprueba ambos environments con `gh api` (TS-O5) antes del primer re-apply.

### Orden de transición

1. **Primer re-apply (PR-B1 mergeada en `main`).** Desde `main` actualizado, `aws login` con `skyroute-dev` y, en `infra/terraform/bootstrap/`:
   1. `terraform init`
   2. `terraform plan -out=b1.tfplan`
   3. Revisa el plan: solo `create` de `ci-apply-dev`, `ci-apply-prod`, sus inline, `workload-boundary-dev`, `workload-boundary-prod` y el bloqueo público de cuenta, y `update in-place` de `ci-boundary` y de la inline de `ci-plan`. Ningún `destroy`: si aparece uno, no apliques.
   4. `terraform apply b1.tfplan`
   5. `terraform plan -detailed-exitcode` debe salir con código 0.

   `ci-apply` sigue intacto y es el rol que usa `terraform-apply.yml`.
2. **PR-W: cambio de workflow.** `terraform-apply.yml` pasa a asumir `role/ci-apply-dev` (job `apply-dev`) y `role/ci-apply-prod` (job `apply-prod`). Al mergear, el push a `main` lanza el apply (sin cambios en `envs/*`): guarda la URL del run con los dos jobs en verde. Si `terraform init` falla por la condición `s3:prefix = envs/<env>/` de `ListBucket`, revierte la PR-W y corrige la inline en bootstrap (otro re-apply).
3. **Segundo re-apply (PR-B2 mergeada: retirada de `ci-apply`).** Solo tras la evidencia del paso 2: `terraform plan -out=b2.tfplan`. Debe mostrar `destroy` de `aws_iam_role.ci_apply` y `aws_iam_role_policy.ci_apply`, y `update in-place` de las políticas que pierden el ARN de `ci-apply` en `DenyCiAndOidcChanges`; ningún `create` ni `destroy` de `ci-apply-dev`/`ci-apply-prod`. Aplica y comprueba `aws iam get-role --role-name ci-apply` (debe dar `NoSuchEntity`) y `terraform plan -detailed-exitcode` con código 0.

### Ventana sin rol de apply

En el camino normal no hay ventana: `ci-apply` existe hasta el segundo re-apply y los roles nuevos ya están creados. La ventana solo existe en la vuelta atrás del segundo re-apply (se destruyó `ci-apply`, los roles nuevos fallan y `ci-apply` aún no se ha recreado). Durante ella ningún push a `main` puede aplicar: el run de `terraform-apply.yml` falla en "Configure AWS credentials" sin tocar el state y se relanza al cerrar la ventana.

### Qué no mergear

- Entre el primer re-apply y el segundo: ninguna PR que toque `envs/*` (la del módulo `generator-landing`), porque `ci-apply` sigue abierto a T17 (un job de `dev` puede escribir el state de prod).
- Entre la PR-W y el segundo re-apply: cualquier PR que toque `bootstrap/` salvo la PR-B2.
- En la ventana de la vuelta atrás: nada salvo las PR de la propia vuelta atrás.

### Vuelta atrás

- **Primer re-apply a medias o con un plan inesperado:** no apliques; corrige la PR-B1 con otra PR. Si el apply quedó a medias, `terraform plan` en `bootstrap/` desde `main` y reaplica hasta 0 cambios; `ci-apply` no se toca en esta fase.
- **PR-W con el run en rojo:** revierte la PR-W (el workflow vuelve a `role/ci-apply`, que existe) y corrige la inline de `ci-apply-<env>` en bootstrap.
- **Segundo re-apply hecho y los roles nuevos fallan:** revierte la PR-B2 y reaplica `bootstrap/` para recrear `ci-apply` con la misma trust; después revierte la PR-W. Entre ambos pasos estás en la ventana sin rol de apply, y el run de `terraform-apply.yml` que dispara el merge de la reversión de PR-B2 se espera fallido (el workflow aún asume los roles nuevos).
- **Recrear `ci-apply` reabre T17:** el rol acepta `environment:dev` y `environment:prod` y escribe el state de prod. La PR del módulo no se mergea hasta un nuevo destroy de `ci-apply` (nueva PR-B2 y nuevo re-apply).

## Antes de cerrar la cuenta Free

La cuenta Free pierde sus recursos al terminar, incluido el bucket de state. Exporta el state antes (`terraform state pull > backup.tfstate` en cada root module) y guárdalo fuera de AWS.

Para borrar después el bucket de state (por ejemplo, al cerrar la cuenta Free): la política del bucket tiene un Deny de `s3:DeleteBucket` para Principal `"*"` y el recurso lleva `prevent_destroy`. Antes hay que quitar ese statement de la política y `prevent_destroy` del código.
