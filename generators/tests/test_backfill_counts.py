"""Recuento esperado de eventos por rango (fuente de la Validation 4b del backfill)."""

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ota import backfill_counts
from ota.clickstream import generate
from ota.keys import SLOTS_PER_DAY

START = "2026-05-30"
END = "2026-06-01"  # cruza fin de mes


def _generated(run_date: str) -> tuple:
    unique, lines = set(), 0
    for slot in range(SLOTS_PER_DAY):
        text = gzip.decompress(generate(run_date, slot)).decode("utf-8")
        for line in text.splitlines():
            lines += 1
            unique.add(json.loads(line)["event_id"])
    return len(unique), lines


def test_days_cross_month_boundary():
    assert backfill_counts.days(START, END) == ["2026-05-30", "2026-05-31", "2026-06-01"]


def test_backfill_counts():
    total_unique = total_lines = 0
    for day in backfill_counts.days(START, END):
        unique, lines = _generated(day)
        assert unique == backfill_counts.day_count(day)
        assert lines >= unique  # el resto son duplicados intencionados (3 %)
        total_unique += unique
        total_lines += lines
    assert total_unique == backfill_counts.expected_unique_events(START, END) > 0
    assert total_lines > total_unique


def test_cli_prints_total(capsys):
    assert backfill_counts.main(["--from", START, "--to", END]) == 0
    expected = backfill_counts.expected_unique_events(START, END)
    assert capsys.readouterr().out.strip() == str(expected)
    assert backfill_counts.main(["--from", END, "--to", START]) == 2
