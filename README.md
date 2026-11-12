# Skyroute Marketing Lakehouse

Plataforma de datos de marketing para Skyroute, una agencia de viajes online ficticia. Ingiere clickstream, reservas, gasto publicitario, CRM y tipos de cambio en S3, los refina en una arquitectura Medallion sobre Apache Iceberg, y publica productos de datos con contrato (ROAS, CAC, atribución, funnel, RFM). Es un proyecto de portfolio de Data Engineer Senior y todos los datos son sintéticos.

## Documentación

- [Descripción de producto](docs/design/platform-blueprint/current/project/README.md): caso de negocio, fuentes, capas, productos de datos y stack.
- [Diseño del proyecto](docs/design/README.md): fases, topics, documentos y decisiones abiertas.

## Estado

Fase de diseño. La memoria de diseño y los archivos raíz están listos; todavía no hay código ni infraestructura. La Fase 1 (Fundaciones) aún no ha empezado.

## Requisitos previstos

Se confirmarán cuando empiece cada fase:

- Cuenta de AWS con MFA y usuario no root
- Terraform
- Docker (Airflow con Astro CLI, Postgres, Marquez, OpenMetadata)
- Python 3 con PySpark y dbt Core (adaptador Athena)
- Java para ejecutar Spark en local
- GitHub Actions (autenticación con AWS por OIDC)
