---
name: reppit-propose
description: >
  Generate 2-3 distinct, adversarial-reviewed solution proposals grounded in a
  research document, with trade-offs, validation steps, open questions, and a
  recommendation table; then ask the user to pick one and record the pick in a
  Decision section. Saves to docs/design/<topic>/working/proposal.md. Use as the second
  stage of the RePPIT method (Research, Propose, Plan, Implement, Test), after
  reppit-research, or when the user provides a research document and asks for
  solution proposals.
---

Adapted from ai_agents_repo @ b9a2286, 2026-10-21: no Evaluate stage (the user picks from the recommendation and the pick is recorded under `## Decision`), one review round. Stage files under `working/` and the pick recorded as a ruling per `design-memory` (ai_agents_repo @ 3e61f25, 2026-10-31).

# RePPIT Propose

Generate solution proposals grounded in an existing research document. Each proposal has concrete changes, evidence-backed trade-offs, validation steps, and open questions. The document gets one adversarial review, ends with a recommendation, and the user makes the pick.

## Trigger

Activate when:
- The user says "propose", "generate proposals", "what are the options", "solution proposals"
- The user provides a research document and asks for solution approaches
- This is the second stage of a RePPIT workflow (after `reppit-research`)

Do NOT use for:
- Research: run `reppit-research` first
- Implementation planning: that is `reppit-plan`, after the user has picked
- Quick "should I use A or B?" questions with no research behind them (just answer)

## Prerequisites

- Research document at `docs/design/<topic>/working/research.md`
- The user's goal and success criteria (they may arrive in the prompt)

If no research document exists, tell the user to run `reppit-research` first.

> **Output path.** RePPIT stages write to `docs/design/<topic>/working/<stage>.md`. If the
> project's `AGENTS.md` names another folder or language for design docs, follow it.
> Set `type: Proposal` in the frontmatter and carry **no `status`** field; the folder
> is the state. Layout, load order, and cycle close: skill `design-memory`.

## Behavior Contract

> - Every claim in a proposal must trace back to a finding in the research document, with section/line references
> - When the research does not cover something a proposal needs, call it out as an open question; do not fabricate claims about the codebase
> - Highlight what the research does and doesn't address for each proposal
> - Trade-offs must cite evidence (file paths, counts, system behaviors), not opinions
> - Validation steps must be concrete and runnable (a command, a test, or a specific test assertion)
> - The user's success criteria are scored for every proposal; never drop or soften one

## Workflow

### Step 1: Intake

1. **The request**: restate what the user wants built in one sentence.
2. **Success criteria**: list them verbatim. Each becomes a row of the recommendation table.
3. **The research document**: read it fully; note the relevant sections.

### Step 2: Parse research

Extract constraints (what any solution must work with), components and their consumers, dependencies and data flow, the comparison-table mismatch points, and open questions. Synthesize them into a **Context** section. It is not a restatement of the task; each bullet cites a research finding.

**Example context extraction (illustrative; the `--delimiter` task):**
- "The comma is assumed in two places: the `csv.DictReader` default in `convert.py` and a manual `split(\",\")` in `detect_header()` (research §3.2, §3.3)"
- "`cli.py` passes parsed flags to `convert()` as keyword arguments; adding one more is a local change (research §3.1)"
- "The JSON writer never sees the input format, so output is delimiter-agnostic (research §3.4)"

### Step 3: Synthesize the solution space

Generate 2-3 proposals that start from **different design philosophies**, not variations of one idea (e.g., "explicit flag" vs "auto-detect with an override" vs "named dialect presets"). Ground every change in a research finding. Order them from most to least aligned with the research constraints. If discussion surfaces another option, add it as a new proposal rather than replacing one.

### Step 4: One adversarial review round

Launch the `adversarial-reviewer` agent once with the proposal document, the research document, and the user's request and criteria. It checks that trade-offs are accurate against the code, assumptions are stated, validation steps would catch the risks, no risk is left uncovered, and the recommendation table is accurate. Skip this only if the user asks to, and say so in the header.

### Step 5: Fix

| Finding type | Action |
|-------------|--------|
| Factual error (stale count, wrong line reference) | Fix in the proposal |
| Missing coverage (a code path no proposal changes) | Add to the affected proposal(s) |
| Unstated assumption | Add to Context or Open Questions |
| Ambiguity (undefined default, vague meaning) | Clarify or remove it |
| Feasibility concern (library limits, test compatibility) | Add to the proposal's Trade-offs and Validation |

There is no second review round; verify your fixes against the code yourself.

Illustrative, from the `--delimiter` task: the reviewer found that Proposal 1 changed `csv.DictReader` but not the manual split in `detect_header()`, so the row was added; a tab typed as `--delimiter '\t'` arrives as two characters, so escape handling and a test were added.

### Step 6: Open questions, then the pick

1. Save the document at `docs/design/<topic>/working/proposal.md`.
2. If an open question needs the user's answer before a pick makes sense, ask it with the interview method in `grill-me`: one question at a time, each with your recommended answer. Record the answers in Context or Open Questions.
3. Present the recommendation table and your recommendation in chat, then **ask the user to pick**. Do not pick for them, and do not continue to planning on your own.
4. When the user answers, append the Decision section (template below) with their choice and their reason in their words. Record the pick as a ruling in its home, with a pointer back to `## Decision` (skill `design-memory` § Rulings). Tell the user the next stage is `reppit-plan`.

## Output Structure

```markdown
---
type: Proposal
---

# {Topic}: Solution Proposals

> **Task:** {one-line task statement}
> **Date:** {date}
> **Research source:** {path to research.md}; {key sections used}

## Context

**Request:** {one sentence}

**Success criteria:** {verbatim list}

**Key constraints from the research:**
- {constraint with research section reference}

## Proposal N: {Title}

### Overview
{2-3 sentences: what it does and why}

### Key Changes
| Component | Change |
|-----------|--------|
| {file/module} | {New / Modified / No change: what} |

### Trade-offs
| Benefit | Risk |
|---------|------|
| {benefit with evidence} | {risk with evidence} |

### Validation
1. {runnable command, test, or test assertion}

### Open Questions
1. {question; why it matters; what could go wrong}

## Recommendation

| Criteria | Proposal 1 | Proposal 2 | Proposal 3 |
|----------|-----------|-----------|-----------|
| {each success criterion, then 3-5 more dimensions} | | | |

{When to pick each proposal; gaps shared by all of them; your recommendation}

## Decision

- **Chosen:** Proposal {N}: {title}
- **Reason (the user's):** {reason}
- **Date:** {date}
```

### Writing effective proposals

- **Context extracts constraints from the research**; each bullet cites a finding.
- **Trade-offs are symmetric.** Every benefit row has a risk row.
- **Validation is runnable.** A command, test, or file check, not "verify correctness".
- **Open Questions show honesty.** A proposal with none has not been challenged.
- **Consistent dimensions.** Score every proposal on every row.
- **Say what a proposal leaves untouched** when it solves a broader problem than the task.

## Quality Gates

- [ ] Every proposal traces its motivation to a research finding
- [ ] Every trade-off cites evidence
- [ ] Every validation step is runnable
- [ ] Review round completed (or skipped at the user's request) and must-fix findings addressed
- [ ] Every success criterion is a row of the recommendation table
- [ ] Questions that needed the user were asked with `grill-me`, or are listed as open
- [ ] The user picked; `## Decision` records the choice and their reason
- [ ] Saved to `docs/design/<topic>/working/proposal.md`
