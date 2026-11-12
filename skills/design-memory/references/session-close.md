# Session close: triage, findings, and checks

Open this at the end of any session that wrote to the design root. The steps run in this
order. The main session runs them, including for files its sub-agents wrote.

## 1. Triage

Decide once for every document a sub-agent or you produced this session:

| Decision | Action | Use when |
|----------|--------|----------|
| Keep | Move to `current/`; add a map row with role and load | It is finished and later work will read it |
| In flight | Leave in `working/` | The next session continues it (mid-cycle stage files, drafts) |
| Archive | Move to `archive/` (`git mv` when tracked); update its map row | It is superseded or spent but someone may need to see it |
| Discard | Delete (ask first if the owner keeps a gate on deletion) | Scratch that concludes nothing; never a file that records a decision or a result |

Do not promote an unfinished draft to `current/` to make the folder look tidy; it moves at
cycle close.

## 2. Findings

Ask: did this session learn a fact a different topic will need ("the export drops rows with
an empty header", "the parser treats `\t` as two characters")? If yes, append a block to
`findings.md` from the template: date, source topic, subject, the finding in at most three
lines, and the provenance path in `evidence/` or `archive/`.

Then update the pointer line in `CONTEXT.md` (`findings.md` — N entries, last {date}).
`findings.md` is never loaded by default: the pointer tells a session it exists, and a brief
may quote the one relevant finding inline instead of sending the sub-agent to the file. When
the file passes about 150 lines, split it by subject into `findings/{subject}.md`; do not
split earlier.

## 3. Record

Update the document map for every file that was added, moved, or removed. Append one
CHANGELOG line for the session.

## 4. Checks

Run these after the triage and fix every failure before the session ends. They exist because
the topic file gets updated and the project files do not; relying on memory to catch that does
not work.

| Check | Pass condition | How |
|-------|----------------|-----|
| (a) Last updated | `CONTEXT.md` `Last updated` is on or after the newest dated entry (journal block or dated ruling label) of every active topic | script |
| (b) Active Context is current | The one current-state block names the latest state: no "next up" item the journal shows as done, no superseded branch or status | read |
| (c) README matches | Every Topics row shows its current status; Phases agree with topics; every `plan in {path}` pointer exists and is not under `archive/` | read; script for pointers |
| (d) Size guardrails | No file crosses a compaction trigger; one current-state block; no "Prior state" block | script |
| (e) Rulings scoped | Every ruling written this session passed the scope test and sits in its home, in the entry format | read |
| (f) Folder shape | No loose files at a topic root; every `current/` file has a map row; no map row points to a missing local file | script |

Run the script from the project root:

```bash
python3 <path-to-this-skill>/scripts/design_check.py docs/design
python3 <path-to-this-skill>/scripts/design_check.py docs/design --today 2026-01-31   # pin the date
```

It prints one `FAIL` line per violation, `WARN` lines for files above their target size,
and a count. Exit 0 means no `FAIL`; 1 means at least one; 2 means the design root has no
`CONTEXT.md` or the arguments are wrong. A topic whose `**Status:**` starts with Done,
Complete, Closed, Cancelled, Merged, Shipped, or Duplicate is skipped for check (a) but still
size-checked. Dates later than today are ignored, because they are deadlines, not entries.

Record the read checks (b), (c), (e) in the closing journal block, for example:
`Close-out: design_check 0 FAIL; Active Context current; README matches; 1 ruling, project-wide, in Conventions.`
