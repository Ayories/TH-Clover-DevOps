#!/usr/bin/env bash
# health-check.sh <url> [expected-sha]  (TH-CLOVER, AI-assisted)
# Polls /health until it reports status ok and, if given, the expected release SHA.
# Exit codes: 0 healthy, 1 not healthy in time, 2 usage error.
# HEALTH_ATTEMPTS (default 24) and HEALTH_DELAY seconds (default 5) tune the wait.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || -z "${1:-}" ]]; then
  echo 'Usage: health-check.sh <url> [expected-sha]' >&2
  exit 2
fi

url=$1
expected=${2:-}
attempts=${HEALTH_ATTEMPTS:-24}
delay=${HEALTH_DELAY:-5}

for ((attempt = 1; attempt <= attempts; attempt++)); do
  response=$(curl --fail --silent --show-error --max-time 3 "$url" 2>/dev/null || true)
  if [[ "$response" == *'"status":"ok"'* ]] &&
    { [[ -z "$expected" ]] || [[ "$response" == *"\"version\":\"${expected}\""* ]]; }; then
    echo "Healthy (attempt ${attempt}): ${response}"
    exit 0
  fi
  if ((attempt < attempts)); then
    sleep "$delay"
  fi
done

echo "Health verification failed after ${attempts} attempts: ${url}${expected:+ (expected ${expected})}" >&2
exit 1
