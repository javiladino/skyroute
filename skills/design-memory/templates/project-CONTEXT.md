# {Project name} — Agent Context

> **Purpose:** Orient any agent working on this project. Read this first, then stop as soon as the task is clear.
> **Last updated:** {YYYY-MM-DD}

## Skills

Load by task, not all at once.

| Skill | When to load |
|-------|--------------|
| {skill name} | {the task that needs it} |

## Repositories

_Omit when the project is one repo._

| Repo | Purpose | Key paths |
|------|---------|-----------|
| {repo} | {what it holds for this project} | `{path}` |

## Active Context

**Load order:** this file → `{topic}/context.md` of the active topic → the files its document map marks `always` → only the files the task names. Never load `CHANGELOG.md`, `evidence/`, `archive/`, or a whole folder unless the task names the file.
**Active topics:** `{topic}` ({one-line status}).
**Known findings:** `findings.md` — {N} entries, last {YYYY-MM-DD}. Open it only when the task touches a subject it covers. {Omit this line until `findings.md` exists.}

**Current state ({YYYY-MM-DD}):** {One block: branch, headline status, what was done last, open blockers. Replace this block when the state changes and move the old one to the CHANGELOG. There is only ever one.}

**Next up:** {short list, optional}
**Known issues:** {short list, optional}

## Conventions

{The single home for project-wide rulings. One entry per ruling; state the verdict once. Omit the section until a ruling exists.}

- **{Convention name} (in force {YYYY-MM-DD}; owner {name}; source {topic}):** {verdict in 1–3 lines}. {Optional: "Detail: `{topic}/context.md` § Rulings."}
- **{topic}-scoped rulings** live in `{topic}/context.md` § Rulings. {Navigation pointer only, no verdict.}
