---
name: design-memory
description: >
  Keeps a project's design docs usable as long-term agent memory: a two-level layout under
  docs/design/ (project CONTEXT, README, CHANGELOG, findings; one folder per topic with a
  context.md and current/ working/ evidence/ archive/), a load order that reads the smallest
  oriented set first, one home per ruling, one current-state block, and mechanical checks at
  session close. Use when starting, resuming, or closing work that writes design docs; when
  deciding which file a fact, ruling, or draft belongs in; when deciding what to read first
  in a docs folder; when a ruling is made, promoted, or reversed; when a context file has
  grown stale or stacked; when the user says "close the ticket", "close this topic", "we're
  done with X", "wrap up", "organize the design docs", or "what should I load first". Not
  for the content of a stage document (reppit-* skills).
---

Adapted from ai_agents_repo @ 3e61f25, 2026-10-31: course stage list (Research, Propose, Plan, Implement, Test), no orchestration ledger, the stop hook ships in `scripts/` with its setup in `references/hook.md`.

# Design Memory

Agents forget everything between sessions. The design folder is their memory, and it only
works if the next session can find the current truth cheaply and trust it. Two things break
that: reading too much (whole folders, long histories) and writing the same fact in several
places (it then drifts). This skill fixes both with a fixed layout, a load order, and a
single home for every ruling. The load order applies progressive disclosure as described in
Anthropic's *Effective context engineering for AI agents*: minimal context up front, plus
paths to pull detail just in time.

Supporting files, opened only when the step says so:
- `templates/` — skeletons for every file below. Open when you scaffold or retrofit.
- `references/rulings.md` — promotion and reversal of rulings.
- `references/lifecycle.md` — placement edge cases, cycle close, moving planned work out.
- `references/session-close.md` — triage, findings, and the six close-out checks in full.
- `references/examples.md` — right and wrong versions of each file, on a toy project.
- `scripts/design_check.py` — the mechanical checks (Python 3, standard library, read-only).
- `scripts/design-check-on-stop.sh` and `references/hook.md` — the hook that runs the checks
  every time an agent ends a turn with design-doc changes. Open when you set it up.

## Trigger

Use this skill when a session will read or write files under the project's design root:
starting a topic, resuming one, recording a ruling, filing a draft, or closing a session that
changed design docs. Also use it to retrofit a folder that has loose files, stacked "prior
state" blocks, or rulings copied into several files.

The design root is `docs/design/` unless the project `AGENTS.md` names another folder. Every
path below is relative to that root.

## Layout

```
docs/design/
  CONTEXT.md        what is true now, project-wide; the entry point
  README.md         outcome and navigation, for humans
  CHANGELOG.md      append-only history; written every session, read only on request
  findings.md       durable cross-topic facts; read only when relevant
  <topic>/          one folder per piece of work (kebab-case slug)
    context.md      control file: orientation, rulings, journal, document map
    handoff.md      optional durable notes (never a session prompt)
    current/        compiled, current documents: the only topic docs loaded by default
    working/        in-flight drafts (stage files, cycle folders)
    evidence/       material collected from outside; immutable
    archive/        superseded or spent; kept, never on the read path
    assets/         non-markdown payloads
```

The design root holds only the four project files, the topic folders, and (once findings are
split) `findings/`. A topic root holds only `context.md`, `handoff.md`, and the folders above.
Every topic folder has a `context.md` from the moment it exists. Create a lifecycle folder the
first time something goes in it, not at scaffold time.

### Which file a sentence belongs in

| The sentence is… | It goes in… |
|------------------|-------------|
| A dated event: "on {date} we did X" | `CHANGELOG.md` |
| A superseded state: "it used to be…" | `CHANGELOG.md`, never `CONTEXT.md` |
| What is true now, project-wide (branch, headline, blocker) | `CONTEXT.md` Active Context, replacing the old block |
| A ruling a future topic would get wrong without it | `CONTEXT.md` Conventions |
| A ruling only this topic needs | `<topic>/context.md` § Rulings |
| What one session did on one topic | `<topic>/context.md` Journal |
| A durable outcome (what was built, key numbers) | `README.md` |
| Planned work that has no topic yet | `README.md` Phases and Open decisions rows; its plan in the originating topic's `working/` |
| A fact later topics need ("join X double-counts") | `findings.md` |

The test behind the table: if a sentence describes the past, it goes in the CHANGELOG; if it
describes now, it goes in CONTEXT. CONTEXT never narrates how it got here.

### Two levels, one cascade

The topic `context.md` holds full detail; the project files hold outcome and navigation.
Whenever a topic session changes project state, the same session adds one CHANGELOG line and,
if the current state changed, replaces the Active Context block. The topic gets the detail;
the project gets one line.

## Load protocol

Read in this order and stop as soon as the task is oriented:

| Level | Read | Typical size |
|-------|------|--------------|
| L0 | `CONTEXT.md` — current state, active topics, conventions, findings pointer | ~2k tokens |
| L1 | `<topic>/context.md` — rulings and document map | ~3–4k tokens |
| L2 | Files the document map marks `always` — usually 0–2 `current/` notes, or `handoff.md` | small |
| L3 | Only the files the task names; `findings.md` only when the task touches a subject it lists | varies |

Unless the task names the specific file, do not open `evidence/`, `archive/`, or
`CHANGELOG.md`, and never list or glob a whole topic folder: read the document map instead.
A session that continues a topic should be oriented within about 15k tokens. A new topic
reads L0, then scaffolds. Updating a deliverable reads L0, L1, and the named `current/` file;
it opens one `evidence/` file only when a named source is in dispute.

When a ruling, a number, or the scope conflicts between files, stop and ask the owner; do
not pick one silently. Output you just ran beats every document.

This is advisory: nothing blocks a read. A project that needs hard enforcement can add a
pre-read hook that refuses `archive/` and `evidence/` paths.

## Keeping files current and small

**One current-state block.** When the project state changes, the same session, the same day:
writes the CHANGELOG entry, deletes the old Active Context block (folding any fact the
CHANGELOG lacks into that entry first), and writes the new block. Never add a "Prior state"
block under the current one: a stack of old states is the failure this rule exists to stop.
Active Context holds one current-state block plus short optional Next up and Known issues
lists.

**A bounded journal.** The topic `context.md` journal is newest first and holds 6–8 dated
blocks. The session that crosses the cap collapses the oldest blocks into a plain list at the
bottom of the journal (`- YYYY-MM-DD: outcome`, no bold date) or drops them once the CHANGELOG
holds the facts. Keep the newest two in full.

**Size guardrails.** Numbers are guidance; the rule is "current and small". The session that
notices a crossed trigger compacts the file before it finishes its own work.

| File | Target | Compaction trigger |
|------|--------|--------------------|
| `CONTEXT.md` | ≤ ~80 lines | > 100 lines, or any "Prior state" block |
| Active Context section | ≤ ~15 lines | more than one current-state block |
| `<topic>/context.md` | ≤ ~120 lines | > 150 lines, or > 8 journal blocks |

## Rulings

A ruling is a decision later work must obey. Each one lives in exactly one place:

- **Project-wide** → `CONTEXT.md` § Conventions.
- **Topic-scoped** → `<topic>/context.md` § Rulings.

Every other file (Active Context, stage documents, handoff prompts, briefs) refers to the
ruling by name and does not restate the verdict. A ruling restated in two files is how two
files come to disagree. A stage document (for example the proposal's `## Decision`) keeps the question
and the discussion that settled it; the home holds the ruling's name, the verdict, and a
pointer to that discussion.

**Scope test, at write time.** Ask: "Would a future topic in this project be wrong if it did
not know this?" Yes → Conventions. No → the topic file. Direction, architecture, where code
lives, the release workflow, and standing owner gates are usually project-wide. Scope cuts,
budgets, model choices, and one-off build choices are usually topic-scoped. When unsure, ask
the owner rather than defaulting to the topic file: the next topic reads `CONTEXT.md`, not old
topic files.

**Entry format.** Name, date in force, owner, source, then the verdict once:

```markdown
- **{Name} (in force {YYYY-MM-DD}; owner {name}; source {topic}):** {verdict, 1–3 lines}.
```

Topic rulings use `- **{Name} ({owner}, {YYYY-MM-DD HH:MM}):** {verdict}.` The date in the
bold label is what the checker reads.

When a topic ruling turns out to be project-wide, or a ruling is reversed, follow
`references/rulings.md`. Both end with a mandatory search of the design root for the old
wording, because a stale copy left behind contradicts the new ruling.

## Lifecycle folders

Folders record where a file is in its life; the document map records what it is for. File
each document by asking, in order, and stop at the first yes:

1. Collected from an outside source (export, capture, transcript)? → `evidence/`
2. A draft of work still in flight? → `working/`
3. Superseded or spent? → `archive/`
4. Otherwise it is current and ours → `current/`

RePPIT writes its stage files in `working/`: `working/research.md`, `working/proposal.md`,
`working/plan.md`, `working/test.md`. Stage files carry an optional `type` field and no
`status` field — the folder is the state.

**Cycle close** (after `reppit-test` reports PASS and the user accepts the work): rulings go to
`context.md`, the deliverable goes to `current/`, and the spent drafts move to `archive/`
(`git mv` when they are tracked, a plain move when they are not). Archive rather than delete:
an agent can be pointed at an archived file, but it does not read git history unprompted.

**Document map.** Every file in the topic gets one row: path, role (deliverable, concept,
reference, draft), load class (`always` or `on-demand`), and one line on what it holds. The map
is the listing: there is no `index.md`. Rows may point to other repos.

Work planned inside a topic that will become its own topic, and the move when it does: see
`references/lifecycle.md`.

## Workflow

### Scaffold (new project or topic, ~4 tool calls)

1. Check which of `CONTEXT.md`, `README.md`, `CHANGELOG.md` exist at the design root.
2. Create the missing ones from `templates/`. Fill the header from the request; leave other
   sections out until there is content for them.
3. For a new topic, create `<topic>/context.md` from `templates/topic-context.md` with the
   task statement and constraints under Orientation, add the topic to Active Context, and add
   a README Topics row. Skip this step when `<topic>/context.md` already exists: the topic is
   being resumed, not started.
4. Add a CHANGELOG line.

Any skill that writes the first file of a new topic runs these steps first.

### Update (after work, ~4–8 tool calls)

1. Append a dated CHANGELOG entry (check the top entries first so you do not duplicate one).
2. File every new document by the four questions and add its document-map row.
3. Write each new ruling to its home after the scope test.
4. If the project state changed, replace the Active Context block.
5. Update the README Documents, Topics, and Open decisions tables if they changed.
6. Run the session-close steps below.

### Close a topic ("close the ticket", ~8–12 tool calls)

1. Close the cycle: rulings to their homes, deliverable to `current/`, spent drafts to
   `archive/` (§ Lifecycle folders).
2. Set the topic's `**Status:**` to `Done` (or `Cancelled`, `Superseded`).
3. Replace the Active Context block and drop the topic from the active list; update the
   README Topics row; append a CHANGELOG entry.
4. Run every step of § Session close, including the script. The topic is not closed until
   the script exits 0 and you have shown the user its summary line.

### Retrofit (existing folder, ~10–15 tool calls)

1. List the design root and read each topic's control file, not every document.
2. Move loose files into lifecycle folders with `git mv`; write the document maps.
3. Move stacked prior-state blocks to the CHANGELOG; leave one current-state block.
4. Find rulings stated in more than one file; keep one home and turn the rest into references.
5. Rebuild missing project files from the folder contents and git history.
6. Run the session-close checks; expect several failures on the first run.

## Session close

Every session that wrote to the design root ends with these steps. Details and the pass
conditions are in `references/session-close.md`.

1. **Triage** every document produced this session, once: keep it (`current/` plus a map row),
   leave it in flight (`working/`), archive it (move to `archive/`), or discard it (only
   scratch that concludes nothing; if the project's owner keeps a gate on deletion, ask).
2. **Findings.** If the session learned a durable cross-topic fact, append a block to
   `findings.md` and update its pointer line in `CONTEXT.md`.
3. **Record.** Update the document map and append one CHANGELOG line.
4. **Check.** Run the script, fix every `FAIL`, and do the three read checks it cannot do:

```bash
python3 <path-to-this-skill>/scripts/design_check.py docs/design
```

The read checks are: Active Context names the latest state (no finished "next up" items, no
superseded branch); README statuses agree with the topic files; every ruling written this
session passed the scope test. Record the result in the closing journal block, and quote the
script's summary line (`N FAIL, M WARN`) in your report to the user. Never report a session or
topic as closed without it.

To make this hold every time, register `scripts/design-check-on-stop.sh` as a stop hook
(`references/hook.md`): it runs the script whenever an agent ends a turn with uncommitted
design-doc changes and sends any `FAIL` back to the agent.

A session that hands work to a new session posts the handoff prompt in chat; it does not write
a session prompt to `handoff.md`.

## Quality gates

- [ ] `design_check.py` exits 0.
- [ ] `CONTEXT.md` has one current-state block and a `Last updated` date no older than the
      newest dated entry of any active topic.
- [ ] Each ruling has one home; other files refer to it by name.
- [ ] No loose files at a topic root; every `current/` file has a document-map row.
- [ ] Every README Documents link and every skill in the CONTEXT Skills table exists.
- [ ] The CHANGELOG has an entry for this session; nothing historical sits in `CONTEXT.md`.
- [ ] Nothing in `evidence/` or `archive/` was edited or deleted.

## Relationship to other skills

- `reppit-research`, `reppit-propose`, `reppit-plan`, and `reppit-test` write their stage files
  to `<topic>/working/`; `reppit-implement` reads them there. This skill decides where those
  files go next.
- `reppit-propose` records the user's pick in `## Decision`; the ruling it creates gets its home
  here (§ Rulings).
- After `reppit-test` reports PASS, close the cycle with § Workflow, Close a topic.

## What this skill does not do

- Write the content of stage documents, deliverables, or handoff prompts.
- Edit code in target repos; it maintains markdown in the design root only.
- Replace the issue tracker: it links to tickets but does not mirror their descriptions.
- Force-load skills: the Skills table in `CONTEXT.md` is advice, not a loader.

Done means: the files above are current, each fact has one home, and the checks pass.
