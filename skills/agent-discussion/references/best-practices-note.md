Copied from ai_agents_repo @ 1cdedc9, 2026-11-06

# Best-practices note format

Read this when step 2 of the skill applies: no agent fits, and you are writing the research
note the discussion prompt will point at. The note outlives the prompt, so a later session
can reuse it or refresh it.

## File

`docs/design/<topic>/working/best-practices-<tool>-<YYYY-MM-DD>.md` in the target project,
or the same path under the docs folder the project `AGENTS.md` names.

## Layout

```markdown
# {Tool or domain} — best practices for this project

Version: {tool} {version} (from {lockfile or config path}) — or "general: current stable
release ({version}) as of {YYYY-MM-DD}". Researched: {YYYY-MM-DD}.
Scope: {what the discussion session will cover; what this note does not cover}.

## Summary
{Five lines at most: the practices that matter most for the work, the biggest gaps, and
what the evidence is weak or disputed on.}

## Practices
| ID | Practice (one line) | Why it matters | Source | Source date |
|---|---|---|---|---|
| P1 | … | … | [S1] | YYYY-MM-DD |

## Anti-patterns and pitfalls
| ID | What goes wrong | How to recognise it | Source |
|---|---|---|---|
| X1 | … | … | [S3] |

## How the work compares (omit for general best practices)
| Practice | Where in the work | Follows / departs / unknown | Note |
|---|---|---|---|
| P1 | `{path}:{line}` | departs | … |

## Open questions and weak evidence
- {Points where sources disagree, evidence is anecdotal, or behavior is version-dependent.}

## Sources
| ID | Title | URL | Publisher | Date | Authority | Freshness |
|---|---|---|---|---|---|---|
| S1 | … | … | … | YYYY-MM-DD | Official docs | Current |
```

## Rules

- Stable IDs (P1, X1, S1) so the prompt's topic menu and the session's notes can cite them.
- Every practice has a source and a date. No source → it goes under open questions, not practices.
- Authority column: Official docs, Maintainer / vendor engineering, Practitioner, Forum.
- Freshness column: Current (under 6 months), Aging (6–12 months), Stale (over 12 months; keep
  only if nothing newer exists, and say so).
- "How the work compares" cites files and lines you actually read; mark "unknown" rather than guess.
- Keep it to what the session needs; this is a working note, not a survey.
