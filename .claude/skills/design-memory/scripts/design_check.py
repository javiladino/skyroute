#!/usr/bin/env python3
"""Read-only close-out checks for a design root (skill design-memory).

Checks, for a design root such as docs/design/:
  (a) CONTEXT.md "**Last updated:** YYYY-MM-DD" is on or after the newest dated
      entry of every active topic context.md. A dated entry is a journal block
      that starts with a bold date (**YYYY-MM-DD ...) or a ruling whose bold
      label holds a date (- **Name (owner, YYYY-MM-DD HH:MM):**). Dates after
      today are ignored: they are deadlines or expiries, not entries.
  (c) Every README "Open decisions" row with "(plan in {path})" names a path
      that exists inside the design root and is not under archive/.
  (d) Size guardrails: CONTEXT.md > 100 lines, any "**Prior state" label, more
      than one "**Current state" block in Active Context; topic context.md
      > 150 lines or > 8 journal blocks. Files above their target (CONTEXT.md
      80, Active Context 15 non-blank lines, topic context.md 120) get a WARN.
  (f) Folder shape: no loose files at a topic root (only context.md, handoff.md
      and the lifecycle folders); every file under current/ has a document-map
      row; no map row names a missing file under the topic's own folders.
      Unknown sub-folders at a topic root get a WARN. At the design root, any
      file other than CONTEXT.md, README.md, CHANGELOG.md, findings.md, and any
      folder other than findings/ that has no context.md, get a WARN.

A topic is any immediate sub-folder that holds a context.md. It is active
unless its **Status:** starts with Done, Complete(d), Closed, Canceled,
Cancelled, Merged, Shipped, Duplicate, Superseded, Archived, or Abandoned;
closed topics skip (a) only.

Usage:
  python3 design_check.py docs/design [--today YYYY-MM-DD]

Exit code 0 = no FAIL; 1 = at least one FAIL; 2 = usage error or a control
file that cannot be read as UTF-8 text.
Reads files only. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

CONTEXT_TRIGGER, CONTEXT_TARGET = 100, 80
ACTIVE_CONTEXT_TARGET = 15
TOPIC_TRIGGER, TOPIC_TARGET = 150, 120
JOURNAL_BLOCK_TRIGGER = 8

PROJECT_FILES = {"CONTEXT.md", "README.md", "CHANGELOG.md", "findings.md"}
ROOT_FILES = {"context.md", "handoff.md"}
LIFECYCLE_DIRS = {"current", "working", "evidence", "archive", "assets"}
IGNORED = {".DS_Store", ".gitkeep"}

DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LAST_UPDATED = re.compile(r"\*\*Last updated:\*\*\s*(\S+)")
STATUS = re.compile(r"\*\*Status:\*\*\s*([^·\n]+)")
CLOSED = re.compile(
    r"^(done|complete|completed|closed|canceled|cancelled|merged|shipped|duplicate"
    r"|superseded|archived|abandoned)\b",
    re.I,
)
JOURNAL_BLOCK = re.compile(r"^\*\*(\d{4}-\d{2}-\d{2})", re.M)
RULING_LABEL = re.compile(r"^\s*- \*\*(.+?)\*\*", re.M | re.S)
BLOCK_LABEL = r"^\s*(?:[-*]\s+)?\*\*{}[^*\n]*(?::\*\*|\*\*\s*:)"
PRIOR_STATE = re.compile(BLOCK_LABEL.format("Prior state"), re.M | re.I)
CURRENT_STATE = re.compile(BLOCK_LABEL.format("Current state"), re.M | re.I)
PLAN_POINTER = re.compile(r"plan in (?:`([^`\s]+)`|([^\s)`,;]+)\))", re.I)
CELL_PATH = re.compile(r"`([^`]+)`|\[[^\]]*\]\(([^)\s]+)\)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    """Body of the first `## ` section whose heading contains `heading`, else ''."""
    pattern = re.compile(heading, re.I)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("## ") and pattern.search(line):
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


def to_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def newest_entry(text: str, today: date) -> tuple[date, str] | None:
    """Newest dated journal block or dated ruling label, ignoring future dates."""
    found: list[tuple[date, str]] = []
    for m in JOURNAL_BLOCK.finditer(section(text, "journal")):
        d = to_date(m.group(1))
        if d:
            found.append((d, "journal block"))
    for m in RULING_LABEL.finditer(section(text, "rulings")):
        label = " ".join(m.group(1).split())
        name = label.split("(")[0].strip() or label[:40]
        for s in DATE.findall(label):
            d = to_date(s)
            if d:
                found.append((d, f'ruling "{name}"'))
    found = [f for f in found if f[0] <= today]
    return max(found, key=lambda f: f[0]) if found else None


def check_context(root: Path, ctx: str, fails: list[str], warns: list[str]) -> None:
    n = len(ctx.splitlines())
    if n > CONTEXT_TRIGGER:
        fails.append(f"(d) CONTEXT.md has {n} lines (trigger > {CONTEXT_TRIGGER})")
    elif n > CONTEXT_TARGET:
        warns.append(f"(d) CONTEXT.md has {n} lines (target <= {CONTEXT_TARGET})")
    if PRIOR_STATE.search(ctx):
        fails.append('(d) CONTEXT.md holds a "Prior state" block (move it to the CHANGELOG)')
    active = section(ctx, "active context")
    n_current = len(CURRENT_STATE.findall(active))
    if n_current > 1:
        fails.append(f"(d) Active Context has {n_current} current-state blocks (allowed: 1)")
    n_active = len([ln for ln in active.splitlines() if ln.strip()])
    if n_active > ACTIVE_CONTEXT_TARGET:
        warns.append(
            f"(d) Active Context has {n_active} non-blank lines (target <= {ACTIVE_CONTEXT_TARGET})"
        )


def check_plan_pointers(root: Path, fails: list[str]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    resolved_root = root.resolve()
    for row in section(read(readme), "open decisions").splitlines():
        for groups in PLAN_POINTER.findall(row):
            pointer = groups[0] or groups[1]
            if any(ch in pointer for ch in "{}<>"):
                continue
            target = (root / pointer.rstrip("/")).resolve()
            try:
                parts = target.relative_to(resolved_root).parts
            except ValueError:
                fails.append(f"(c) README Open decisions plan pointer {pointer} is outside the design root")
                continue
            if "archive" in parts:
                fails.append(f"(c) README Open decisions plan pointer {pointer} is under archive/")
            elif not target.exists():
                fails.append(f"(c) README Open decisions plan pointer {pointer} does not exist")


def map_paths(doc_map: str) -> set[str]:
    """Paths named in the first cell of each document-map row: `path` or [text](path)."""
    paths: set[str] = set()
    for line in doc_map.splitlines():
        cells = line.strip().split("|")
        if len(cells) < 3 or set(cells[1].strip()) <= set("-: "):
            continue
        for code, link in CELL_PATH.findall(cells[1]):
            p = (code or link).strip().rstrip("/")
            paths.add(p[2:] if p.startswith("./") else p)
    return paths


def check_shape(topic: Path, text: str, fails: list[str], warns: list[str]) -> None:
    name = topic.name
    for child in sorted(topic.iterdir()):
        if child.name in IGNORED or child.name.startswith("."):
            continue
        if child.is_file() and child.name not in ROOT_FILES:
            fails.append(f"(f) {name}/{child.name} is a loose file at the topic root (file it in a lifecycle folder)")
        elif child.is_dir() and child.name not in LIFECYCLE_DIRS:
            warns.append(f"(f) {name}/{child.name}/ is not a lifecycle folder")
    rows = map_paths(section(text, "document map"))
    current = topic / "current"
    if current.is_dir():
        for f in sorted(current.rglob("*")):
            if f.is_file() and f.name not in IGNORED:
                rel = f.relative_to(topic).as_posix()
                if rel not in rows:
                    fails.append(f"(f) {name}/{rel} has no document-map row")
    for row in sorted(rows):
        first = row.split("/")[0]
        if first in LIFECYCLE_DIRS or row in ROOT_FILES:
            if any(ch in row for ch in "*?{}<>"):
                continue
            if not (topic / row).exists():
                fails.append(f"(f) {name}/context.md document map names {row}, which does not exist")


def check_root(root: Path, warns: list[str]) -> None:
    for child in sorted(root.iterdir()):
        if child.name in IGNORED or child.name.startswith("."):
            continue
        if child.is_file() and child.name not in PROJECT_FILES:
            warns.append(f"(f) {child.name} is a loose file at the design root (file it in a topic)")
        elif child.is_dir() and child.name != "findings" and not (child / "context.md").is_file():
            warns.append(f"(f) {child.name}/ has no context.md (scaffold the topic or move its files)")


def check(root: Path, today: date) -> tuple[list[str], list[str]]:
    fails: list[str] = []
    warns: list[str] = []
    ctx = read(root / "CONTEXT.md")
    check_context(root, ctx, fails, warns)
    check_plan_pointers(root, fails)
    check_root(root, warns)

    m = LAST_UPDATED.search(ctx)
    last_updated = to_date(m.group(1)) if m else None
    if m is None:
        fails.append('(a) CONTEXT.md has no "**Last updated:** YYYY-MM-DD" line')
    elif last_updated is None:
        fails.append(f'(a) CONTEXT.md "Last updated" value {m.group(1)!r} is not a valid YYYY-MM-DD date')

    topics = sorted(p for p in root.iterdir() if p.is_dir() and (p / "context.md").is_file())
    if not topics:
        warns.append("no topic folder with a context.md found")
    for t in topics:
        rel = f"{t.name}/context.md"
        text = read(t / "context.md")
        n = len(text.splitlines())
        if n > TOPIC_TRIGGER:
            fails.append(f"(d) {rel} has {n} lines (trigger > {TOPIC_TRIGGER})")
        elif n > TOPIC_TARGET:
            warns.append(f"(d) {rel} has {n} lines (target <= {TOPIC_TARGET})")
        n_blocks = len(JOURNAL_BLOCK.findall(section(text, "journal")))
        if n_blocks > JOURNAL_BLOCK_TRIGGER:
            fails.append(f"(d) {rel} has {n_blocks} journal blocks (trigger > {JOURNAL_BLOCK_TRIGGER})")
        check_shape(t, text, fails, warns)

        sm = STATUS.search(text)
        status = sm.group(1).strip() if sm else "unknown"
        if CLOSED.match(status):
            continue
        newest = newest_entry(text, today)
        if newest and last_updated and last_updated < newest[0]:
            shown = status if len(status) <= 40 else status[:37] + "..."
            fails.append(
                f"(a) CONTEXT.md Last updated {last_updated} is before the newest dated entry "
                f"in {rel} ({newest[0]}, {newest[1]}; topic status: {shown})"
            )
    return fails, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root", type=Path, help="design root, e.g. docs/design")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today(),
                    help="ignore dated entries after this day (default: today)")
    args = ap.parse_args()
    if not (args.root / "CONTEXT.md").is_file():
        print(f"usage error: {args.root}/CONTEXT.md not found", file=sys.stderr)
        return 2

    try:
        fails, warns = check(args.root, args.today)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"usage error: cannot read a control file: {exc}", file=sys.stderr)
        return 2
    print(f"design_check: {args.root} (script checks (a), (c) plan pointers, (d), (f); "
          "(b), the rest of (c), and (e) are read checks)")
    for f in fails:
        print(f"FAIL {f}")
    for w in warns:
        print(f"WARN {w}")
    print(f"{len(fails)} FAIL, {len(warns)} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
