"""Argumentos comunes: Glue añade los suyos; en local un argumento desconocido sigue fallando."""

import pytest
from lib.args import parse_args

BASE = ["--run-date", "2026-01-01", "--warehouse", "s3://bucket/silver"]
GLUE = ["--JOB_NAME", "skyroute-dev-silver-events", "--TempDir", "s3://bucket/glue-temp/"]


def with_gap(parser):
    parser.add_argument("--session-gap-minutes", type=int, default=30)


def test_glue_arguments_are_ignored_when_job_name_is_present():
    args = parse_args([*BASE, *GLUE, "--datalake-formats", "iceberg", "--enable-metrics"])
    assert args.dates == ["2026-01-01"]


def test_glue_reserved_arguments_with_values_are_accepted():
    glue = [
        *GLUE,
        "--JOB_ID", "j_1",
        "--JOB_RUN_ID", "jr_1",
        "--job-language", "python",
        "--job-bookmark-option", "job-bookmark-disable",
        "--extra-py-files", "s3://bucket/scripts/spark-libs.zip",
        "--extra-files=s3://bucket/scripts/checks/events.yaml",
        "--additional-python-modules", "PyYAML==6.0.4",
        "--conf", "spark.sql.extensions=x --conf spark.sql.session.timeZone=UTC",
        "--enable-spark-ui", "false",
        "--continuous-log-logGroup", "g",
    ]  # fmt: skip
    assert parse_args([*BASE, *glue]).dates == ["2026-01-01"]


def test_unknown_argument_fails_outside_glue():
    with pytest.raises(SystemExit):
        parse_args([*BASE, "--TempDir", "s3://bucket/glue-temp/"])


def test_typo_in_glue_fails_instead_of_using_the_default():
    with pytest.raises(SystemExit):
        parse_args([*BASE, *GLUE, "--session-gap-minute", "5"], extra=with_gap)


def test_abbreviation_does_not_assign_an_option():
    with pytest.raises(SystemExit):
        parse_args([*BASE, "--session-gap", "5"], extra=with_gap)
    with pytest.raises(SystemExit):
        parse_args([*BASE, *GLUE, "--session-gap", "5"], extra=with_gap)


def test_full_option_name_still_works_in_glue():
    args = parse_args([*BASE, *GLUE, "--session-gap-minutes", "5"], extra=with_gap)
    assert args.session_gap_minutes == 5


# argv de un job Silver en Glue: default_arguments de glue_jobs.tf + los que inyecta Glue.
GLUE_SILVER_ARGV = [
    "--JOB_ID", "j_x", "--JOB_RUN_ID", "jr_x", "--JOB_NAME", "skyroute-dev-silver-fx_daily",
    "--scriptLocation", "s3://bucket/scripts/jobs/silver/fx_daily.py",
    "--job-language", "python",
    "--datalake-formats", "iceberg",
    "--TempDir", "s3://bucket/glue-temp/",
    "--extra-py-files", "s3://bucket/scripts/spark-libs.zip",
    "--env", "dev",
    "--catalog-name", "skyroute",
    "--catalog-impl", "glue",
    "--warehouse", "s3://bucket/silver",
    "--region", "eu-west-3",
    "--jars-packages", "none",
    "--enable-metrics", "true",
    "--enable-spark-ui", "false",
    "--enable-glue-datacatalog",
    "--enable-job-insights", "false",
    "--job-bookmark-option", "job-bookmark-disable",
    "--conf", "spark.sql.extensions=x --conf spark.sql.session.timeZone=UTC",
    "--extra-files", "s3://bucket/scripts/checks/fx_daily.yaml",
    "--checks-dir", ".",
    "--additional-python-modules", "PyYAML==6.0.4",
    "--SECURITY_CONFIGURATION", "sc",
    "--encryption-type", "sse-s3",
    "--spark-event-logs-path", "s3://bucket/logs/",
    "--execution_class", "FLEX",
    "--from", "2026-11-19", "--to", "2026-11-20",
]  # fmt: skip


def with_checks(parser):
    parser.add_argument("--checks-dir", default=".")


def test_realistic_glue_argv_is_accepted():
    args = parse_args(GLUE_SILVER_ARGV, extra=with_checks)
    assert args.dates == ["2026-11-19", "2026-11-20"]
    assert args.checks_dir == "."


def test_run_date_variant_of_glue_argv_is_accepted():
    argv = [*GLUE_SILVER_ARGV[:-4], "--run-date=2026-11-20"]
    assert parse_args(argv, extra=with_checks).dates == ["2026-11-20"]


def test_typo_in_realistic_glue_argv_is_rejected():
    with pytest.raises(SystemExit):
        parse_args([*GLUE_SILVER_ARGV, "--run-dat", "2026-11-20"], extra=with_checks)
