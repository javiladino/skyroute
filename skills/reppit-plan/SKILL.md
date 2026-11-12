---
name: reppit-plan
description: >
  Draft an implementation plan document from the proposal the user picked,
  using the sibling design_doc_template.md structure. Confirms scope, fills
  Current Context from the research, maps Design Decisions from the proposal,
  lists every file change with line references, orders phases by dependency,
  and names the checks reppit-test will run. Only fills sections relevant to
  the change. Use as the third stage of RePPIT (Research, Propose, Plan,
  Implement, Test), after the user has picked a proposal, or when asked to plan
  an implementation.
---

Adapted from ai_agents_repo @ b9a2286, 2026-10-21: reads the pick from `proposal.md` `## Decision` (no Evaluate stage, no autonomous mode; with no answer, ask), and the Testing Strategy names the checks `reppit-test` runs. Stage files under `working/` per `design-memory` (ai_agents_repo @ 3e61f25, 2026-10-31).

# RePPIT Plan

Draft an implementation plan from the chosen proposal. The plan uses the structure of `design_doc_template.md` (in this skill's folder), filled with context from the research and decisions from the proposal. Sections that do not apply say "Not applicable for this change." The output is a `.md` document, not code.

## Trigger

Activate when:
- The user has picked a proposal and says "plan this", "draft a plan for Proposal N"
- The user asks "what needs to change to implement this?"
- This is the third stage of a RePPIT workflow (after `reppit-research` and `reppit-propose`)

Do NOT use for:
- Research (`reppit-research`) or proposals (`reppit-propose`)
- Writing code (`reppit-implement`)

## Prerequisites

- `docs/design/<topic>/working/proposal.md` with a `## Decision` section naming the chosen proposal
- `docs/design/<topic>/working/research.md` for codebase context
- `design_doc_template.md`, next to this file

If there is no proposal, tell the user to run `reppit-propose` first.

> **Output path.** RePPIT stages write to `docs/design/<topic>/working/<stage>.md` (for
> example `docs/design/delimiter-option/working/plan.md`). If the project's `AGENTS.md`
> names another folder or language for design docs, follow it. Set `type: Plan` in the
> frontmatter and carry no `status` field; the folder is the state. Layout, load order,
> and cycle close: skill `design-memory`.

## Behavior Contract

> - Do not implement any change; only produce a plan document
> - Only include changes that the chosen proposal directly requests
> - Keep solutions simple and focused; do not expand scope beyond the proposal
> - Populate template sections only when they are relevant to this change
> - Include explicit file paths and line numbers in "Files Changed"; this is the most important section
> - Verify every file path and line range against the actual codebase before writing them in the plan
> - Every validation step is a single, non-destructive command the project allows: a test, build, lint, or read-only check. No `;`, `&&`, or pipe chains, no deletes, no temporary-folder setup and teardown. When a check needs fixtures, make it a test in the project's test suite rather than a shell one-liner

## Workflow

### Step 1: Scope confirmation

1. **Which proposal was chosen?** Read `## Decision` in `proposal.md`. If it is missing, ask the user to pick; do not pick for them.
2. **What is in scope?** The concrete changes from the chosen proposal's Key Changes table.
3. **What is out of scope?** State what is deferred, even if the proposal mentions it.
4. **Which checks prove it works?** Collect the success criteria from the proposal's Context, the behavior checks the project's `AGENTS.md` names, and the proposal's Validation steps.

When several scope questions are open, resolve them with the `grill-me` interview: one question at a time, each with your recommended answer. With no answer from the user, ask again; never assume.

### Step 2: Template intake

Read `design_doc_template.md`, `research.md`, and `proposal.md`. Map the sections:

| Template Section | Source |
|-----------------|--------|
| Current Context | Research: summary and inventory |
| Functional Requirements | Proposal: Overview, success criteria |
| Non-Functional Requirements | Proposal: Trade-offs (performance, memory, scalability) |
| Design Decisions | Proposal: Trade-off resolutions, the user's reason in `## Decision` |
| Core Components | Proposal: Key Changes table |
| Data Models | Proposal: data format, schema, or configuration changes (if any) |
| Integration Points | Research: data flow diagrams |
| Files Changed | Proposal: Key Changes, verified against the code with line numbers |
| Implementation Plan | Proposal: validation steps ordered by dependency |
| Testing Strategy | Success criteria, `AGENTS.md` behavior checks, proposal Validation |
| Observability / Security / Rollout | Only if the proposal touches them |
| Future Considerations | Proposal: Open Questions |
| References | research.md, proposal.md, the task |

### Step 3: Draft the plan

**Always populated:** Current Context (3 to 5 bullets), Requirements, Design Decisions (one subsection per resolution, with rationale and alternatives considered), Files Changed (Step 4), Implementation Plan (phases ordered by dependency, each with one validation command), Testing Strategy (below), References.

**Conditional:** Data Models, Integration Points, Observability, Security, Rollout. When one does not apply, write `Not applicable for this change.`

**Testing Strategy is the contract for `reppit-test`.** List every check it will run, each with the exact command or assertion and the expected result:
1. The project's verify command, and any rule about which test files must not change (for example `git diff <base> -- 'tests/**/test_*.py'` is empty).
2. The behavior checks named in `AGENTS.md`.
3. One check per success criterion in the proposal (for example "add a new dataset; the diff touches only {the configuration location this plan names}").

**For analysis plans (notebooks, reports)**, add **Mockups** (rendered chart mockups watermarked "plausible-but-FAKE") and **Conclusions we could draw**.

### Step 4: Files Changed audit

For every file in the chosen proposal's Key Changes table:

1. **Verify it exists.** For a new file, write "NEW: does not exist yet."
2. **Read it** and identify the line ranges that change.
3. **Record** in this format (illustrative, for the `--delimiter` task):
   ```
   - cli.py (lines 12-24: argument parser; add --delimiter with default ",")
   - convert.py (lines 8-15: pass the delimiter to csv.DictReader; lines 30-38: use it in detect_header() instead of split(","))
   - tests/test_convert.py (lines 40-58: add semicolon and tab cases)
   ```
4. **Cross-check** against the research inventory so no file is missed.

A file the proposal marks "No change" does not appear in Files Changed.

### Step 5: Deliver

Save the plan at `docs/design/<topic>/working/plan.md`, summarise the phases in chat, and tell the user the next stage is `reppit-implement`.

## Output Structure

The plan mirrors `design_doc_template.md`, with this frontmatter and header:

```markdown
---
type: Plan
---

# {Topic}: {Feature} Design Document
```

The `## References` section links `research.md`, `proposal.md`, and the task.

## Quality Gates

- [ ] The chosen proposal comes from `## Decision` (or the user's explicit pick in chat)
- [ ] Every phase's validation step is a single, non-destructive command or test
- [ ] Every file in Files Changed verified against the code with line numbers
- [ ] No implementation code in the plan, only descriptions
- [ ] Every populated section traces back to the research or the proposal
- [ ] Inapplicable sections say "Not applicable for this change"
- [ ] Phases are ordered by dependency
- [ ] Testing Strategy names every check `reppit-test` will run, with its command and expected result
- [ ] Saved to `docs/design/<topic>/working/plan.md`
