# Lifecycle: placement edge cases, cycle close, planned work

Open this when a file does not fit the four placement questions cleanly, when a cycle closes,
or when work planned inside one topic is about to become its own topic.

## Why folders record lifecycle and the map records role

Whether a file was collected, is in flight, is dead, or is current is a fact anyone can check,
so two people file it the same way. Whether it is a "deliverable", a "concept", or a
"reference" is a judgement, so folders built on role get misfiled and readers stop trusting
them. Role therefore lives in a document-map column, where it is cheap to change. There are no
role folders (no `wiki/`, no `deliverables/`) and no `index.md` beside the map: a second listing
drifts from the first. A crowded `current/` means a cycle close was skipped, not that the
folder needs splitting.

## Placement edge cases

| File | Folder | Why |
|------|--------|-----|
| A query export or log capture you saved | `evidence/` | Collected; never edited after saving |
| Your summary of that export | `current/` (or `working/` while drafting) | Ours |
| A stage file of the active cycle | `working/` | In flight until cycle close |
| Last cycle's plan, now replaced | `archive/` | Superseded |
| A plan for work that has no topic yet | `working/<subtopic>/` | In flight; see below |
| A note that two deliverables share | `current/` in the topic that owns it; a map row elsewhere points to it | One copy |
| A screenshot or data file | `assets/` | Not markdown |
| Scratch that concluded nothing | delete | Only this may be deleted |

`evidence/` and `archive/` are append-only. Do not edit a file there; write a new one in
`current/` and point to the old one in the document map.

## Cycle close

When the last stage of a cycle is accepted:

1. Write the cycle's lasting rulings to `context.md` (promote any that pass the scope test).
2. Write or update the deliverable in `current/` and give it a map row.
3. Move the spent drafts from `working/` to `archive/` (`git mv` when tracked, a plain move
   when not). Skip any `working/<subtopic>/` that
   a README Open decisions row points to: move it out first (below) or leave it in place so the
   pointer stays valid.
4. Update the map rows for every moved file, the CHANGELOG, and Active Context.

Do this alongside the commit that delivers the work, with the owner's approval, not at every
session end. Unfinished drafts stay in `working/`.

## Planned work without its own topic

Work planned inside one topic before it has a topic of its own (for example, a release plan
drafted during a discovery topic) gets a defined home, so it is neither lost nor mistaken for
the current topic's scope:

1. **README:** a Phases row with status `Planned - no topic`, and an Open decisions row
   `Topic needed: {work} (plan in {topic}/working/{subtopic}/)` with options
   `Create topic / defer / drop` and status `Proposed`.
2. **The plan stays** in the originating topic's `working/{subtopic}/`, with a document-map
   row. Do not create the new topic folder before the work is accepted as a topic.
3. Rulings about the planned work take the scope test like any other ruling.

## Moving planned work into its own topic

The session that creates the new topic:

1. Creates `{new}/context.md` from the template.
2. Moves `{old}/working/{subtopic}/` to `{new}/working/` (`git mv` when tracked; move, never
   copy: one copy only).
3. Adds a Provenance section to `{new}/context.md`: source topic, date, moved paths, and a
   reference to any source ruling the new topic inherits.
4. Updates both document maps: the old one keeps one pointer line
   (`{subtopic} moved to {new}/ on {date}`); the new one gets the rows. Topic-scoped rulings
   about the work move to the new topic, with a reference left in the old one.
5. Updates the README: the Phases status, a Topics row, the Open decisions row set to
   `Accepted`, and Documents paths. Then runs `grep -rn "{old}/working/{subtopic}" docs/design/`
   and fixes every stale path.
6. Adds one CHANGELOG line (`Moved {subtopic} from {old} to {new}`), and updates Active
   Context if the list of active topics changed.
