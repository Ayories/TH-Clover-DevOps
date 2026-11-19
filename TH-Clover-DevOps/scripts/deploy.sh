#!/usr/bin/env bash
set -euo pipefail
: "${APP_IMAGE:?APP_IMAGE must be an immutable digest}"
: "${RELEASE_SHA:?RELEASE_SHA required}"
[[ "$APP_IMAGE" == *@sha256:* ]] || { echo 'Refusing mutable image tag' >&2; exit 1; }
cd /opt/th-clover
if [[ "${PRESERVE_PREVIOUS:-false}" != true ]]; then
  cp /opt/th-clover/release.env /opt/th-clover/previous.env 2>/dev/null || true
fi
printf 'APP_IMAGE=%s
RELEASE_SHA=%s
' "$APP_IMAGE" "$RELEASE_SHA" > release.env
# Secrets must be injected from the protected host environment file, never stored in Git.
docker compose --env-file /opt/th-clover/secrets.env --env-file release.env -f docker-compose.yml pull app
docker compose --env-file /opt/th-clover/secrets.env --env-file release.env -f docker-compose.yml up -d --remove-orphans
./health-check.sh http://127.0.0.1:8000/health "$RELEASE_SHA"
echo "deployed sha=$RELEASE_SHA image=$APP_IMAGE at=$(date -u +%FT%TZ)"
