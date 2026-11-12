---
name: reppit-implement
description: >
  Execute an implementation plan: read plan.md, run its phases in order (in
  this session for a small plan, one implementer sub-agent per phase for a
  larger one), run the plan's verification commands after each phase, track
  drift against Files Changed, and hand over to reppit-test. Use as the fourth
  stage of RePPIT (Research, Propose, Plan, Implement, Test), after reppit-plan
  has produced plan.md, or when the user says "implement this plan".
---

Adapted from ai_agents_repo @ b9a2286, 2026-10-21: small plans run in the current session (sub-agents per phase only for larger ones), no `evaluation.md`, the final review moves to `reppit-test`. Stage files under `working/` per `design-memory` (ai_agents_repo @ 3e61f25, 2026-10-31).

# RePPIT Implement

Execute a plan.md phase by phase. The plan already says what to build; this skill builds it, verifies each phase, and keeps the result honest against the plan.

## Trigger

Activate when:
- The user says "implement this plan", "execute the plan", "build what's in the plan"
- The user gives a path to a plan.md and asks to execute it
- This is the fourth stage of a RePPIT workflow (after `reppit-plan`)

Do NOT use for:
- Deciding what to build: use `reppit-propose` and `reppit-plan` first
- Exploratory coding without a plan: just code directly
- Checking the finished result: that is `reppit-test`

## Prerequisites

- `docs/design/<topic>/working/plan.md` with an **Implementation Plan** (numbered phases) and **Files Changed** (paths with line numbers)
- The project's `AGENTS.md`: verify, lint and test commands, conventions, boundaries

If no plan exists, tell the user to run `reppit-plan` first.

> **Input paths.** RePPIT stage files live at `docs/design/<topic>/working/<stage>.md`;
> this skill reads `plan.md` and its siblings `research.md` and `proposal.md`. If the
> project's `AGENTS.md` names another folder, read from there. Layout and load order:
> skill `design-memory`.

## Behavior Contract

> - Follow the plan exactly; do not expand scope beyond what the plan specifies
> - If a phase fails or produces unexpected results, stop and report to the user; do not improvise a fix
> - Do not commit or push without explicit user approval
> - Track what was done vs what the plan specified; surface any drift

## Workflow

### Step 1: Read the plan

Extract the phases and their tasks, the Files Changed entries, the verification commands (Testing Strategy, each phase's validation step, `AGENTS.md`), and the context (task, chosen proposal, design decisions). Build a checklist of phases.

### Step 2: Decide where the phases run

| Plan size | Where it runs |
|-----------|---------------|
| Small: one to three phases, a handful of files (the usual case) | In this session, phase by phase |
| Larger | One implementer sub-agent per phase (the one `AGENTS.md` names, otherwise a general-purpose sub-agent), briefed with the template below |

Tell the user which one you chose before starting. Verification always runs in this session.

### Step 3: Execute phases in order

For each phase:

1. Do (or brief) exactly the phase's tasks, touching only the files the plan lists for it.
2. Run the phase's validation command yourself; never accept a sub-agent's report as proof.
3. Run `git diff --stat` and compare it with the phase's Files Changed. Files changed outside the plan, or planned files left untouched, are **drift**: report it to the user before continuing.
4. Mark the phase done.

If a phase fails, report what was attempted, what went wrong, and where (file and line). Do not retry automatically or improvise; ask the user whether to fix and retry, skip, or stop.

### Step 4: Hand over to Test

When every phase is done:

1. Run the project's verify command and lint command once more.
2. Summarise: phases completed, files changed (`git diff --stat`), commands run and their results, any drift and how it was resolved.
3. Tell the user the next stage is `reppit-test`, which runs the plan's Testing Strategy and the review. Do not commit; commits wait for the user's approval after Test.

## Implementer Brief Template (larger plans only)

Example values use the illustrative `--delimiter` task:

```
## Context
- Task: add a --delimiter option to the CSV-to-JSON command-line tool
- Proposal: Proposal 1, a single --delimiter flag, default ","
- Plan: docs/design/delimiter-option/working/plan.md

## This Phase
Phase 1: Accept and pass the delimiter

### Tasks
1. Add --delimiter to the argument parser with default ","
2. Pass the delimiter to the CSV reader and to detect_header()

### Files to Change
- cli.py (lines 12-24: argument parser)
- convert.py (lines 8-15: csv.DictReader call; lines 30-38: detect_header())

### Verification
- Run the project's verify command; it must pass

### Behavior
- Follow the plan exactly; do not add, remove, or modify anything not listed above
- If something in the plan seems wrong or incomplete, stop and report instead of improvising
- Follow the project's AGENTS.md conventions; do not commit or push
- End with a summary: files changed, commands run and their results, anything you could not do
```

## Quality Gates

- [ ] Every phase ran in order, and each phase's validation command passed when run by this session
- [ ] Every file in Files Changed was changed, and no file outside the plan was (checked with `git diff --stat`)
- [ ] Drift, if any, was reported to the user and resolved
- [ ] Verify and lint commands pass at the end
- [ ] Nothing committed or pushed; the user was pointed to `reppit-test`
