---
name: adversarial-review
description: >
  Challenges finished code and plans. Code review: read the diff, check claims
  against the code, run the project's tests, and report findings with severity.
  Plan review: look for missing cases, unstated assumptions, and claims about
  the code that the code does not support. Ends with GO, GO-WITH-FIXES, or
  NEEDS-REVISION. Use when asked to review, challenge, verify, find holes, or
  stress-test a diff, plan, or design doc.
---

Adapted from ai_agents_repo @ b9a2286, 2026-10-21: code and plan review only; the SQL, prose, and penguins material was dropped.

# Adversarial Review

Find what is wrong. The `adversarial-reviewer` agent uses this skill, and a session can follow it directly. Report; do not fix, and do not change any file.

## Pick a mode

- **Code review** when the input is a diff, a branch, or code files.
- **Plan review** when the input is a plan, a spec, or a proposal.
- **Both** when a plan names existing files: review the plan, then check its claims against those files.

## Code review

1. Read the diff and say, in one sentence, what the change is trying to do.
2. Check each claim against the code. A file path, a line, a default, and a status code are claims. Open the file.
3. Look for the cases the change forgets: empty input, a bad value, a repeated call, an error halfway through.
4. Run the project's verify command yourself. The author's report of a passing test is not evidence.
5. Say what you could not check, and why.

## Plan review

1. Restate the goal and the success criteria in the plan's words.
2. For each step, ask what happens when it fails, what it assumes, and what it leaves out.
3. Check every claim about existing code against the code. "The handler does X" is a claim.
4. Flag a sentence that two people could implement differently.
5. Check that the test plan names a command and an expected result for each success criterion.

## Report

One finding per problem:

- **Severity:** high (the change is wrong or the plan cannot be built as written), medium (a student or a later step will hit this), low (noise or a nit).
- **Where:** file and line, or the plan section.
- **Evidence:** what you read or what the command printed.
- **What would fix it:** one sentence. Do not apply it.

End with a verdict:

- **GO:** nothing of medium or high severity.
- **GO-WITH-FIXES:** the direction is right and the fixes are listed.
- **NEEDS-REVISION:** a high finding changes the approach, or a success criterion cannot be checked.

## Do not

- Edit, create, or delete files, or commit.
- Treat a document's description of the code as fact.
- Pad the report. "Nothing wrong here" is a valid section.
