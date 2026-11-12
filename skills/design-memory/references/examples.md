# Examples: right and wrong, on a toy project

Open this when you are unsure what a finished file looks like. The project is a small
CSV-to-JSON command-line tool with two topics: `delimiter-option` (add a `--delimiter` flag)
and `pretty-output` (planned). All dates, counts, and names are illustrative.

## Active Context

Wrong — a stack of states, history in the present-tense file:

```markdown
**Current state (2026-03-12):** `--delimiter` merged; working on `--pretty`.
**Prior state (2026-03-05, superseded):** plan approved, branch `feat/delimiter` open.
**Prior state (2026-02-28, superseded):** research done; header detection breaks on `;`.
```

Right — one block; the older facts are already in the CHANGELOG:

```markdown
**Current state (2026-03-12):** `delimiter-option` closed (merged, archived). `pretty-output`
is planned with no topic yet (README Open decisions). No blockers.
**Next up:** decide whether `pretty-output` becomes a topic.
```

Why this is right: the next session reads one block and knows where things stand. The
stacked version costs it three blocks of reading to learn one fact, and the "header detection
breaks" line is no longer true.

## CHANGELOG entry

Wrong — implementation steps, no outcome:

```markdown
## 2026-03-12
- Edited convert.py, added an argparse option, fixed tests, moved some files.
```

Right — the outcome, the numbers, the files:

```markdown
## 2026-03-12

### delimiter-option — `--delimiter` flag shipped
- Users can pass any single-character delimiter; the default stays `,`.
- Header detection now uses the chosen delimiter (12 new test cases, illustrative).

### Files (cli-tool, branch feat/delimiter)
- `cli.py`, `convert.py` (modified); `tests/test_convert.py` (modified)
- `docs/design/delimiter-option/working/*.md` → `archive/` (moved)
```

## Scope test

Project-wide — a future topic would be wrong without it, so it goes in `CONTEXT.md`
Conventions:

```markdown
- **Single-character options (in force 2026-03-03; owner maintainer; source delimiter-option):**
  New flags that take a separator accept exactly one character; multi-character separators are
  out of scope for the tool.
```

Topic-scoped — only this topic needs it, so it goes in `delimiter-option/context.md`:

```markdown
- **Skip tab handling this cycle (maintainer, 2026-03-03 10:00):** `\t` support is deferred to
  a later cycle; tests for it are marked expected-fail.
```

Why: the `pretty-output` topic will add an `--indent-char` flag. If the single-character
ruling lived only in the `delimiter-option` file, that topic would never load it.

## Document map

The `delimiter-option` map after its cycle closed:

```markdown
| File | Role | Load | What it holds |
|------|------|------|---------------|
| `current/delimiter-design.md` | deliverable | always | The shipped design: flag, default, header rule |
| `working/pretty-output/plan.md` | draft | on-demand | Plan for planned work with no topic yet |
| `evidence/sample-inputs.csv` | reference | on-demand | Saved test inputs from user reports |
| `archive/research.md`, `archive/proposal.md`, `archive/plan.md` | draft (spent) | on-demand | The closed cycle's stage files |
```

Wrong: listing `archive/` files as `always`, or leaving `current/delimiter-design.md` out of
the map because "it is obvious". The map is the only listing a session reads.

## Topic root

Wrong:

```
delimiter-option/
  context.md  research.md  proposal.md  plan.md  notes-old.md  sample.csv
```

Right (the same topic after its cycle closed; `notes-old.md` held nothing and was discarded):

```
delimiter-option/
  context.md
  current/delimiter-design.md
  working/pretty-output/plan.md
  archive/research.md  archive/proposal.md  archive/plan.md
  evidence/sample-inputs.csv
```
