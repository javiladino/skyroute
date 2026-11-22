"""El zip de --extra-py-files debe poder importarse solo, como en Glue.

zipimport no admite namespace packages (PEP 420): sin `__init__.py` en jobs/ y sus
subcarpetas, `from jobs.silver... import` falla en Glue aunque funcione en local. El zip
se construye con la misma raiz y exclusiones que `data.archive_file.spark_libs`
(infra/terraform/modules/lakehouse/glue_jobs.tf): lib/ y jobs/, sin tests/ ni checks/.
Importar los modulos no crea SparkSession (solo importa pyspark y yaml).
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SPARK_DIR = Path(__file__).resolve().parents[1]
ZIP_ROOTS = ("lib", "jobs")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}
MODULES = [
    "jobs.silver.bookings_scd2",
    "jobs.silver.fx_daily",
    "jobs.silver.bookings_eur",
    "jobs.bronze.ingest",
    "lib.checks",
]


def build_zip(target: Path, skip_init: bool = False) -> Path:
    with zipfile.ZipFile(target, "w") as zf:
        for root in ZIP_ROOTS:
            for path in sorted((SPARK_DIR / root).rglob("*")):
                rel = path.relative_to(SPARK_DIR)
                if not path.is_file() or SKIP_PARTS & set(rel.parts) or path.suffix == ".pyc":
                    continue
                if skip_init and path.name == "__init__.py":
                    continue
                zf.write(path, rel.as_posix())
    return target


def import_from_zip(zip_path: Path, module: str) -> subprocess.CompletedProcess:
    code = f"import sys; sys.path.insert(0, {str(zip_path)!r}); import {module}"
    return subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        cwd=zip_path.parent,
        check=False,
    )


def test_zip_has_lib_and_jobs_at_root(tmp_path):
    names = set(zipfile.ZipFile(build_zip(tmp_path / "libs.zip")).namelist())
    assert "lib/__init__.py" in names
    assert {"jobs/__init__.py", "jobs/bronze/__init__.py", "jobs/silver/__init__.py"} <= names
    assert not any(n.startswith(("tests/", "checks/")) for n in names)


@pytest.mark.parametrize("module", MODULES)
def test_modules_import_from_zip_alone(tmp_path, module):
    result = import_from_zip(build_zip(tmp_path / "libs.zip"), module)
    assert result.returncode == 0, result.stderr


def test_zip_without_init_files_fails(tmp_path):
    """Guarda: sin los __init__.py el import falla como en Glue."""
    zip_path = build_zip(tmp_path / "libs.zip", skip_init=True)
    result = import_from_zip(zip_path, "jobs.silver.fx_daily")
    assert result.returncode != 0
    assert "No module named 'jobs" in result.stderr
