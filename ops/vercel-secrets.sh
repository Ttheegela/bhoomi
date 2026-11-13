#!/usr/bin/env bash
# Puts secrets straight into the linked Vercel project (never on disk). Input is hidden.
# Usage, from the repo root:  bash ops/vercel-secrets.sh production   (or: preview)
# production gets the PROD keys; preview gets the PREVIEW OpenRouter key + Langfuse DEV keys.
set -euo pipefail
env="${1:?usage: bash ops/vercel-secrets.sh production|preview}"

add() { # name prompt
  local v
  read -rsp "$2 (Enter to skip): " v
  echo
  [ -z "$v" ] && return
  printf '%s' "$v" | vercel env add "$1" "$env" --force --sensitive --yes >/dev/null
  echo "  set $1 ($env)"
}

add OPENROUTER_API_KEY  "OpenRouter key for $env (capped)"
add LANGFUSE_PUBLIC_KEY "Langfuse public key for $env (pk-lf-...)"
add LANGFUSE_SECRET_KEY "Langfuse secret key for $env (sk-lf-...)"

vercel env ls "$env"
