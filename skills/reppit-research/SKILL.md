---
name: reppit-research
description: >
  Research what exists in the codebase for a task: explore it in this session,
  run one adversarial review round, fix what the review finds, and save a
  structured research document to docs/design/<topic>/working/research.md. Use when
  starting work that needs codebase exploration, when asked to research or
  document what exists today for a feature area, or as the first stage of the
  RePPIT method (Research, Propose, Plan, Implement, Test).
---

Adapted from ai_agents_repo @ b9a2286, 2026-10-21: this session explores itself (no `researcher` agent), one review round that the user may skip, course stage list. Stage files under `working/` per `design-memory` (ai_agents_repo @ 3e61f25, 2026-10-31).

# RePPIT Research

Run a full research cycle in this session: take in the task, explore the code under a behavior contract, get one review from the `adversarial-reviewer` agent, fix what it finds, cross-reference any design docs, and save a structured research document.

## Trigger

Activate when:
- The user gives a task statement and asks to research what exists
- The user says "research", "explore", "what exists for X", "document what's there"
- This is the first stage of a RePPIT workflow

Do NOT use for:
- Quick "where is X defined?" questions (just answer directly)
- Reading the internals of one function (just read it)

## Behavior Contract

This contract governs the entire research stage. Follow it yourself and pass it verbatim to the `adversarial-reviewer`:

> - Only document what exists today; do not suggest improvements, root-cause analysis, or future work
> - Provide concrete file paths and line references in findings
> - Read any user-mentioned files fully before decomposing work
> - Prioritize live code findings over historical docs

The contract keeps research focused. When triaging review feedback, test every proposed addition against it: does it document what exists, or does it suggest what should change?

## Workflow

### Step 1: Intake

1. **Read the task.** Extract the goal, any acceptance criteria, and any constraint the user stated.
2. **Read any referenced context** the user names: design docs, notes, the project's `AGENTS.md`.
3. **Identify scope**: which folders to explore, what concept to trace, what the task expects as output.

If a referenced doc points to another document, read that too. Context stacks.

### Step 2: Decompose into research areas

Break the question into 3 to 7 focused areas:

- Each area targets a specific module, function, command, test file, or concept
- Include a "cross-references and data flow" area that connects the findings
- If the concept exists in several independent places (the same assumption hard-coded in two code paths), each place is its own area

**Example decomposition (illustrative; task: "add a `--delimiter` option to a small CSV-to-JSON command-line tool"):**
1. Argument parsing in `cli.py` (existing flags, defaults, help text)
2. CSV reading in `convert.py` (the `csv.DictReader` call and its implicit comma default)
3. Header detection in `convert.py` (`detect_header()`, which splits the first line itself)
4. JSON output (serialization, `--pretty`; does any of it depend on the input format?)
5. Tests and fixtures (`tests/test_convert.py`, sample CSV files)
6. Docs (README usage section, `--help` output)
7. Cross-references and data flow (how a parsed flag value reaches the reader)

### Step 3: Explore and write the draft

Explore each area yourself, read-only: read files, search, run `git log` when history matters. Record findings with file:line evidence as you go.

> **Output path.** RePPIT stages write to `docs/design/<topic>/working/<stage>.md`, where
> `<topic>` is a short kebab-case slug for the task (e.g.
> `docs/design/delimiter-option/working/research.md`). If the project's `AGENTS.md` names
> another folder or language for design docs, follow it. Set `type: Research` in the
> file's frontmatter and carry **no `status`** field; the folder is the state. If the
> topic is new, run the Scaffold steps of skill `design-memory` first; it also owns the
> folder layout, what to read first, and the cycle close.

Merge the findings into the research document (structure below) and save it.

### Step 4: One adversarial review round

Launch the `adversarial-reviewer` agent once, with the research document, the task, and the behavior contract. Skip this step only if the user asks to; then say "review skipped at the user's request" in the document header.

The reviewer checks file existence and line accuracy, claims against the code, missing components, diagram accuracy, comparison-table completeness, and unstated assumptions. It returns: Verdict, Gaps, Unstated Assumptions, Ambiguities, Feasibility Concerns, Looks Good. Factual errors appear under Feasibility Concerns as "the document says X, the code says Y".

### Step 5: Triage and fix

| Finding type | Contract test | Action |
|-------------|--------------|--------|
| Factual error (wrong line number, wrong claim) | Always fix | Correct the document |
| Gap (missing component, missing file) | Does it document what exists? | Add if yes, skip if it is a suggestion |
| Unstated assumption | Is it a fact about current code? | Add as a factual observation |
| Ambiguity (vague wording) | Clarify with concrete code references | Fix the wording |
| Other feasibility concern | Does it reveal something about the codebase? | Add the fact, skip the recommendation |

If the review found a structural problem (a diagram that implies calls that do not exist), rebuild that section rather than patching it. There is no second review round; verify your fixes yourself against the code.

Illustrative: on the delimiter task, a first draft that documents only the `csv.DictReader` call misses the manual `split(",")` in `detect_header()`. That is a Gap that documents what exists, so it is added. A reviewer note "the tool should auto-detect delimiters" is a suggestion, so it is skipped.

### Step 6: Design-doc cross-reference

If design docs or planning notes exist for the work, read them and add facts about **existing code** that they mention and the research missed (e.g., the README states "input must be comma-separated"). Add only facts about what exists, never requirements.

### Step 7: Deliver

Save the final document at `docs/design/<topic>/working/research.md` and tell the user the next stage is `reppit-propose`.

## Output Structure

1. **Header**: task, date, scope statement, whether the review ran
2. **Summary** (3 to 6 sentences): how many components exist, what they share, what differs
3. **Detailed findings per component**, each with:
   - Source file path and line count
   - Logic description with code references (file:lines)
   - Values or outputs produced
   - Consumers (callers, tests, Docker services)
   - Edge cases
4. **Merge points and consumers**: code that combines or passes through the components above
5. **Flow diagrams**: Mermaid diagrams per path, every edge an actual call, import, or data hand-off
6. **Comparison table**: if a concept varies across components, one row per distinct value or assumption
7. **Inventory**: every file that touches the researched concept, labeled by component and role

## Quality Gates

- [ ] Every file path cited exists
- [ ] Every line reference points to what the document claims
- [ ] Every diagram arrow matches an actual call, import, or data hand-off
- [ ] Review round completed (or skipped at the user's request) and its must-fix findings addressed
- [ ] Design-doc cross-reference completed, if design docs exist
- [ ] No suggestions, no future work, no root-cause analysis
- [ ] Saved to `docs/design/<topic>/working/research.md`
