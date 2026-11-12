---
name: grill-me
description: >
  Interviews the user relentlessly about a plan or design until reaching shared
  understanding, resolving each branch of the decision tree. Also holds the shared
  interview primitive that other skills call for one-question-at-a-time rounds. Use when
  user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Copied from ai_agents_repo @ b9a2286, 2026-10-21

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Interview primitive (shared)

Other skills call this primitive whenever they need to resolve open questions with a person. It is used by `brainstorming` (its clarifying-question and proposal-refinement steps) and by the RePPIT open-question rounds. The calling skill supplies the topic and the list of open items; the primitive runs the rounds.

1. **One question at a time.** Never batch questions in one message.
2. **Recommend an answer with each question.** State what you would choose and why, so the person can reply "yes" or correct you.
3. **Look before you ask.** If the code, the docs, or an earlier artifact can answer the question, read them instead of asking.
4. **Walk the decision tree in dependency order.** Resolve a decision before the decisions that depend on it. If an answer opens a new branch, add it to the list and resolve it in turn.
5. **Stop when every branch is resolved.** Do not keep asking once nothing open remains.
6. **Record each decision in one line.** Format: `<question> → <decision> (<reason>)`. The calling skill decides where the lines go.

Example (illustrative), for a small CSV-to-JSON command-line tool:

> **Q:** Should the tool emit one JSON array or one JSON object per line? I recommend one object per line (JSON Lines), because it streams large files without holding them in memory.

Recorded: `Output format → JSON Lines (streams large files)`.
