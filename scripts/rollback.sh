#!/usr/bin/env bash
# rollback.sh <staging|production>   (TH-CLOVER, AI-assisted)
# Restarts the release recorded in previous.env, verifies it and logs how long that took.
# Run as root. deploy.sh also calls this after a failed health check, with CLOVER_LOCK_HELD=1
# because it already holds the environment lock. This script never calls deploy.sh.
# The database is not changed: see docs/operations/incident-runbook.md before rolling back
# across a schema change.
# Exit codes: 0 restored and healthy; 1 rollback failed; 2 bad arguments;
# 3 nothing usable to roll back to; 4 another run holds the lock.
set -euo pipefail
umask 077

ROOT=${CLOVER_ROOT:-/opt/th-clover}
IMAGE_REPO='ghcr.io/ayories/th-clover-devops'
export HOME=${HOME:-/root}

die() {
  echo "$2" >&2
  exit "$1"
}

[[ $# -eq 1 ]] || die 2 'Usage: rollback.sh <staging|production>'
env_name=$1
[[ "$env_name" == staging || "$env_name" == production ]] || die 2 'Environment must be staging or production'

env_dir=$ROOT/$env_name
release_env=$env_dir/release.env
previous_env=$env_dir/previous.env
health_check=$ROOT/bin/health-check.sh

for required in "$env_dir/secrets.env" "$ROOT/docker-compose.yml" "$health_check"; do
  [[ -f "$required" ]] || die 3 "Missing $required - run the Ansible playbook first"
done

trigger=auto
if [[ "${CLOVER_LOCK_HELD:-}" != 1 ]]; then
  trigger=manual
  exec 9>"$env_dir/deploy.lock"
  flock -n 9 || die 4 "Another deployment or rollback of $env_name is running"
fi

[[ -s "$previous_env" ]] || die 3 "No previous release recorded for $env_name"

# Read values without executing the file.
value() { sed -n "s/^$2=//p" "$1" | tail -n 1 | tr -d '\r'; }
image=$(value "$previous_env" APP_IMAGE)
sha=$(value "$previous_env" RELEASE_SHA)
port=$(value "$previous_env" APP_PORT)
[[ "$image" =~ ^${IMAGE_REPO//./\.}@sha256:[0-9a-f]{64}$ ]] || die 3 "Bad APP_IMAGE in $previous_env"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || die 3 "Bad RELEASE_SHA in $previous_env"
[[ "$port" =~ ^[0-9]+$ ]] || die 3 "Bad APP_PORT in $previous_env"
[[ "$(value "$previous_env" APP_ENV)" == "$env_name" ]] || die 3 "$previous_env is not for $env_name"
# After a rollback both files match, so a second manual rollback has no older release to use.
if [[ "$trigger" == manual ]] && cmp -s "$previous_env" "$release_env"; then
  die 3 "$env_name already runs the release in previous.env; deploy a chosen release instead"
fi

started=$(date -u +%FT%TZ)
start_seconds=$(date +%s)
logged=false

record() { # record <success|failed>
  logged=true
  printf '{"event":"rollback","env":"%s","sha":"%s","image":"%s","started":"%s","finished":"%s","seconds":%d,"result":"%s","trigger":"%s"}\n' \
    "$env_name" "$sha" "$image" "$started" "$(date -u +%FT%TZ)" "$(($(date +%s) - start_seconds))" "$1" "$trigger" |
    tee -a "$env_dir/deployments.log"
}

# shellcheck disable=SC2317,SC2329 # run by the EXIT trap
on_exit() {
  rm -f "$release_env.rollback"
  if [[ "$logged" == false ]]; then
    record failed
  fi
}
trap on_exit EXIT

compose() { # compose <release env file> <arguments...>
  local release_file=$1
  shift
  local files=(-f "$ROOT/docker-compose.yml")
  if [[ -f "$ROOT/docker-compose.aws.yml" ]]; then
    files+=(-f "$ROOT/docker-compose.aws.yml")
  fi
  docker compose -p "clover-$env_name" \
    --env-file "$env_dir/secrets.env" --env-file "$release_file" "${files[@]}" "$@"
}

echo "Rolling $env_name back to $sha ($trigger)"
docker network inspect clover-monitoring >/dev/null 2>&1 || docker network create clover-monitoring >/dev/null

# Fetch the image before changing anything; normally it is still on the host.
if ! docker image inspect "$image" >/dev/null 2>&1; then
  compose "$previous_env" pull --quiet app || die 1 'Previous image is not available - nothing was changed'
fi

if [[ -s "$release_env" ]] && ! cmp -s "$previous_env" "$release_env"; then
  cp "$release_env" "$env_dir/release.env.replaced"
fi
cp "$previous_env" "$release_env.rollback"
mv "$release_env.rollback" "$release_env"

if compose "$release_env" up -d --remove-orphans &&
  "$health_check" "http://127.0.0.1:${port}/health" "$sha"; then
  record success
  exit 0
fi

compose "$release_env" ps --all >&2 || true
record failed
die 1 "Rollback of $env_name did not produce a healthy service: follow the incident runbook"
