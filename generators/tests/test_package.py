import os
import subprocess
import sys
from pathlib import Path

GENERATORS = Path(__file__).resolve().parents[1]

SNIPPET = (
    "import sys, json, lambda_handler;"
    "assert callable(lambda_handler.handler);"
    "bad = [m for m in ('seed_postgres', 'ota.seed_postgres', 'pytest', 'verify_landing', 'boto3')"
    " if m in sys.modules];"
    "print(json.dumps(bad))"
)


def test_ts_u9_handler_imports_like_lambda(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(GENERATORS)
    out = subprocess.run(
        [sys.executable, "-c", SNIPPET],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"
