---
type: Research note
---

# Research note: terraform-layout

## Header

- Área: terraform-layout (topic `foundations`, Fase 1).
- Fecha: 2026-11-12.
- Alcance: estado del repo respecto a Terraform; patrones de layout de la documentación oficial de HashiCorp; backend S3 con `use_lockfile`; opciones documentadas para el bucket de estado; versiones vigentes. Solo hechos existentes, sin recomendaciones. Convenciones que atan a la nota: Region (eu-west-3, estado incluido), IaC only, Apply gate (no se ejecutó ningún comando terraform/AWS), Simple shell commands, Design write ownership.
- Revisión adversarial: no corrida en esta nota (la consolida el autor de research.md).

## Hallazgos

1. **Layout de módulos (HashiCorp).** La página "Standard module structure" describe "a file and directory layout we recommend for reusable modules". El root module es "the only required element"; los módulos anidados van bajo `modules/` y los ejemplos bajo `examples/`; los `module` de `examples/` usan como `source` la dirección que usaría un llamador externo. La página no da guía para un directorio `environments/` ni `envs/`; sus árboles de ejemplo solo muestran `modules/` y `examples/`. Fuente: https://developer.hashicorp.com/terraform/language/modules/develop/structure, consultado 2026-11-12.
2. **Backend S3: argumentos obligatorios.** `bucket` ("Name of the S3 Bucket"), `key` ("Path to the state file inside the S3 Bucket") y `region` ("AWS Region of the S3 Bucket and DynamoDB Table (if used)"). Fuente: https://developer.hashicorp.com/terraform/language/backend/s3, consultado 2026-11-12.
3. **`use_lockfile`.** Descrito como "Whether to use a lockfile for locking the state file. Defaults to `false`." Con `true` el bloqueo se hace con un objeto `.tflock` junto a la clave del estado. Fuente: misma página del punto 2, consultado 2026-11-12.
4. **Versión de introducción.** Terraform 1.10.0 (2024-11-27): "The s3 backend now supports S3 native state locking"; con DynamoDB a la vez, "locks will be acquired from both sources". Terraform 1.11.0 (2025-02-27): "S3 native state locking is now generally available". La página del backend S3 no indica la versión. Fuentes: https://github.com/hashicorp/terraform/blob/v1.10/CHANGELOG.md y https://github.com/hashicorp/terraform/blob/v1.11/CHANGELOG.md, consultado 2026-11-12.
5. **Permisos IAM del backend.** Sobre el archivo de lock (con `use_lockfile`): `s3:GetObject`, `s3:PutObject` y `s3:DeleteObject` (ejemplo `arn:aws:s3:::mybucket/path/to/my/key.tflock`). Sobre la clave del estado: `s3:GetObject` y `s3:PutObject`; "`s3:DeleteObject` is not required on the state file". La página lista además los permisos de listado del bucket; el extracto obtenido no los citó literalmente, ver Estado del repo / no verificado. Fuente: https://developer.hashicorp.com/terraform/language/backend/s3, consultado 2026-11-12.
6. **Estado de DynamoDB locking.** La página del backend S3 dice: "DynamoDB-based locking is deprecated and will be removed in a future minor version". Los argumentos S3 y DynamoDB pueden fijarse a la vez para migrar. El changelog 1.11.0 indica que los argumentos DynamoDB quedan deprecados. Fuentes: página del punto 2 y changelog v1.11, consultado 2026-11-12.
7. **Bloque backend y variables.** "A backend block cannot refer to named values (like input variables, locals, or data source attributes)". Fuente: https://developer.hashicorp.com/terraform/language/backend, consultado 2026-11-12.
8. **Configuración parcial.** "You do not need to specify every required argument in the backend configuration"; los valores faltantes se pasan por archivo, pares clave/valor en línea de comandos o prompts en `init`. `terraform init -backend-config=...` sirve para ello cuando los valores son dinámicos o sensibles. Fuentes: https://developer.hashicorp.com/terraform/language/backend y https://developer.hashicorp.com/terraform/cli/commands/init, consultado 2026-11-12.
9. **Cambio de backend y migración de estado (hecho documentado, base del chicken-and-egg).** "You can change your backend configuration at any time"; Terraform detecta el cambio y pide reinicializar; "When you change backends, Terraform gives you the option to migrate your state to the new backend"; se recomienda copiar antes `terraform.tfstate`. `init -migrate-state` "will attempt to copy existing state to the new backend" (con `-force-copy` suprime prompts); `init -reconfigure` "disregards any existing configuration, preventing migration of any existing state". Fuentes: páginas backend e init del punto 8, consultado 2026-11-12.
10. **Formas documentadas de crear el bucket de estado (opciones, sin elegir).** Lo que respaldan las páginas oficiales consultadas: (a) crear el bucket con un root module que usa estado local y después añadir el bloque `backend "s3"` y ejecutar `terraform init -migrate-state` (hecho 9); (b) usar `-backend-config` para pasar los valores del backend en `init` (hechos 7 y 8). Que el bucket se cree fuera de Terraform (consola/CLI de AWS) es posible, pero ninguna página oficial consultada lo describe como procedimiento de bootstrap. Las páginas consultadas no contienen un procedimiento oficial de bootstrap de bucket de estado; las opciones (a) y (b) son la combinación de los hechos 7 a 9.
11. **Versión estable de Terraform CLI.** v1.17.2, publicada 2026-11-11, marcada "Latest" en la página de releases; el changelog v1.17 lista una mejora y dos correcciones, sin notas del backend S3. Fuentes: https://github.com/hashicorp/terraform/releases y https://github.com/hashicorp/terraform/blob/v1.17/CHANGELOG.md, consultado 2026-11-12.
12. **Provider hashicorp/aws.** Última release v6.73.0, publicada 2026-11-11. Fuente: https://github.com/hashicorp/terraform-provider-aws/releases, consultado 2026-11-12. No se consultó registry.terraform.io.

## Estado del repo

- `Glob **/*.tf` en la raíz del repo: sin resultados. `Glob infra/**`: sin resultados. Ni `infra/` ni ningún archivo `.tf` existen el 2026-11-12.
- Ruta prevista, aún no creada: `infra/terraform/{bootstrap,modules,envs/{dev,prod}}/` (`AGENTS.md:23`, tabla "Previsto (aún no existe; no lo crees sin un plan aprobado)").
- No verificado: texto literal de los permisos de listado del bucket (`s3:ListBucket`) en la página del backend S3 (el extracto devuelto por la herramienta de fetch no los incluyó); versión de provider según registry.terraform.io; existencia de una guía oficial de bootstrap del bucket de estado.

## Fuentes

- https://developer.hashicorp.com/terraform/language/modules/develop/structure (consultado 2026-11-12)
- https://developer.hashicorp.com/terraform/language/backend (consultado 2026-11-12)
- https://developer.hashicorp.com/terraform/language/backend/s3 (consultado 2026-11-12)
- https://developer.hashicorp.com/terraform/cli/commands/init (consultado 2026-11-12)
- https://github.com/hashicorp/terraform/blob/v1.10/CHANGELOG.md (consultado 2026-11-12)
- https://github.com/hashicorp/terraform/blob/v1.11/CHANGELOG.md (consultado 2026-11-12)
- https://github.com/hashicorp/terraform/blob/v1.17/CHANGELOG.md (consultado 2026-11-12)
- https://github.com/hashicorp/terraform/releases (consultado 2026-11-12)
- https://github.com/hashicorp/terraform-provider-aws/releases (consultado 2026-11-12)
- `AGENTS.md:23`, `docs/design/CONTEXT.md` § Conventions
