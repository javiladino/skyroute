---
name: session-orchestration
description: >
  Run an agent session in orchestrator mode: the parent agent keeps the main
  line of context and delegates ALL execution to sub-agents (the Task tool in
  Cursor, the Agent tool in Claude Code), using the models the user specifies.
  Sub-agents do the work and write their own files; the parent only briefs,
  monitors, verifies, and reports. Use when the user says "you are the
  orchestrator", "keep the main line of context", "launch sub-agents to do the
  work", or "you don't implement, the sub-agents do" — often combined with a
  per-sub-agent model instruction. Applies to any task type — research,
  implementation, analysis, doc refinement — not just RePPIT cycles. Not for
  one-off delegation requests ("launch a sub-agent for this task") without
  session-wide orchestration intent.
---

Adapted from ai_agents_repo @ 1cdedc9, 2026-11-06: no `reppit-orchestrator` agent or `meta-orchestration` skill (the course RePPIT stage skills take that row), skill paths in briefs are `skills/<name>/SKILL.md` inside the repo.

# Session Orchestration

A general pattern for human-in-the-loop sessions where the parent agent is a
coordinator, not an executor. The user steers; the orchestrator decomposes,
briefs sub-agents, monitors them, verifies output, and reports back. This is
methodology-agnostic: a RePPIT cycle, an ad hoc analysis, a plan
implementation, or a doc refinement can all run under this pattern.

## Trigger

Activate when the user's message contains any of:

- "You are the orchestrator" / "orchestrator pattern" / "orchestration pattern"
- "Keep (or maintain/contain) the main line of context"
- "Launch sub-agents to do the work" / "the sub-agents are the ones who execute"
- "You are not the one who implements"

A per-sub-agent model instruction ("use {model} sub-agents", "{model A} for
complex tasks, {model B} for simple ones") usually accompanies these phrases
and confirms the intent — but a model instruction alone on a single task
("launch a {model} sub-agent to review this") is a one-off delegation: honor
it without activating this skill's session-wide contract.

## The Contract (non-negotiable)

1. **The parent never produces work products.** Research documents, proposals,
   plans, implementations, and analysis documents are always produced by
   sub-agents — no code edits, no heavy analysis, no long-running commands in
   the parent session.
   *Why:* the parent's context is the session's memory. Absorbing research
   content or doing implementation burns the context that the user is paying
   the orchestrator to preserve.
   **Exception — session-context artifacts:** lightweight bookkeeping the
   orchestrator already holds in its head (a `context.md` scaffold, a
   changelog entry, folder setup) may be written by the parent directly or
   delegated, at the orchestrator's discretion. These capture orchestration
   state, so writing them doesn't contaminate context.
2. **Sub-agents write their own work products.** Give write-capable sub-agents
   the output path and let them produce the artifact. The parent never writes
   a sub-agent's document for it — not even to "clean it up".
   *Why:* if the sub-agent's full output flows through the parent so the
   parent can write it, the context is contaminated and the pattern collapses.
   For artifact-producing tasks, output returned as text instead of a file
   means the wrong sub-agent type was used (use a write-capable type, not a
   read-only one). Review and verification tasks are different: a read-only
   reviewer returning findings as text is correct — route those findings to a
   fix sub-agent, don't apply them yourself.
3. **The parent reads artifacts only for gate-checking.** Skim structure,
   verify required sections exist, check acceptance criteria — do not ingest
   entire work products into the parent context.
4. **Models are set by the user, per session.** There are no default models.
   If the user has not specified which model(s) sub-agents should use, ask
   before launching the first sub-agent. When the user gives a tiered
   instruction ("model X for deep reasoning, model Y for simple tasks"), apply
   the tiers consistently and state which tier each launch uses.
5. **The user owns the gates.** Stop at the checkpoints the user defined
   ("report back after each phase", "don't implement yet", "check with me
   before launching"). Never skip a gate because the next step seems obvious.

## Workflow

### 1. Session intake

Before launching anything:

- Restate the goal, the phases you plan to run, and where artifacts will live.
- Confirm the sub-agent model(s). If not given, ask.
- Identify the artifact home. Default: `docs/design/<topic>/working/` inside the
  target project, per skill `design-memory` (§ Layout). If the project's `AGENTS.md` names
  another folder or documentation convention, follow it; if the user names a
  folder, use that.
- If any sub-agent will call an externally authenticated system (a database,
  a cloud CLI, an API), verify that a **non-interactive** credential works
  before the first launch — run one trivial read with it. When helper scripts
  call the CLI without naming a profile, also check that this credential is
  the CLI's default. If none works, stop and ask the owner to set one up
  while present. Sub-agents never create credentials and never fall back to
  an interactive login.
- Ask clarifying questions now — the user expects to be grilled up front, not
  interrupted mid-flow.

### 2. Decompose and brief

Split the work into units a single sub-agent can own end-to-end — one
deliverable per sub-agent (one document, one phase, one fix). If a unit needs
two unrelated deliverables, split it. For each unit decide: parallel
(independent) or sequential (depends on a prior output).

**Sub-agents see none of the parent conversation.** Every prompt must be
self-contained:

- Full absolute paths for every file to read and write — name the exact 1–3
  files the sub-agent needs, **never a folder** (`design/x.md`, not `design/`)
- Exact task boundaries — what is in scope and what is explicitly not
- Relevant excerpts from plans, and any rulings quoted **inline** so the
  sub-agent doesn't re-derive them (quote them; don't say "as discussed"). A
  brief may quote a single relevant finding inline instead of pointing the
  sub-agent at a whole findings file.
- Which skill file(s) the sub-agent must read before starting, by path inside
  the workspace — `skills/<name>/SKILL.md` from the repo root — never a path
  outside the workspace (reads there can be denied)
- The output artifact path the sub-agent must write
- When the session runs under a command allowlist, the shell rule from
  Launch and monitor, quoted inline in Constraints
- **For any externally authenticated system, name the ONE approved access
  route and explicitly forbid the alternatives.** A permitted-but-not-exclusive
  route lets the sub-agent pick a client that ignores the parent's verified
  credential and opens an interactive prompt. Pattern: "access is
  `{cli} --profile {non-interactive-profile}` ONLY; never the interactive
  profile, never a client library that opens its own session; if the
  credential fails, stop and report — do not fall back to an interactive
  login."
- What to report back (a summary, not the full content)

Briefing template:

```
Context: {1-3 sentences: project, task, why this task exists}
Read first: {skill paths, plan paths}
Task: {exact scope, with boundaries}
Constraints: {conventions, things NOT to do, safety rules}
Output: write {artifact} to {absolute path}
Report back: {what the orchestrator needs to verify — sections written,
  checks passed, open questions}
```

**Artifact-heavy implementers (notebooks, long docs) need method rules in the
brief:** build incrementally — one cell/section per tool call, no monolithic
builder scripts, row-limited query output, and read each reference file once.
Oversized single-shot edits come back malformed, get retried, and the retries
exhaust the sub-agent's context (see Failure Modes).

### 3. Launch and monitor

- **Match the sub-agent type to the task's execution needs before launching.**
  A background sub-agent cannot answer permission prompts — nobody is there to
  click approve. Read-only agent types stall indefinitely on their first shell
  command, including "harmless" ones like `jq` or a read-only query. Any
  background task that must run shell commands, query a database, or call a
  CLI needs a **full-execution type with the read-only discipline written into
  the brief** ("read-only queries only; modify no files"). Reserve read-only
  types for tasks satisfiable with file-read tools alone.
- **Under a command allowlist, keep shell calls simple.** Allowlists match
  the start of a command, so a compound command is denied even when each
  part is allowed. Shell rule for the parent and every brief: one simple
  command per shell call; no `;`, `&&`, or pipe chains, no heredocs, no
  `cd … &&` or `git -C`; use the Read/Glob/Grep tools instead of `cat`,
  `find`, or `ls` chains. On a denial, switch to the simple form or a file
  tool — never retry the same command.
- Launch sub-agents in the background. Parallelize independent units in a
  single batch; sequence dependent ones.
- **Smoke-check each background launch without blocking.** At the next natural
  pause (or immediately if the user reports a stall), read the sub-agent's
  transcript tail: tool calls with **no tool results** after a few minutes
  means it is stalled — usually a permission prompt. One-shot check only;
  never sleep/poll in the parent to babysit a sub-agent — completion
  notifications arrive on their own.
- **Never block the session waiting on a terminal or a sub-agent** when there
  is other orchestration work or user conversation to attend to. Monitor
  background work; don't babysit it.
- **For long-running implementers, one mid-flight check is legitimate.** About
  ten minutes into a large artifact build, read the transcript once: is the
  output file growing, or are edits repeatedly failing? A single smoke-check
  that catches a context-exhaustion spiral early is distinct from babysitting —
  don't turn it into polling.
- If a sub-agent needs something only the parent can do, the parent handles
  that one input and hands control back — it does not take over the task.
  Interactive auth prompts are the canonical case: a sub-agent that triggers
  one will hang. The fix is never to complete the prompt for it — correct the
  brief to the approved non-interactive route and relaunch; if the credential
  itself has expired, stop and ask the owner to renew it.

### 4. Verify and gate-check

After each sub-agent completes:

- Verify the artifact exists at the expected path (`ls`, quick structure read).
- Check it against the acceptance criteria from the briefing.
- If output is wrong or incomplete: re-brief and relaunch the sub-agent with
  the specific defect described. Do not fix it yourself. If the same
  sub-agent fails the same task twice, stop and report to the user.
- If a sub-agent crashes, stalls, or times out: **read its transcript and
  identify the blocker before relaunching.** A stall is usually configuration
  (wrong agent type, missing permissions, expired external auth), and an
  identical retry reproduces it. Fix the cause, then retry once. On a second
  failure, stop and report. Stop superseded stuck agents (resume + interrupt
  with a stop order) so their eventual output doesn't confuse the session.
- If the user-specified model is unavailable in the session, report it and
  ask which model to use instead — never silently substitute.

### 5. Report and iterate

- After each phase, summarize to the user: what each sub-agent did, what was
  produced (paths), what's next, what's blocked. Keep it bulleted and short.
- Quality loop when the user requests it or when it was agreed at intake:
  launch an adversarial sub-agent (see `adversarial-review`) to
  challenge the output, then a fix sub-agent to address findings, then
  re-verify. At intake, propose including this loop before any implementation
  phase and for artifacts that feed decisions or external communication — but
  never insert it unrequested mid-session (see Failure Modes).
- Wait at user-defined gates. "Report back and stop" means stop.

### 6. Close

- Run the session close in skill `design-memory` (§ Session close): triage
  every document a sub-agent produced this session exactly once, unless the
  project's documentation conventions say otherwise. Append one changelog line
  for the session. These are session-context artifacts: the parent may write
  them or delegate them, depending on how much content must flow through its
  context.
- If handing off, deliver the continuation prompt in chat (see
  `session-prompting`, handoff mode, below) — do not write it to a file.
- Summarize the session: artifacts produced, decisions made, open items.

## Relationship to Other Patterns

| Artifact | Relationship |
|---|---|
| `reppit-research` … `reppit-test` | The RePPIT stage skills (Research → Propose → Plan → Implement → Test). Under this pattern each stage is one sub-agent unit: the stage skill governs what the sub-agent produces, this skill governs the delegation, and the user's gate sits between stages. |
| `adversarial-review` | The methodology for the review loop in step 5. |
| `session-prompting` | Handoff mode is the template for continuation prompts; task prompt mode writes a one-off prompt for another agent outside an orchestrated session. When the user asks for a continuation prompt, fill the handoff template and post it in chat in a single fenced markdown block, never as a file. The prompt carries the pattern forward — the orchestration contract (parent keeps context, sub-agents execute and write their own files), the sub-agent model(s), the documents to read first (full paths), and the gates. A prompt without the contract produces a session that implements everything in the parent context. |
| `agent-discussion` | The prompt that opens a discussion session with a specialized agent. A sub-agent brief is not that prompt, and that prompt is not a brief; when the user asks for one, use that skill. |

## Failure Modes (all observed in real sessions)

| Failure | Rule |
|---|---|
| Orchestrator starts doing a phase itself ("I'll just do the research quickly") | Under no circumstances does the parent conduct a phase. Launch a sub-agent, even for small units. |
| Orchestrator writes a work product from a sub-agent's returned text | Wrong sub-agent type for an artifact-producing task. Relaunch with a write-capable sub-agent that saves its own file. (Read-only reviewers returning findings as text are fine.) |
| Sub-agent prompt says "as we discussed" or omits paths | Sub-agents have zero conversation visibility. Re-brief with a self-contained prompt. |
| Parent blocks on a foreground terminal command waiting for a sub-agent's process | Run long processes in the background and monitor; keep the parent responsive. |
| Extra unrequested phases inserted (e.g., an adversarial pass the user didn't ask for on an already-approved artifact) | Follow the phase list agreed at intake. Ask before adding steps. |
| Model instruction ignored or forgotten mid-session | The model instruction from intake applies to every launch. Restate the model in each launch summary. |
| Read-only sub-agent type launched in the background for a task needing shell/DB/CLI execution | It stalls forever on its first permission prompt (even for `jq` or a read-only query). Use a full-execution type with read-only rules in the brief; smoke-check the transcript after launch. |
| Shell calls denied under a command allowlist (`;`/`&&` chains, heredocs, `git -C`, `find` pipelines) | Allowlists match the command's start, so compound commands are denied even when every part is allowed. One simple command per shell call, file tools for reading and searching, and the shell rule quoted in every brief. On a denial, switch to the simple form; do not retry. |
| Brief points a sub-agent at a skill through a path outside the workspace (for example where a symlink resolves) | Reads outside the workspace can be denied. Give the in-workspace path, `skills/<name>/SKILL.md` from the repo root. |
| Stalled sub-agent relaunched with the same configuration, no diagnosis | Read the transcript tail first (tool calls without results = stalled). Identify the blocker — agent type, permissions, expired auth — and fix it; an identical retry reproduces the stall. |
| Parent sleeps/polls to babysit a background sub-agent | One-shot smoke-check, then end the turn; completion notifications arrive unprompted. Repeated waiting blocks the user's conversation — the thing the pattern exists to protect. |
| A background sub-agent hangs on an interactive auth prompt | At intake, verify a non-interactive credential works. Every brief names the single approved access route and forbids the alternatives (other profiles, client libraries with their own login). Check the credential's expiry before each launch batch and ask the owner to renew it when it is close. If the credential fails, stop and ask the owner — never complete the prompt for the sub-agent or fall back to an interactive login. |
| Brief names the interactive profile, or leaves the profile out so the CLI default applies | Name the non-interactive profile explicitly in every brief. Before launch, search the brief for the interactive profile's name and for the interactive login method; fix any match. |
| Orchestrator posts progress through a messaging MCP and waits for a notification that never comes | A messaging MCP posts as you, and you get no notification for your own messages — mentioning yourself does not help. MCP-posted updates are a visible log, not an alert; a real ping needs a different author (a bot or webhook). Don't gate the session on a self-notification. |
| Implementer sub-agent composes a large artifact (notebook, long doc) in one monolithic builder script or oversized string-replace edits | Giant payloads come back malformed and get retried; every mega-edit and retry piles into the transcript until the sub-agent runs out of context mid-edit with zero output files. Briefs for artifact-producing sub-agents must mandate incremental builds (one cell/section per edit), small tool payloads, and row-capped query output (a limit or sample, not full tables). On a context-exhaustion crash, diagnose the transcript for this pattern before relaunching. |

## Quality Gates

Before ending any orchestrated session, verify:

- [ ] No work products (research, proposals, plans, implementations, analyses)
      were written by the parent agent; any parent-written files are
      session-context artifacts only
- [ ] Every artifact exists at its expected path and passed gate-checks
- [ ] Every sub-agent launch used the user-specified model (or tier)
- [ ] All user-defined checkpoints were honored
- [ ] The session changelog line (or the project's equivalent) is written
- [ ] Final summary lists artifacts, decisions, and open items

## Example

> **User:** "Add a `--delimiter` option to our small CSV-to-JSON command-line
> tool. You are the orchestrator — you keep the main line of context,
> sub-agents do the work and write their own documents. Use {frontier model}
> for research and proposal, {cheaper model} for simple tasks. Report back
> after each phase."
>
> **Orchestrator (right):** Confirms scope and the artifact folder, launches a
> {frontier model} research sub-agent in the background with a self-contained
> brief and the output path `docs/design/delimiter-option/working/research.md`,
> monitors it, verifies the file exists with the required sections,
> summarizes in bullets, and stops for the user's go-ahead before the
> proposal phase.
>
> **Orchestrator (wrong):** Reads the CLI's source itself "to get oriented",
> writes `research.md` from a read-only sub-agent's returned text, and
> proceeds to the proposal phase without stopping.
