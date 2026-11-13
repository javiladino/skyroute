import hashlib
import os
import subprocess
import sys
from pathlib import Path

GENERATORS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATORS))

from ota.clickstream import generate  # noqa: E402

SNIPPET = (
    "import hashlib;"
    "from ota.clickstream import generate;"
    "print(hashlib.sha256(generate('2026-05-01', 17)).hexdigest())"
)


def test_ts_u1_same_bytes_twice():
    assert generate("2026-05-01", 17) == generate("2026-05-01", 17)


def test_different_slots_differ():
    assert generate("2026-05-01", 17) != generate("2026-05-01", 18)


def _run(hashseed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=hashseed, PYTHONPATH=str(GENERATORS))
    out = subprocess.run(
        [sys.executable, "-c", SNIPPET], env=env, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def test_ts_u2_same_bytes_across_hashseeds():
    here = hashlib.sha256(generate("2026-05-01", 17)).hexdigest()
    assert _run("0") == _run("1") == here
