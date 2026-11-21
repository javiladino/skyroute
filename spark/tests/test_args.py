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
