Adapted from ai_agents_repo @ 1cdedc9, 2026-11-06: the template names the orchestration skill by its path `skills/session-orchestration/SKILL.md`.

# Handoff Mode

The full method for handoff mode of skill `session-prompting`: the prompt that boots a
fresh orchestrator or agent session to continue multi-phase work. The shared core
(delivery in chat, core principles) is in `SKILL.md`; apply it here too. Target ~60–90
lines.

## The Template

Fill in the `{placeholders}`; delete any section that is genuinely empty rather than
padding it.

```markdown
You are the orchestrator for the next phase of {topic or task}: {one-line mission}. Keep the
main line of context. Sub-agents do all the work and write their own artifacts; you brief,
gate-check, and keep the project-doc bookkeeping. Follow {orchestration skill, e.g.
skills/session-orchestration/SKILL.md}.

## Read first, in order — nothing else yet
1. {docs/design/CONTEXT.md, or the context doc the project AGENTS.md names} (what is true now)
2. {docs/design/<topic>/context.md} (rulings + document map)
3. {current stage file, e.g. docs/design/<topic>/working/plan.md} (which parts describe this workstream)
4. {the primary input artifact, e.g. the approved proposal} (note what it contains)
5. {supporting research doc} (note what it contains)
Defer until the phase that needs them: {code files (planning)}, {reader docs (final phase)}.

## Task
{Concrete deliverables with full absolute paths, branch names, repo states.}

## Ground rules
All sub-agents run on {model + slug}. {Access rule, if the project has one.} Freshly executed
outputs beat every document; treat any number you read as as-of its run date. If anything
material conflicts — a ruling seems contradicted, a number is far off, the scope changed —
stop and ask me; never resolve it silently.

The rulings recorded in {files} are settled. Apply them; do not re-open them.

## Decisions I owe you — ask at the plan gate, before anything launches
{Numbered list. The one thing no file can answer — this is the prompt's highest-value payload.}

## Out of scope
{Adjacent-and-tempting things NOT to touch. External actions gated on explicit go.}

## Sequence
{3–6 steps at task altitude, each gate stated exactly once, format-reference pointers to
exemplar artifacts instead of embedded examples.}

## Done means (verified from executed outputs, not documents)
{4–6 checkable criteria; no live counts or numbers that can go stale.}
```

Notes on filling it in:

- **Decisions I owe you** is why the prompt exists. Gather every open human decision into
  this one list, including unrelated-but-pending items ("ask alongside") so the human is
  interrupted once, at the gate.
- **Out of scope** should name the specific tempting adjacent artifact (the sibling
  module, the related doc) — models over-explore; explicit scope limits are the
  documented countermeasure.
- **Sequence** points to an exemplar artifact for format ("Format reference: {path}")
  instead of embedding an example — example-by-reference is cheap and effective.
- **Done means** criteria must be checkable from executed outputs. "The existing test
  suite still passes" is durable; "tests are 14/14" (illustrative) is a stale count waiting to happen.

## Per-Recipient-Model Tailoring

The skeleton above is **model-agnostic**. Tailoring for the recipient model is a thin
final pass over register and phrasing — not a different structure. Vendor guidance
for literal-instruction-following models (the basis for the baseline below): they follow
instructions *literally*, so dial back aggressive MUST/CRITICAL/all-caps language to a
normal register, prefer general instructions over prescriptive step-by-step scripts, and
give the *reason* behind a constraint so the model generalizes it correctly instead of
rules-lawyering the letter.

**Two different "models" — don't conflate them.** The MODEL PIN inside the prompt ("all
sub-agents run on {model + slug}" in Ground rules) says which model the *receiving
session's sub-agents* should use. The RECIPIENT model is the one the handoff prompt itself
is addressed to and styled for. They are independent: an orchestrator on one model can pin
its sub-agents to another.

| Recipient model | Tailoring notes |
|---|---|
| Any model covered by the baseline guidance | Apply the baseline in full — normal register, no all-caps emphasis, reasons attached to constraints, general instructions over scripts. State scope limits explicitly (over-exploration countermeasure). No further verified adjustments. |
| {new model} | Add only with a cited reason (see below). |

**Honest note: models in the same generation rarely need different handoff prompts.** The
same ~60–90 line markdown skeleton with the same register usually works for all of them.
Do not invent model folklore ("model X needs XML", "model Y prefers bullets") — none of
that is grounded unless you can cite it.

**Updating this table when a new model arrives:** add a row only when you have either
(a) published vendor guidance naming a behavioral difference, or (b) an observed,
reproducible failure of the baseline style on that model — and cite which in the row.
Default any new model in a covered family to the baseline. If a row's advice is just the
baseline restated, say "no further verified adjustments" rather than padding it.

## Pre-Flight Checklist

Run this before sending the handoff:

- [ ] Every ruling the prompt references exists in a project doc (search for it). Anything
      missing gets written into the project docs first — never into the prompt only.
- [ ] No live numbers, counts, or dated metrics inline. Durable phrasings only.
- [ ] Each gate and permission stated exactly once; no attribute-smuggled or duplicate
      gate language.
- [ ] "Decisions I owe you" is complete — every open human decision, including
      unrelated-but-pending ones, gathered at the gate.
- [ ] All paths are absolute; branch names and repo states (committed/uncommitted) stated.
- [ ] Out of scope names the tempting adjacent artifacts by name.
- [ ] No restated workspace rules, orchestration-skill contract, or project-doc content.
- [ ] The read-first list names no `archive/`, `evidence/`, or `CHANGELOG.md` files.
- [ ] Markdown headers only; no XML tags; no instructions in attributes.
- [ ] Total length roughly 60–90 lines.
- [ ] Recipient-model pass done (register check per the table above); model pin for
      sub-agents present and distinct from the recipient styling.
- [ ] Delivered in chat as a single ` ```markdown ` fenced block; no new project doc
      created (unless the owner explicitly asked to save it).

## Worked Anti-Pattern

Example (illustrative) for a small CSV-to-JSON command-line tool. Bad — a stale inline
count, an instruction smuggled into an attribute, and a gate also stated in two other
sections:

```markdown
<rulings decided="never re-ask">
- Existing tests: 14/14 passing as of this morning.
- Delimiter = comma by default, auto-detect off (restates the proposal's rule verbatim).
</rulings>
...
<execution_plan>
3. Gate: I approve the plan.   ← also in <contract> item 4 and the ask="..." attribute
</execution_plan>
```

Corrected — durable phrasing, prose instead of attributes, pointer instead of restatement,
gate stated once:

```markdown
## Ground rules
The rulings in the topic context.md (default delimiter, quoting rule, header
handling) are settled. Apply them; do not re-open them. Verify from freshly executed
outputs — the existing test suite must still pass (no counts quoted here; they go stale).

## Sequence
3. Gate: I approve the plan before anything launches. (Stated here and only here.)
```
