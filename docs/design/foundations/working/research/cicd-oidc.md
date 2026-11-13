---
type: Research note
---

# Research note: cicd-oidc (topic foundations)

## Header

- Tarea: documentar qué existe hoy para CI/CD con GitHub Actions y OIDC hacia AWS (Fase 1, topic `foundations`).
- Fecha: 2026-11-12.
- Alcance: estado del repo y hechos externos documentados (GitHub, AWS, HashiCorp). Sin recomendaciones.
- Conventions que acotan el área: Apply gate (apply solo desde CI al fusionar en dev; prod con aprobación manual), IaC only, Region (`eu-west-3`), Simple shell commands, Design write ownership.
- Revisión adversarial: no aplica a esta nota; la consolida el autor posterior.
- Repo: `javiladino/skyroute`.

## Hallazgos

1. **Proveedor OIDC de IAM para GitHub.** URL del emisor: `https://token.actions.githubusercontent.com`. Audiencia: `sts.amazonaws.com` cuando se usa la action oficial `aws-actions/configure-aws-credentials`. La página de GitHub no menciona thumbprint y remite a la documentación de AWS para añadir el proveedor.
   Fuente: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws (consultado 2026-11-12).

2. **Estado del thumbprint en AWS.** AWS verifica el certificado TLS del endpoint JWKS con su biblioteca de CAs raíz de confianza; solo si el IdP usa un certificado no firmado por una de ellas recurre a los thumbprints configurados (también recurre a ellos si no puede obtener el certificado o si se exige TLS 1.3). Un proveedor IAM OIDC debe tener entre 1 y 5 thumbprints y entre 1 y 100 audiencias. Al crearlo, IAM intenta obtener el thumbprint de la CA intermedia superior del certificado del servidor. El proveedor debe estar en la misma cuenta que el rol que confía en él. Dentro de una cuenta, cada proveedor usa una URL única.
   Fuente: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html (consultado 2026-11-12).

3. **Condiciones de la trust policy.** El ejemplo de GitHub usa dos claves de condición: `token.actions.githubusercontent.com:aud` igual a `sts.amazonaws.com` y `token.actions.githubusercontent.com:sub` igual a uno de los valores de `sub`. Con comodín se usa `StringLike`, por ejemplo `repo:octo-org/octo-repo:*`.
   Fuente: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws (consultado 2026-11-12).

4. **Formatos de `sub`.** Tabla de la referencia OIDC de GitHub (el ejemplo usa `octo-org/octo-repo`):

   | Tipo | Formato | Cuándo aplica |
   |------|---------|---------------|
   | Rama | `repo:ORG/REPO:ref:refs/heads/RAMA` | sin environment y sin evento pull_request |
   | pull_request | `repo:ORG/REPO:pull_request` | evento de PR sin environment |
   | Environment | `repo:ORG/REPO:environment:NOMBRE` | el job referencia un environment |
   | Tag | `repo:ORG/REPO:ref:refs/tags/TAG` | sin environment y sin evento PR |

   Para este repo, los valores concretos serían `repo:javiladino/skyroute:ref:refs/heads/main`, `repo:javiladino/skyroute:pull_request` y `repo:javiladino/skyroute:environment:<nombre>` (sustitución directa del formato documentado). Los `:` dentro de valores de metadatos se sustituyen por `%3A`.
   Fuente: https://docs.github.com/en/actions/reference/security/oidc (consultado 2026-11-12).

5. **Formato inmutable de `sub`.** Los repos creados después del 15 de julio de 2026, o que hayan optado por ello, emiten `sub` con IDs numéricos: `repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/BRANCH`. Los repos anteriores a esa fecha mantienen el formato solo con nombres salvo que opten. La README de `aws-actions/configure-aws-credentials` indica que una trust policy con el formato antiguo falla con "Not authorized to perform sts:AssumeRoleWithWebIdentity" frente a un token inmutable. No he comprobado qué formato emite `javiladino/skyroute` (fecha de creación del repo y opt-in no verificados).
   Fuentes: https://docs.github.com/en/actions/reference/security/oidc ; https://github.com/aws-actions/configure-aws-credentials (consultado 2026-11-12).

6. **Acotar a repo y rama.** El ejemplo de GitHub fija el `sub` al valor de rama (`...:ref:refs/heads/octo-branch`) para limitar el rol a esa rama, o al valor de environment (`...:environment:prod`) para limitarlo a un environment. El comodín `repo:ORG/REPO:*` abarca todo el repo.
   Fuente: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws (consultado 2026-11-12).

7. **Permisos del workflow.** El job o workflow debe conceder `id-token: write`; sin él no se puede solicitar el JWT. El permiso solo habilita pedir y usar el token, no escribir en recursos. El ejemplo añade `contents: read` para `actions/checkout`. Para workflows reutilizables fuera de la organización, la página recomienda fijar `id-token: write` explícitamente en el llamador.
   Fuentes: https://docs.github.com/en/actions/reference/security/oidc ; https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws (consultado 2026-11-12).

8. **`aws-actions/configure-aws-credentials`.** Versión mayor actual en los ejemplos de la README: `v6`; los ejemplos usan `@v6.3.0` y también el tag flotante `@v6`. El ejemplo de la documentación de GitHub referencia la action por SHA de commit (`e3dd6a429d7300a6a4c196c26e071d42e0343502`), sin tag. La sección Releases no se vio en la captura, por lo que el último tag publicado no está confirmado.
   Fuentes: https://github.com/aws-actions/configure-aws-credentials ; https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws (consultado 2026-11-12).

9. **`hashicorp/setup-terraform`.** Versión mayor actual en la README: `v4` (`uses: hashicorp/setup-terraform@v4`). El último tag publicado no está confirmado (Releases no visible en la captura).
   Fuente: https://github.com/hashicorp/setup-terraform (consultado 2026-11-12).

10. **Plan comentado en la PR (README de setup-terraform).** La README muestra un workflow en eventos `pull_request` que ejecuta format check, init, validate y plan, y publica el resultado con `actions/github-script@v7`; el plan va en una sección colapsable "Show Plan". Hay una variante que busca un comentario previo del bot y lo actualiza en lugar de crear otro. Advierte que los comentarios de GitHub tienen un límite de 65535 caracteres, por lo que un plan largo puede romper el paso, y menciona el job summary como alternativa.
    Fuente: https://github.com/hashicorp/setup-terraform (consultado 2026-11-12).

11. **Patrón plan en PR / apply en merge (tutorial de HashiCorp).** El tutorial usa dos workflows: `terraform-plan.yml` en `pull_request` y `terraform-apply.yml` en `push` a `main` (incluye PRs fusionadas). Está montado sobre HCP Terraform con `hashicorp/tfc-workflows-github@v1.0.0` y `actions/checkout@v3`, no con `setup-terraform`. Permisos del job de plan: `contents: read` y `pull-requests: write`; del de apply: `contents: read`. El comentario lo publica `actions/github-script@v6` y borra el anterior del bot. El tutorial no muestra condiciones `github.ref` ni `github.event_name`.
    Fuente: https://developer.hashicorp.com/terraform/tutorials/automation/github-actions (consultado 2026-11-12).

12. **Environments con revisores requeridos.** Hasta 6 personas o equipos como revisores; basta que apruebe uno. La opción "Prevent self-review" impide que apruebe quien lanzó el run. "Deployment branches and tags" limita qué ramas/tags pueden desplegar al environment (reglas por patrón, ramas y tags por separado). Un job que referencia un environment debe pasar sus reglas antes de ejecutarse o acceder a sus secretos. Los secretos de environment solo están disponibles para jobs que lo usan, tras pasar las reglas. En planes Free, los environments solo se configuran en repos públicos; GitHub Team/Pro también en privados. Si un repo pasa a privado en plan Free, sus reglas y secretos de environment se ignoran. Visibilidad y plan de `javiladino/skyroute` no verificados.
    Fuente: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments (consultado 2026-11-12).

13. **Interacción con el `sub`.** Un job que referencia un environment emite `sub` de tipo environment (hallazgo 4), no de rama. Es el formato documentado "Job references an environment".
    Fuente: https://docs.github.com/en/actions/reference/security/oidc (consultado 2026-11-12).

14. **`pull_request` y forks.** `GITHUB_REF` es `refs/pull/N/merge` y `GITHUB_SHA` el merge commit; `actions/checkout` extrae ese resultado. Los secretos no se pasan al runner en workflows disparados desde un fork, salvo `GITHUB_TOKEN`, que es de solo lectura en PRs de forks. Los workflows no corren en forks hasta activar Actions allí. Las PRs de Dependabot se tratan como PRs de fork. No corren con conflicto de merge.
    Fuente: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows (consultado 2026-11-12).

15. **`pull_request_target`.** Corre en el contexto de la rama por defecto del repo base (`GITHUB_SHA` y `GITHUB_REF` de la rama por defecto), no en el merge commit. La documentación indica evitarlo si se necesita compilar o ejecutar código de la PR y advierte de que ejecutar código no confiable puede causar vulnerabilidades (envenenamiento de caché, escrituras o acceso a secretos no previstos). La guía de hardening lo describe como privilegiado, con posible acceso de escritura y a secretos, y recomienda `workflow_run` para separar privilegios.
    Fuentes: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows ; https://docs.github.com/en/actions/how-tos/security-for-github-actions/security-guides/security-hardening-for-github-actions (consultado 2026-11-12).

16. **Disponibilidad del token OIDC en PRs de fork.** No verificado: ni la referencia OIDC ni la página de hardening ni la de eventos tratan si se emite un JWT a PRs de forks. Solo está documentado lo del hallazgo 14 (sin secretos, `GITHUB_TOKEN` de solo lectura).
    Fuentes consultadas sin respuesta sobre este punto: las tres páginas citadas en 14 y 15 más https://docs.github.com/en/actions/reference/security/oidc (consultado 2026-11-12).

## Estado del repo

- `.github/workflows/`: no existe. `Glob` con patrón `.github/**` desde la raíz del repo devuelve "No files found" (2026-11-12).
- `AGENTS.md` § Mapa del repo, tabla "Previsto (aún no existe)": lista `.github/workflows/` con contenido "CI" (fila de `AGENTS.md`); `infra/terraform/{bootstrap,modules,envs/{dev,prod}}/` también figura como previsto.
- `docs/design/CONTEXT.md` § Conventions, línea 45 (Apply gate): `apply` solo desde CI al fusionar (dev) y prod con aprobación manual; ningún agente ejecuta `plan`/`apply`. Línea 44 (IaC only): state remoto en S3 con `use_lockfile`. Línea 42 (Region): `eu-west-3`.
- No hay workflow, rol IAM ni proveedor OIDC definidos en el repo: no hay código Terraform ni YAML de CI que revisar hoy.

## Fuentes

- https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws (consultado 2026-11-12)
- https://docs.github.com/en/actions/reference/security/oidc (consultado 2026-11-12)
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows (consultado 2026-11-12)
- https://docs.github.com/en/actions/how-tos/security-for-github-actions/security-guides/security-hardening-for-github-actions (consultado 2026-11-12)
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments (consultado 2026-11-12)
- https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html (consultado 2026-11-12)
- https://github.com/aws-actions/configure-aws-credentials (consultado 2026-11-12)
- https://github.com/hashicorp/setup-terraform (consultado 2026-11-12)
- https://developer.hashicorp.com/terraform/tutorials/automation/github-actions (consultado 2026-11-12)
- Repo: `/Users/javierladino/Documents/Portafolio/skyroute/skyroute/AGENTS.md`, `/Users/javierladino/Documents/Portafolio/skyroute/skyroute/docs/design/CONTEXT.md`
