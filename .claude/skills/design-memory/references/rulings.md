# Rulings: promotion, reversal, and the proposal's Decision

Open this when a topic ruling turns out to be project-wide, when a ruling is reversed, or
when the user picks a proposal.

## Promotion: a topic ruling turns out to be project-wide

Any session that finds a topic ruling passing the scope test promotes it, whether it notices
at write time, at session close, or when a later topic needs the ruling:

1. **Add the Conventions entry** in `CONTEXT.md`: date in force is the date of the original
   ruling, owner is who made it, source is the topic.
2. **Replace the topic text** with a reference plus only the topic-specific detail:
   `Verdict: per project CONTEXT Conventions ("{Name}"). Topic detail: …`
3. **Search for copies.** Run `grep -rn "<distinctive phrase from the verdict>" docs/design/`
   and turn every restatement (other topics, Active Context, stage files) into a reference.
4. **Log it.** One CHANGELOG line, `Promoted ruling "{Name}" from {topic} to Conventions`, and
   a new `Last updated` date in `CONTEXT.md`.

## Reversal: a ruling is replaced or withdrawn

The same session that records the reversal:

1. **Edits the home copy in place.** Replace the old wording; do not leave the old ruling
   standing next to the new one.
2. **Searches for stale copies.** Run `grep -rni "<distinctive phrase from the old ruling>"
   docs/design/` and fix or delete every match outside `evidence/` and `archive/`. This search
   is not optional. A typical miss: a "do not publish the draft number" rule left in a stage
   file after the owner approved the number, so the next session refuses to use it.
3. **Searches the deliverable.** If a deliverable quotes the old ruling or depends on it, fix
   it, or flag it to the owner when it is already published.
4. **Logs the reversal** as a CHANGELOG entry that names the old and the new verdict.

## Wording a ruling so it can be found again

Give every ruling a short name and one distinctive phrase that appears nowhere else. The
promotion and reversal searches depend on that phrase. Avoid restating the verdict in your
own words elsewhere: a paraphrase does not match the search, so it survives every reversal.

## The proposal's Decision

`reppit-propose` records the user's pick, and the reason in their words, under `## Decision`
in `working/proposal.md`. That section is the discussion. The ruling it creates gets one home:

```markdown
- **Chosen approach (user, 2026-03-03 10:00):** Proposal 2, a `--delimiter` flag with `,` as
  the default. Discussion: `working/proposal.md` § Decision.
```

Put it in the topic `context.md` § Rulings, or in `CONTEXT.md` Conventions when it passes the
scope test (for example "new separator flags take exactly one character"). Later stages and
briefs quote the ruling by name; they do not copy the proposal's reasoning. When the cycle
closes and `proposal.md` moves to `archive/`, update the pointer to the archived path.
