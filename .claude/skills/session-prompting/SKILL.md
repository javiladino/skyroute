---
name: session-prompting
description: >
  Writes the prompt the owner gives another agent to run a task, delivered in chat as one
  fenced markdown block, never a file. The target is a ticket, a repo, a sub-agent, or
  another chat. Two modes. Task prompt (default, light): infers five fields and a "Done
  means" check from the conversation and files, asks only about decisions that change the
  prompt (one round, at most four questions, each with a recommended answer), then fills
  a 15–40 line template adjusted to the target. Handoff: the prompt that boots a fresh
  session to continue multi-phase work, with a read-first list, the decisions the owner
  owes, gates, model tailoring, and a pre-flight checklist. Use when the owner says "help
  me prompt an agent", "write a prompt for X", "I want an agent to implement X", "prompt
  for the next session", "continuation or kickoff prompt", or "hand this off". Not for a prompt that opens a discussion with a specialized agent
  (agent-discussion), or for sub-agent briefs inside an orchestrated session
  (session-orchestration).
---

Adapted from ai_agents_repo @ 1cdedc9, 2026-11-06: replaces the course's `session-handoff` copy; dropped the `meta-orchestration` pointer; the handoff template names the orchestration skill by its path `skills/session-orchestration/SKILL.md`.

# Session Prompting

How to write the prompt that gets another agent to do a piece of work: a task prompt for
one deliverable, or a handoff prompt that boots a fresh session to continue multi-phase
work. The method rests on published vendor guidance on context engineering and prompting,
and on an adversarial review of a real handoff prompt over three iterations: the first
failed on stale inlined facts, the second on duplication and XML ceremony, and the third
became the handoff template in [references/handoff.md](references/handoff.md).

## Trigger

Activate when the owner asks for a prompt that another agent, session, or sub-agent will
run ("help me prompt an agent to implement X", "write a prompt for X"); when asked for a
handoff prompt, continuation prompt, or "prompt for the next session"; when closing an
orchestrator session whose work continues elsewhere; or when reviewing someone else's
task or handoff prompt.

## Choose the mode

| Situation | Mode |
|---|---|
| One deliverable that starts now: implement, fix, research, analyse, review a change | Task prompt (default) |
| Work already in progress that a fresh session continues, with rulings, gates, and phases | Handoff |
| The owner says "hand this off", "continuation prompt", or "prompt for the next phase" | Handoff |
| The session talks something through with the owner instead of doing the work | Not this skill: `agent-discussion` |
| A brief for a sub-agent inside an orchestrated session | Not this skill: `session-orchestration` |

When unsure, start in task prompt mode. If the draft needs open owner decisions, more than
one gate, or a phase sequence, or grows past ~40 lines because of them, switch to handoff.
If the choice is still unclear, add it to the one round of questions, with handoff
recommended only when a later phase depends on rulings made in this session.

## Delivery — chat, not a file (both modes)

The filled template **is** the deliverable. Post it in the chat as a single fenced
markdown block so the owner can copy-paste it where it will run:

````markdown
```markdown
{filled prompt}
```
````

A one-line lead-in before the fence ("Copy everything inside the block below") is fine.
Do not write the prompt to `handoff.md`, a draft under `working/`, or any other file. Do
not put extra commentary inside the fence.

**Why:** prompts are disposable (principle 1). Project docs hold lasting state; the prompt
is a boot script the human pastes once. Writing it as a document duplicates the template,
mixes disposable instructions with durable rulings, and makes the owner copy from a file
instead of chat. Some projects already keep a durable `handoff.md` with a different job
(for example, a problem list) — this skill never creates or overwrites that file.

Exception: write the prompt to a file only if the owner explicitly asks to save it.

## Core Principles (both modes)

These come from published vendor guidance (for example Anthropic's engineering post
"Effective context engineering for AI agents" and its prompting best-practices doc,
especially the multi-context-window sections) plus the failure analysis above.

1. **The prompt carries only what files cannot.** Open decisions the human owes, gates,
   the concrete task, model pins, and out-of-scope warnings. Everything else — rulings,
   research, numbers, history — lives in project docs the prompt points at. If a ruling is
   not yet written down, **write it into its one home in the project docs first** (skill
   `design-memory` § Rulings), then point at it. State belongs in files; prompts are
   disposable.
2. **Ordered read-first list with explicit deferral.** Fresh sessions are very good at
   discovering state from the filesystem. The strongest bootstrap is a prescriptive "read
   these, in this order, nothing else yet" list with a one-line note on what each file
   holds, plus "defer until the phase that needs them" for everything else. When the work
   keeps its artifacts in `docs/design/` (or the folder the project `AGENTS.md` names), this
   list follows skill `design-memory` (§ Load protocol): the project `CONTEXT.md`, the topic
   `context.md`, then the named `current/` or `working/` files. The ordered items are
   levels L0–L2 and the deferral line is L3. Never name `archive/`, `evidence/`, or
   `CHANGELOG.md` — they are off the boot path.
3. **Escape hatch.** One sentence: if anything material conflicts — a ruling seems
   contradicted, a number is far off, the scope changed — stop and ask; never resolve
   silently. This replaces any precedence ladder. Do not build a multi-tier "X beats Y
   beats Z" table; in the reviewed prompt the ladder's "docs beat prompt" tier collided
   with its own "never re-ask these rulings" section.
4. **Executed outputs beat documents.** State it once: freshly executed outputs beat every
   document; treat any number you read as as-of its run date. Never inline a live count or
   metric in the prompt — in the first iteration one went stale within an hour.
5. **Markdown headers, no XML.** Vendor guidance treats XML tags and markdown headers as
   interchangeable section delimiters, and formatting matters less with each model
   generation. The documented XML win is separating *mixed content types* (pasted
   documents, examples, variable inputs). A task or handoff prompt is homogeneous instructions
   from one author, so headers win on readability. **Never smuggle instructions into tag
   attributes** (`<rulings decided="never re-ask">` has no basis in any guidance; make it
   the section's first sentence instead).
6. **Each gate or permission stated exactly once.** Pick    the section where a gate or a
   permission lives (in a handoff, gates usually in the Sequence, permissions in Ground
   rules or Out of scope; in a task prompt, both in Constraints) and state it there only.
   The reviewed second iteration stated the plan-approval gate three times — contract,
   attribute, and execution plan — which literal-instruction-following models treat as
   three rules to reconcile.
7. **Don't duplicate what the session already gets.** Always-injected workspace rules,
   the orchestration skill's own contract, and the content of the files in the read-first
   list are already in the recipient's context. One line of safety redundancy for
   sub-agent briefs is defensible; whole restated sections are not.
8. **Length follows the mode.** Task prompt ~15–40 lines; handoff ~60–90 lines. Minimal
   does not mean short — it means the minimal set that fully outlines expected behavior.
   In practice each template lands in its range.

## Task Prompt Mode (default)

### 1. Identify the five fields and Done means

| Field | What it holds | Infer it from |
|---|---|---|
| Goal | What to do or produce, as an action, with the why: the motivation, or actual vs desired behaviour for a bug | The owner's request and the conversation |
| Target | A ticket agent, a repo agent, a sub-agent, or a new chat in another tool or model | Where the owner said it will run; if unstated, ask (step 2) |
| Context | Only what the receiver would not find on its own: files in reading order, findings, ruled-out options; if it can read this conversation, say only what is left | Files read or changed in this conversation, the ticket body, the project docs folder |
| Constraints | Scope, hard boundaries with a reason, one ask rule, one stop rule | The owner's words, the project `AGENTS.md` (point at it, do not restate it), rulings, branch state, anything irreversible |
| Done means | A check the receiver can run or observe: a command and its expected result, or a testable statement; kept apart from Output | The goal: the test, command, or behaviour that proves the work is finished |
| Output | The artifact and a short reply: what changed, checks run with results, assumptions, anything not verified | The goal: a code change → an uncommitted change, or a pull request when the target runs unattended; research → a doc at a named path; a question → a table in chat |
Cut role or persona lines, conventions the receiver loads from repo instruction files
(point at the file), step lists for an investigation (hand over the question), and bans
on actions it would never consider. Add a mode line ("plan first and stop") only for
multi-file or unclear work; an effort hint only where the tool has one.

Adjust for the target:

- **Ticket agent**: the ticket is the prompt; point at it and add only what it lacks (why,
  boundaries, Done means). One ticket, one deliverable: split broad work; keep ambiguous
  or security-sensitive work out of an unattended agent. Stop rule: a finished change, or
  one blocker and a targeted question.
- **Repo agent**: point at the repo instruction file instead of restating conventions;
  give the absolute path, branch, committed state, and the files in reading order.
- **Sub-agent**: only what its role needs, but always the shared project background. Copy
  the owner's constraints word for word. A lookup gets the exact command; an investigation
  gets the question; never "based on your findings, fix it". Inside an orchestrated
  session, use the briefing template in `session-orchestration` (§ Decompose and brief).
- **New chat in another tool or model**: assume nothing loads automatically. Put the rules
  that matter inline, with an absolute-path read-first list; label each carried claim
  verified or unverified. When a person watches, end with "restate the goal and your
  first step, then wait".

A decision made in this chat that later work relies on is a ruling: write it to its home
first (principle 1). Background that matters only to this one task goes in the prompt.

### 2. Infer first, then ask once

Look up every fact you can find (paths, commands, ticket text, table names) instead of
asking for it. Ask only about decisions whose answer would change the prompt: the goal
when two readings lead to different work, the target when it is not stated, and any hard
boundary (what must not change, what needs approval). Ask in one round: at most four
numbered questions, goal first, each with your recommended answer, worded so that "yes"
accepts it. Never ask about format, length, or anything with a conventional default;
choose it and say so. If nothing material is missing, ask nothing: post the prompt with a
one-line "Assumed:" list under the block. Settle the goal before the prompt leaves.

Example (illustrative):

> 1. **Goal** — I read "pretty output" as indented JSON, not coloured output. Yes?
> 2. **Boundary** — I recommend the default output stays byte-for-byte unchanged, because
>    existing scripts parse it. Yes?

### 3. Fill the template

Delete any line with nothing real to say. ~15–40 lines is a guideline, not a measured
optimum: keep every field that carries information.

```markdown
{Goal: what to do or produce, on what, as an action.} Why: {the motivation, or actual vs
desired behaviour}.
{Optional mode line: Plan first, then stop for my go before you edit.}

## Where you work
{Target: {abs repo path}, branch {branch}, {committed | uncommitted changes present} — or
ticket {reference}.}

## Read first, in order — nothing else yet
1. {abs path or ticket} ({what to look for there})
2. {abs path} ({what to look for there})
Conventions: follow {instruction file}; they are not repeated here.
Defer until needed: {files}.

## Background
{Only what no file says: a decision, a ruled-out option, a known trap. In a new chat,
mark each carried claim verified or unverified.}

## Constraints
In scope: {...}. Out of scope: {only what you might plausibly touch}.
{Hard boundary}, because {reason}. {Commits, pushes, and pull requests need my go | unattended: open a pull request from {branch} and stop.}
Ask me before {irreversible or shared-state action}; on anything else unclear, proceed and
list your assumptions. If anything material conflicts with this prompt, stop and ask;
never resolve it silently. Stop when the Done means checks pass, or at one blocker plus
one targeted question.

## Done means
- {command} → {expected result} | {testable statement}

## Output
{Artifact and place: an uncommitted change on {branch} | a doc at {abs path} | a table in
chat.} Reply in about {N} lines: what changed, checks run with results, assumptions,
anything not verified.
```

### Worked example (abridged)

Toy domain: a small CSV-to-JSON command-line tool. Owner: "I want an agent to implement a
`--pretty` flag. Write the prompt for another chat on this repo." The target is a repo
agent; every fact came from the repo; the owner answered the two questions above "yes".

```markdown
Add a `--pretty` flag to the CSV-to-JSON tool that indents the JSON output. Why: people
read the output by eye and pipe it through a second tool to format it.

## Where you work
{abs path}/csv2json, branch `feat/pretty-flag`, no uncommitted changes.

## Read first, in order — nothing else yet
1. {abs path}/csv2json/src/cli.py (the argument parser; the flag goes here)
2. {abs path}/csv2json/tests/test_cli.py (the test pattern to follow)
Conventions: follow {abs path}/csv2json/AGENTS.md; they are not repeated here.

## Constraints
In scope: the parser, the writer, and their tests. No new dependencies.
Keep the default output byte-for-byte unchanged, because existing scripts parse it.
Commits and pushes need my go. Ask me before you change any existing flag; on anything
else unclear, proceed and list your assumptions. Stop when the Done means checks pass, or
at one blocker plus one targeted question.

## Done means
- `csv2json --pretty tests/fixtures/two_rows.csv` prints both rows indented two spaces (illustrative).
- `csv2json tests/fixtures/two_rows.csv` prints the same bytes as before the change.
- The test suite passes, including a new test for `--pretty`.

## Output
An uncommitted change on `feat/pretty-flag`. Reply in about five lines: what changed,
checks run with results, assumptions, anything not verified.
```

Under the block: `Assumed: reply length five lines; no README change.`

### Task prompt checklist

- [ ] Facts looked up, not asked; at most four decision questions in one round, goal
      first, each with a recommended answer; guesses in an "Assumed:" line.
- [ ] Goal is one action with its why and only one reading; target adjustment applied.
- [ ] Context points at files in reading order, each with what to look for; conventions
      by pointer; no pasted file content; no live numbers.
- [ ] Constraints: scope, boundaries with reasons, the owner's limits word for word, one
      ask rule, one stop rule; each gate and permission stated once.
- [ ] Done means is a runnable or observable check, separate from Output; Output asks for
      the reply (changes, checks with results, assumptions, not verified).
- [ ] Re-read as the receiver: it can start without asking. No leaked writer notes or
      out-of-role facts, no dropped shared background, no "read X" inside X, no drifted
      owner constraint, no stale inlined fact, no "as discussed", no bare folder pointer,
      no retyped identifier (branch, file, ticket, table).
- [ ] ~15–40 lines as a guideline; delivered in chat as one fenced markdown block.

## Handoff Mode

Use it when a fresh orchestrator or agent session continues multi-phase work. On top of
the five fields it carries the orchestration contract (parent keeps context, sub-agents
execute and write their own files), an ordered read-first list built from the project's
design docs, the decisions the owner still owes (asked once, at the plan gate), the out-of-
scope list, a phase sequence with each gate stated once, checkable "done means" criteria,
and a sub-agent model pin kept distinct from the recipient model. Target ~60–90 lines.

Read [references/handoff.md](references/handoff.md) and follow it: the template, notes on
filling it in, per-recipient-model tailoring, the pre-flight checklist, and a worked
anti-pattern.

## What This Skill Does NOT Do

- Write a project doc (`handoff.md` or otherwise). The prompt goes in chat, in a fenced
  markdown block. Existing `handoff.md` files that hold other durable content are out of
  scope — do not create, overwrite, or treat them as this skill's output.
- Write sub-agent briefs inside an orchestrated session (see `session-orchestration` —
  briefs are self-contained task instructions; outside an orchestrated session, a task
  prompt for a sub-agent uses the Sub-agent adjustment above).
- Write a prompt that opens a discussion with a specialized agent rather than doing or
  continuing the work (see `agent-discussion`; it reuses this skill's shared rules).
- Define the orchestration workflow itself (`session-orchestration`).
- Manage the content of project docs — this skill only requires that rulings live there
  before the prompt points at them.
- Do the task itself. It writes the prompt; the recipient does the work.
