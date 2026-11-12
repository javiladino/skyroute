#!/usr/bin/env bash
# Run the design-memory close-out checks when the agent tries to finish a turn, and send
# any FAIL back to the agent so it fixes them before it stops.
#
# Runs only when the design root has uncommitted changes, so sessions that did not touch
# design docs are never interrupted. Reports the same failures at most once per session:
# if the agent could not fix them, it has already been told, and the turn may end.
#
# Works as:
#   - Claude Code Stop hook: block = {"decision":"block","reason":...} on stdout.
#   - Cursor stop hook: reply {"followup_message": ...} on stdout, or {} to let it stop.
#
# Settings (environment variables):
#   DESIGN_ROOT   design root relative to the project (default docs/design)
#   DESIGN_CHECK  path to design_check.py (default: next to this script)
# Needs python3. Uses jq when present to read the session id. Compatible with bash 3.2.

input=$(cat)

case "$input" in
  *'"loop_count"'*) tool="cursor" ;;
  *) tool="claude" ;;
esac

project="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$(pwd)}}"
root="${DESIGN_ROOT:-docs/design}"
checker="${DESIGN_CHECK:-$(cd "$(dirname "$0")" && pwd)/design_check.py}"

allow() {
  [ "$tool" = "cursor" ] && printf '{}\n'
  exit 0
}

json_string() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

cd "$project" 2>/dev/null || allow
[ -f "$root/CONTEXT.md" ] || allow
[ -f "$checker" ] || allow
command -v python3 >/dev/null 2>&1 || allow

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  [ -n "$(git status --porcelain -- "$root" 2>/dev/null)" ] || allow
fi

output=$(python3 "$checker" "$root" 2>&1)
status=$?

session=""
if command -v jq >/dev/null 2>&1; then
  session=$(printf '%s' "$input" | jq -r '.session_id // .conversation_id // empty' 2>/dev/null)
fi
state=""
if [ -n "$session" ]; then
  key=$(printf '%s|%s' "$project" "$session" | cksum | cut -d' ' -f1)
  state="${TMPDIR:-/tmp}/design-check-$key"
fi

if [ "$status" -eq 0 ]; then
  [ -n "$state" ] && rm -f "$state"
  allow
fi

fingerprint=$(printf '%s' "$output" | grep '^FAIL' | cksum | cut -d' ' -f1)
if [ -n "$state" ] && [ "$(cat "$state" 2>/dev/null)" = "$fingerprint" ]; then
  allow
fi
[ -n "$state" ] && printf '%s' "$fingerprint" > "$state"

message="Design docs changed and the design-memory close-out check failed (exit $status). Fix every FAIL below by following skill design-memory (Session close), rerun: python3 $checker $root, and tell the user the final summary line and anything you could not fix.

$output"

if [ "$tool" = "cursor" ]; then
  printf '{"followup_message":%s}\n' "$(printf '%s' "$message" | json_string)"
else
  printf '{"decision":"block","reason":%s}\n' "$(printf '%s' "$message" | json_string)"
fi
exit 0
