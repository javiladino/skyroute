---
name: reppit-test
description: >
  Check a finished implementation against its plan and record the result in
  docs/design/<topic>/working/test.md: one row per check with its command, result, and
  PASS or FAIL, and an overall verdict. Runs the verify command and the
  protected-test diff, the behavior checks named in AGENTS.md, one check per
  success criterion from the proposal, and an adversarial-reviewer review of
  the diff against plan.md. Use as the fifth and last stage of RePPIT
  (Research, Propose, Plan, Implement, Test), after reppit-implement, or when
  asked to test, verify, or sign off an implemented plan.
---

Written for dec-ai-workshop, 2026-10-21: the course's Test stage (the library has none).

# RePPIT Test

Prove that the implementation does what the plan and the proposal promised, with commands this session runs, and write the evidence down. Test does not fix anything and does not commit.

## Trigger

Activate when:
- The user says "test", "verify", "sign off", "run the checks" for an implemented plan
- This is the fifth stage of a RePPIT workflow (after `reppit-implement`)

Do NOT use for:
- Writing or changing code: a failing check goes back to the user (and from there to `reppit-implement`)
- Running one test while coding: just run it

## Prerequisites

- `docs/design/<topic>/working/plan.md` (its Testing Strategy is the list of checks) and `proposal.md` (its success criteria and `## Decision`)
- The project's `AGENTS.md`: the verify command, the behavior checks, and which files must not change
- The **base** to diff against: the branch or commit the work started from. If neither the plan nor the user names it, ask.

## Behavior Contract

> - Every result comes from a command this session ran; never copy a result from a document or a sub-agent report
> - Run each check exactly as written. A check that needs Docker is N/A when `docker info` fails, and N/A does not fail the verdict. Any other check that cannot run is FAIL, with the reason; never skip a row silently
> - Do not change code, tests, or fixtures to make a check pass; report the failure instead
> - A temporary change made only to run a check (for example the "add a dataset" check) is undone afterwards, and `git status` shows it is gone
> - Do not commit or push

## Workflow

### Step 1: Collect the checks

Build the list from four sources, in this order, and keep every check the plan's Testing Strategy names:

1. **Suite and protected files.** The verify command exits 0, and the diff of the protected test files against the base is empty (for example `git diff <base> -- 'tests/**/test_*.py'` prints nothing).
2. **Behavior checks** named in `AGENTS.md`. The Docker checks there run only when `docker info` succeeds; otherwise each is a row with status N/A.
3. **Success criteria** from `proposal.md`, one check each. A criterion like "adding a new X is configuration only" is checked by actually adding X with its fixture and test, then confirming with `git diff --stat` that only the configuration location `plan.md` names (plus the new fixture and test) changed. Undo the change afterwards.
4. **Review.** Launch the `adversarial-reviewer` agent once with `plan.md`, `proposal.md`, and the full diff against the base. Its verdict is the row's result: GO is PASS; GO-WITH-FIXES is PASS only if every listed fix is outside the plan's scope and is recorded as follow-up; NEEDS-REVISION is FAIL.

### Step 2: Run them

Run each check, one command at a time. Record the command, the relevant part of its output (a count, a status code, a key, the empty diff), and PASS or FAIL. Do not stop at the first failure; run every check so the report is complete.

### Step 3: Write test.md

Save `docs/design/<topic>/working/test.md`:

```markdown
---
type: Test
---

# {Topic}: Test Report

> **Date:** {date} · **Base:** {branch or commit} · **Plan:** docs/design/<topic>/working/plan.md

## Verdict: PASS | FAIL

{one or two sentences: what was proven, or which checks failed}

## Checks

| # | Check | Source | Command | Result | Status |
|---|-------|--------|---------|--------|--------|
| 1 | Verify command passes | AGENTS.md | `...` | `N passed` | PASS |
| 2 | Protected tests unchanged | plan.md | `git diff <base> -- ...` | empty | PASS |

## Review

{the reviewer's verdict and its findings, each marked fixed, follow-up, or rejected with a reason}

## Follow-up

{anything that failed or was deferred; "None." if empty}
```

The verdict is PASS when every row is PASS or N/A and the verify row is PASS. A single FAIL makes the verdict FAIL.

### Step 4: Report

Tell the user the verdict, list any failing rows, and stop. Committing is the user's call. On PASS, offer to close the cycle (skill `design-memory`, Close a topic); do it only when the user agrees.

## Quality Gates

- [ ] Every check in the plan's Testing Strategy has a row
- [ ] The protected-file diff against the base was run and its output recorded
- [ ] Every success criterion from `proposal.md` has a row, checked by doing it, not by reading the code
- [ ] Temporary changes were undone and `git status` confirms it
- [ ] The review ran once and its verdict is recorded
- [ ] Every result came from a command this session ran
- [ ] Nothing was committed or pushed
