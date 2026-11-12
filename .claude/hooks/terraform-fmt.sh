#!/usr/bin/env bash
# PostToolUse (Edit|Write): formatea con `terraform fmt` el archivo .tf o .tfvars.example editado.
# Nunca bloquea: si falla, avisa a Claude por stderr con exit 2 (la herramienta ya se ejecutó).
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
case "$file" in
  *.tf|*.tfvars.example) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0
command -v terraform >/dev/null 2>&1 || exit 0
if ! out=$(terraform fmt "$file" 2>&1); then
  printf 'terraform fmt falló en %s:\n%s\n' "$file" "$out" >&2
  exit 2
fi
exit 0
