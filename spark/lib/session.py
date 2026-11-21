"""SparkSession con el catalogo Iceberg configurado por parametro; nunca lee el reloj."""

import os

from pyspark.sql import SparkSession

S3A_PROVIDERS = ",".join(
    [
        "org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        "com.amazonaws.auth.EnvironmentVariableCredentialsProvider",
        "com.amazonaws.auth.profile.ProfileCredentialsProvider",
    ]
)
ICEBERG_EXTENSIONS = "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
CATALOG_CLASS = "org.apache.iceberg.spark.SparkCatalog"


def catalog_conf(name: str, impl: str, warehouse: str, region: str) -> dict:
    """Configuracion de spark.sql.catalog.<name>; misma para local y Glue."""
    prefix = f"spark.sql.catalog.{name}"
    conf = {prefix: CATALOG_CLASS, f"{prefix}.warehouse": warehouse}
    if impl == "glue":
        conf[f"{prefix}.catalog-impl"] = "org.apache.iceberg.aws.glue.GlueCatalog"
        conf[f"{prefix}.io-impl"] = "org.apache.iceberg.aws.s3.S3FileIO"
        conf[f"{prefix}.client.region"] = region
    elif impl == "hadoop":
        conf[f"{prefix}.type"] = "hadoop"
    else:
        raise ValueError(f"catalog-impl desconocido: {impl}")
    return conf


def build_spark(args) -> SparkSession:
    builder = (
        SparkSession.builder.appName(f"skyroute-{args.dates[0]}")
        .config("spark.sql.extensions", ICEBERG_EXTENSIONS)
        .config("spark.sql.session.timeZone", "UTC")
        # Reemplazo de particion (Convention Idempotency): INSERT OVERWRITE solo toca
        # las particiones que trae el resultado.
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.hadoop.fs.s3a.endpoint.region", args.region)
    )
    if os.environ.get("AWS_PROFILE"):
        # El proveedor por defecto de s3a no lee perfiles (S3FileIO de Iceberg si, via SDK v2):
        # se anade el de perfil tras las variables de entorno para poder refrescar via ~/.aws.
        builder = builder.config("spark.hadoop.fs.s3a.aws.credentials.provider", S3A_PROVIDERS)
    if args.jars_packages and args.jars_packages.lower() != "none":
        builder = builder.config("spark.jars.packages", args.jars_packages)
    conf = catalog_conf(args.catalog_name, args.catalog_impl, args.warehouse, args.region)
    for key, value in conf.items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()
    # Si la sesion ya existia (tests, Glue), getOrCreate no reaplica el catalogo en todos los casos.
    for key, value in conf.items():
        spark.conf.set(key, value)
    return spark
