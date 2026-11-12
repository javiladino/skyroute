# The stop hook: run the checks every time

Open this when you set up a project so the close-out checks run without anyone remembering
them. A skill is advice the agent may skip; a hook runs on every matching event.

`scripts/design-check-on-stop.sh` runs when the agent ends a turn. If the design root has
uncommitted changes, it runs `design_check.py`. On `FAIL` it sends the output back to the agent
with the instruction to fix it, rerun, and report the summary line. It stays silent when
nothing under the design root changed, when the check passes, and when the same failures were
already reported in this session, so a failure the agent cannot fix is reported once.

The examples below assume the skill sits at `.claude/skills/design-memory/`; change the path if
yours lives elsewhere. The script finds `design_check.py` beside itself. Settings: `DESIGN_ROOT` (default `docs/design`) and
`DESIGN_CHECK` (path to the checker). Needs `python3`; reads the session id with `jq` when
present.

## Claude Code

In `.claude/settings.json` (merge into an existing `hooks` object):

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/skills/design-memory/scripts/design-check-on-stop.sh" } ] }
    ]
  }
}
```

A reply of `{"decision":"block","reason":...}` keeps Claude working and gives it the reason.
Claude Code stops honouring blocks after eight consecutive continuations.

## Cursor

In `.cursor/hooks.json` at the project root (merge into an existing `stop` list):

```json
{
  "version": 1,
  "hooks": {
    "stop": [ { "command": ".claude/skills/design-memory/scripts/design-check-on-stop.sh", "loop_limit": 3 } ]
  }
}
```

The hook gets `{"status": ..., "loop_count": ...}`. A non-empty `followup_message` is submitted
as the next user message. `loop_limit` caps how many follow-ups the hook may trigger in one
conversation (default 5).

## Test it

Make the script executable (`chmod +x`), change a file under `docs/design/`, then:

```bash
echo '{"session_id":"t","stop_hook_active":false}' | .claude/skills/design-memory/scripts/design-check-on-stop.sh
echo '{"status":"completed","loop_count":0}' | .claude/skills/design-memory/scripts/design-check-on-stop.sh
```

The first prints block JSON when the check fails and nothing when it passes; the second prints
follow-up JSON or `{}`. Review a hook before you register it: it runs on every turn.
