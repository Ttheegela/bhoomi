#!/usr/bin/env bash
# Stores DEV secrets outside the repo in ~/.config/bhoomi/dev.env (chmod 600).
# Input is hidden and never echoed. Re-run any time: Enter skips a key, a new value replaces the old one.
# Production keys never go here; they go straight into Vercel with ops/vercel-secrets.sh.
set -euo pipefail

f="$HOME/.config/bhoomi/dev.env"
mkdir -p "$(dirname "$f")"
chmod 700 "$(dirname "$f")"
touch "$f"
chmod 600 "$f"

save() { # name value
  grep -v "^$1=" "$f" > "$f.tmp" || true
  mv "$f.tmp" "$f"
  chmod 600 "$f"
  printf "%s='%s'\n" "$1" "$2" >> "$f"
}

secret() { # name prompt
  local v
  read -rsp "$2 (Enter to skip): " v
  echo
  if [ -n "$v" ]; then save "$1" "$v"; fi
}

plain() { # name prompt default (not secret, shown while typing)
  local v
  read -rp "$2 [$3]: " v
  save "$1" "${v:-$3}"
}

secret OPENROUTER_API_KEY  "OpenRouter DEV key (capped)"
secret EARTHDATA_TOKEN     "Earthdata Login user token"
secret NOAA_CDO_TOKEN      "NOAA Climate Data Online token"
secret LANGFUSE_PUBLIC_KEY "Langfuse DEV public key (pk-lf-...)"
secret LANGFUSE_SECRET_KEY "Langfuse DEV secret key (sk-lf-...)"
plain  LANGFUSE_HOST       "Langfuse host" "https://us.cloud.langfuse.com"
secret UPTIMEROBOT_API_KEY "UptimeRobot main API key"

echo "Saved in $f: $(cut -d= -f1 "$f" | tr '\n' ' ')"
