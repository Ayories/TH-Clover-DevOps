#!/usr/bin/env bash
set -euo pipefail
URL="${1:-http://127.0.0.1:8000/health}"
EXPECTED="${2:-}"
for attempt in $(seq 1 24); do
  response=$(curl --fail --silent --show-error --max-time 3 "$URL" || true)
  if [[ "$response" == *'"status":"ok"'* ]] && { [[ -z "$EXPECTED" ]] || [[ "$response" == *"$EXPECTED"* ]]; }; then
    echo "Healthy: $response"; exit 0
  fi
  sleep 5
done
echo 'Health verification failed' >&2
exit 1
