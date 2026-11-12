---
name: agent-discussion
description: >
  Writes the prompt that opens a new session with a specialized agent the owner wants to
  talk something through with — domain expert, code tutor, reviewer, or ideation partner —
  delivered in chat as one fenced markdown block. Points at an agent in your project
  (agents/<group>/<name>.md, then .claude/agents/ or .cursor/agents/) when one fits; otherwise researches current best
  practices for the tool or domain, writes them to a note, and builds the prompt on it.
  Covers session outcomes, interaction style, the read-first list, read-only permissions,
  and the notes the session writes on "wrap up". Use when the owner asks for a prompt to discuss, review, learn,
  brainstorm, or be walked through something with another agent, e.g. "write a prompt to
  talk this plan through with a reviewer", "I want a tutor to walk me through this code".
  Not for continuing or implementing work (session-prompting), holding the conversation
  yourself (the matching agent does that), or sub-agent briefs (session-orchestration).
---

Adapted from ai_agents_repo @ 1cdedc9, 2026-11-06: the agent lookup is `agents/<group>/<name>.md` in this repo (then `.claude/agents/` or `.cursor/agents/`), promotion rules say "write an agent file / a skill" without naming creator skills, the plan-review example reads the pick under `## Decision` in `proposal.md` and uses a reviewer agent from your fork.

# Agent Discussion

Write the prompt the owner pastes into a fresh chat to talk something through with a
specialized agent. The session is a conversation: the agent helps the owner understand,
challenge, decide, or ideate. It does not continue the work. The prompt is disposable;
lasting state stays in project docs.

## Workflow

### 1. Find the agent

Check the agents in your project, in this order: `agents/<group>/<name>.md` (the `name`
field is the identity; the folder is the group), then `.claude/agents/` and `.cursor/agents/`.
If an agent fits, the prompt points at it and does not restate its persona, interaction rules,
permissions, or report-back format. Use the in-workspace path:

> Read `{workspace}/agents/{group}/{name}.md` and act as that agent.

If none fits, research the domain first (step 2), then write one role sentence: the domain,
the artifact, the stance. No superlatives ("world-class", "senior expert"): a role sets tone
and focus, not accuracy. The research note, the goals, and the boundaries do the work.

> You are a tutor for the argument parser of our CSV-to-JSON command-line tool: you explain
> the code against the best-practices note and test my understanding; you do not change it.

**Promotion rules.**
- Third prompt for the same kind of agent, or persona text copied from an older prompt →
  propose writing an agent file (`agents/<group>/<name>.md`).
- A best-practices note for the same tool reused or refreshed in a second session →
  propose writing a skill (`skills/<name>/SKILL.md`), so any session can load it.

### 2. Research the domain (when no agent fits)

A specialized agent without an agent file is only as good as the research behind its
prompt. Do decent research, not exhaustive: enough to compare the work against current
practice.

1. **Reuse before searching.** Look for an existing note on the tool in the topic's
   `working/`, other topics in the design root, and the project's `skills/`. Reuse it if it
   is under 6 months old and covers the same scope; otherwise refresh it.
2. **Set the scope: the version in use, or the tool in general.**
   - If the project already runs the tool, read the version from the lockfile,
     `pyproject.toml`, `package.json`, or the SDK or server config, and research that major
     version. Practices differ between major versions, and a search without one returns a mix.
   - If the owner wants the tool's best practices in general (the project does not use it
     yet, or the question is about the tool, not the code), research the current stable
     release and say so in the note. Skip practices that apply only to old releases.
3. **Cover these lenses**, each with at least one source:
   - official docs for the version in scope: concepts and recommended patterns;
   - release notes and migration guides: what changed, what is deprecated;
   - pitfalls: maintainer answers, issues, post-mortems;
   - testing, debugging, and observability;
   - how practitioners structure real work: vendor examples, reference implementations;
   - for internal tools: internal search and your own repos before the web.
4. **Budget and stop rule.** Roughly 8–15 sources. Stop when two consecutive sources add no
   new practice, or at about 15 sources.
5. **Vet every source.** Official docs > maintainer or vendor engineering posts >
   established practitioners > forums. Date each one; flag anything over 12 months old;
   drop anything written for a different major version than the one in scope.
6. **Map it to the work, when there is work.** If the session will discuss the project's
   code or config, read it and note where it follows or departs from each practice; this
   list becomes the topic menu. For general best practices, skip this and build the menu
   from the practices themselves.
7. **Write the note** in the format in [references/best-practices-note.md](references/best-practices-note.md),
   to `docs/design/<topic>/working/best-practices-<tool>-<YYYY-MM-DD>.md` in the target
   project (skill `design-memory`; scaffold the topic first if it does not exist). If the
   project `AGENTS.md` names another docs folder, use it. The prompt points at the note; it
   never pastes it.
8. **Checkpoint with the owner.** Before writing the prompt, show a five-line summary: scope
   (version in use or general), top practices, the biggest gaps in the work if any, weak or
   disputed evidence. Ask what is missing.

Do the research in this session by default. If the domain is broad (several tools, or a
process plus a tool), launch one research sub-agent with a pinned model that writes the note
itself (brief it per skill `session-orchestration`); verify its sources before you rely on them.

### 3. Decide what the session is for

Settle these before filling the template; ask the owner only for what context cannot answer:

- **Outcomes**: 2–4 things the owner wants to understand, decide, or have challenged, and why.
- **Stance**: teach, challenge, partner, or review.
- **Register**: e.g. ASD-STE100 Simplified Technical English, or plain language for a
  non-technical reader. State it only if the owner asked or the agent file does not set it.
- **Execution mode**: solo by default (the session does the work itself; no sub-agents).
  Switch to orchestration only when the owner asks or the session needs research lanes;
  then pin the sub-agent model (model + slug).
- **Return path**: where the wrap-up notes go —
  `docs/design/<topic>/working/session-notes-<YYYY-MM-DD>.md`.

### 4. Fill the template

The template is a default, not a fixed form. Delete empty sections; do not pad. Target
30–60 lines; with an agent file, nearer 30.

```markdown
{Role: "Read {workspace}/agents/{group}/{name}.md and act as that agent in {mode}."
OR one sentence — domain, artifact, stance.} This is a conversation with me, not an
implementation session. Work {solo in this session | as orchestrator: sub-agents run on
{model + slug} and write their own files}.

## What I want from this session
{2–4 outcomes, each with its reason.}

## How we work together
{Only what the agent file does not already say: stance, turn size ("small steps, then
check with me"), register, a position with a reason on every question. With a
best-practices note: compare the work against its practice IDs, and cite current docs
for any claim the note does not cover.}

## Read first, in order — nothing else yet
1. {abs path} ({what it holds})
2. {abs path to the best-practices note, if any} (practices for {tool} {version or "general"}, gaps in the work if any)
Defer until a topic needs them: {files}.

## What you may touch
Read-only by default. Scratch work goes in {abs path}. Edit {named files} only after I
say "go" for that change. No commits, pushes, or posts to chat, issue-tracker, or wiki tools.

## Ground rules
{Data-access line, e.g. the one approved non-interactive route to a database.} Freshly
executed outputs beat every document; treat any number you read as as-of its run date. If
anything material conflicts, stop and ask me; never resolve it silently.

## Ask me first
1. {What I want to start with.}
2. {Any pending decision no file can answer.}

## Topics — a menu, not a sequence
{3–7 topics I am likely to raise, citing note practice IDs where they apply. Follow my lead.}

## Out of scope
{The tempting adjacent things, by name.}

## When I say "wrap up"
Write {abs path}/docs/design/{topic}/working/session-notes-{YYYY-MM-DD}.md: {the agent's
report-back format, or: decisions made, decisions I still owe, proposed changes, open
questions, what was not verified}. The next session reads that file, not this chat.
```

### 5. Deliver

Post the filled prompt in chat as one ` ```markdown ` fenced block, with at most a one-line
lead-in. Do not write it to a file unless the owner asks.

## Shared rules (owned by `session-prompting`)

- The prompt carries only what files cannot. If a ruling it relies on is not in a project
  doc yet, write it to its home first (skill `design-memory`), then point at it.
- Ordered read-first list with a one-line note per file; defer everything else.
- No live numbers, counts, or dated metrics inline.
- Markdown headers, no XML; each gate or permission stated once.
- All paths absolute; state the branch and whether the work is committed.

## Worked example — agent file fits (abridged)

Toy domain: a small CSV-to-JSON command-line tool. Owner: "I want a reviewer to challenge
the plan for the `--delimiter` option before I approve it." The fork has a reviewer agent
at `agents/review/plan-reviewer.md` (illustrative).

```markdown
Read {workspace}/agents/review/plan-reviewer.md and act as that agent in
plan review mode, on the plan for the `--delimiter` option of our CSV-to-JSON tool. This
is a conversation with me, not an implementation session. Work solo.

## What I want from this session
1. Find the holes in the plan before I approve it, so the implement phase does not stall.
2. Decide which edge cases (quoted fields, multi-character delimiters) the plan must cover.

## Read first, in order — nothing else yet
1. {abs path}/docs/design/delimiter-option/context.md (rulings, document map)
2. {abs path}/docs/design/delimiter-option/working/plan.md (the plan under review)
3. {abs path}/docs/design/delimiter-option/working/proposal.md (the chosen option under `## Decision`)
Defer until a question needs them: the parser source, the test suite.

## Ask me first
1. Which part of the plan I trust least.

## Out of scope
Editing the plan or the code; starting the implement phase.

## When I say "wrap up"
Write {abs path}/docs/design/delimiter-option/working/session-notes-{YYYY-MM-DD}.md in the
agent's report-back format.
```

No "How we work together" or "What you may touch" section: the agent file already sets the
stance, the read-only mode, and the report-back format.

## Worked example — no agent fits (abridged)

Owner: "I want a tutor to walk me through the tool's argument parser and how it compares
with good practice for the CLI library it uses." No agent fits, so step 2 runs first: the
version comes from the lockfile, the note goes to
`docs/design/parser-walkthrough/working/best-practices-{library}-{YYYY-MM-DD}.md`, and the owner
sees the five-line summary. Practice IDs below are illustrative.

```markdown
You are a tutor for the argument parser of our CSV-to-JSON command-line tool: you explain
the code against the best-practices note and test my understanding; you do not change it.
This is a conversation with me, not an implementation session. Work solo.

## What I want from this session
1. Understand how flags become options, so I can review the next change to the parser.
2. Know which departures from the note matter, and which are fine for a small tool.

## How we work together
Small steps, then check with me. Compare the code against the note's practice IDs; cite
current docs for any claim the note does not cover. A position with a reason on every question.

## Read first, in order — nothing else yet
1. {abs path}/docs/design/parser-walkthrough/working/best-practices-{library}-{YYYY-MM-DD}.md (practices for the version in use; gaps in our parser)
2. {abs path}/src/cli.py (the parser)
Defer until a topic needs them: the tests, the usage section of the README.

## What you may touch
Read-only. Scratch work goes in {abs path}/docs/design/parser-walkthrough/working/scratch/.
No commits or pushes.

## Topics — a menu, not a sequence
Flag naming and defaults (P2); error messages and exit codes (P4, X1); help text (P5);
testing the parser (P7).

## When I say "wrap up"
Write {abs path}/docs/design/parser-walkthrough/working/session-notes-{YYYY-MM-DD}.md: decisions
made, decisions I still owe, proposed changes, open questions, what was not verified.
```

## Gotchas

- **File placement follows `design-memory`.** Notes and session notes are drafts →
  `working/`. `evidence/` holds only material collected from an outside source. The
  read-first list never names `evidence/`, `archive/`, or `CHANGELOG.md`.
- **Do not restate an agent file.** Copying its persona or permissions into the prompt
  creates a second copy that drifts.
- **Do not assume orchestration.** Solo is the default; the owner often wants one lean session.
- **"Keep it simple" means cut sections, not compress sentences.** Drop topics and deferred
  files before you shorten the wording.
- **When the project runs the tool, check its version before searching.** Otherwise the note
  mixes practices from incompatible releases. When the ask is general, say "current stable
  release" in the note so a later reader knows what it covers.
- **Never paste the research into the prompt.** It goes stale and bloats the prompt; write
  the note and point at it.
- **The note is a starting point, not the last word.** The prompt still tells the agent to
  cite current docs for any specific claim the note does not cover.

## Pre-flight checklist

- [ ] Right skill: the session talks with the owner; it does not continue the work.
- [ ] Project agents checked (`agents/<group>/`, then `.claude/agents/` and `.cursor/agents/`); if an agent fits, the prompt points at it and restates nothing.
- [ ] No agent fits → best-practices note written (scope stated: version in use or general;
      all lenses covered; sources dated), summary shown to the owner, note in the
      read-first list.
- [ ] Role sentence (if any) names domain, artifact, and stance; no superlatives.
- [ ] Outcomes have reasons; topics are a menu.
- [ ] Read-only default, scratch path, and "go" rule present; side-effect ban present.
- [ ] Execution mode stated; model + slug pinned if orchestrating.
- [ ] Wrap-up notes path under the topic's `working/`.
- [ ] No live numbers; absolute paths; 30–60 lines.
- [ ] Delivered in chat as one fenced markdown block.

## What this skill does not do

- Hold the discussion itself (the matching agent does).
- Write task, implementation, or continuation prompts (`session-prompting`).
- Write sub-agent briefs (`session-orchestration`).
- Write agent files or skills; it only proposes them under the promotion rules.
- Exhaustive research. For a full survey of a field, run skill `reppit-research` instead.
