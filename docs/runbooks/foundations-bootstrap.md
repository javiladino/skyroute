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

## Antes de cerrar la cuenta Free

La cuenta Free pierde sus recursos al terminar, incluido el bucket de state. Exporta el state antes (`terraform state pull > backup.tfstate` en cada root module) y guárdalo fuera de AWS.
