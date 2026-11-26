#!/usr/bin/env bash
# deploy.sh <staging|production> <image-ref@sha256:...> <40-char-sha>   (TH-CLOVER, AI-assisted)
# Runs as root on the host, normally through the SSM document th-clover-deploy.
# Exit codes: 0 deployed; 2 bad arguments; 3 host not prepared; 4 another run holds the lock;
# 5 backup failed; 6 pull failed; 10 unhealthy, previous release restored;
# 11 unhealthy and not restored. Codes 2 to 6 leave the running release untouched.
set -euo pipefail
umask 077

ROOT=${CLOVER_ROOT:-/opt/th-clover}
IMAGE_REPO='ghcr.io/ayories/th-clover-devops'
KEEP_BACKUPS=5
# SSM Run Command does not set HOME, and docker looks there for registry credentials.
export HOME=${HOME:-/root}

die() {
  echo "$2" >&2
  exit "$1"
}

# --- validate inputs (also validated by the SSM document) ---
[[ $# -eq 3 ]] || die 2 'Usage: deploy.sh <staging|production> <image@sha256:digest> <40-char-sha>'
env_name=$1
image=$2
sha=$3
case "$env_name" in
  staging) port=8080 ;;
  production) port=80 ;;
  *) die 2 'Environment must be staging or production' ;;
esac
[[ "$image" =~ ^${IMAGE_REPO//./\\.}@sha256:[0-9a-f]{64}$ ]] ||
  die 2 "Image must be ${IMAGE_REPO}@sha256:<64 hex>; mutable tags are refused"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || die 2 'Release SHA must be 40 lowercase hex characters'

env_dir=$ROOT/$env_name
release_env=$env_dir/release.env
candidate_env=$env_dir/release.env.new
previous_env=$env_dir/previous.env
health_check=$ROOT/bin/health-check.sh
rollback=$ROOT/bin/rollback.sh

for required in "$env_dir/secrets.env" "$ROOT/docker-compose.yml" "$health_check" "$rollback"; do
  [[ -f "$required" ]] || die 3 "Missing $required - run the Ansible playbook first"
done

# --- one deployment per environment at a time ---
exec 9>"$env_dir/deploy.lock"
flock -n 9 || die 4 "Another deployment or rollback of $env_name is running"

started=$(date -u +%FT%TZ)
start_seconds=$(date +%s)
logged=false

record() { # record <success|failed|rolled_back>
  logged=true
  printf '{"event":"deploy","env":"%s","sha":"%s","image":"%s","started":"%s","finished":"%s","seconds":%d,"result":"%s"}\n' \
    "$env_name" "$sha" "$image" "$started" "$(date -u +%FT%TZ)" "$(($(date +%s) - start_seconds))" "$1" |
    tee -a "$env_dir/deployments.log"
}

# Called by the trap below.
# shellcheck disable=SC2329
on_exit() {
  rm -f "$candidate_env"
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

# The single-quoted variables are expanded inside the database container, not here.
# shellcheck disable=SC2016
backup_database() {
  local file
  file=$env_dir/backups/$(date -u +%Y%m%dT%H%M%SZ).sql.gz
  if ! { mkdir -p "$env_dir/backups" &&
    compose "$release_env" up -d --wait db &&
    compose "$release_env" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' |
    gzip >"$file.tmp" &&
    mv "$file.tmp" "$file"; }; then
    rm -f "$file.tmp"
    return 1
  fi
  echo "Database backup written: $file"
  # Backups contain personal data: keep only the newest few.
  find "$env_dir/backups" -name '*.sql.gz' -type f | sort -r | tail -n "+$((KEEP_BACKUPS + 1))" | xargs -r rm -f --
}

docker network inspect clover-monitoring >/dev/null 2>&1 || docker network create clover-monitoring >/dev/null

printf 'APP_IMAGE=%s\nRELEASE_SHA=%s\nAPP_ENV=%s\nAPP_PORT=%s\n' "$image" "$sha" "$env_name" "$port" >"$candidate_env"

# --- back up, then fetch the new image before touching the running release ---
if [[ -s "$release_env" ]]; then
  backup_database || die 5 'Database backup failed - nothing was changed'
else
  echo "First deployment of $env_name: no database to back up"
fi
compose "$candidate_env" pull --quiet app || die 6 'Image pull failed - nothing was changed'

# --- switch release, keeping the old one as the rollback target ---
if [[ -s "$release_env" ]] && ! cmp -s "$release_env" "$candidate_env"; then
  cp "$release_env" "$previous_env"
fi
had_release=false
[[ -s "$release_env" ]] && had_release=true
mv "$candidate_env" "$release_env"

if compose "$release_env" up -d --remove-orphans &&
  "$health_check" "http://127.0.0.1:${port}/health" "$sha"; then
  record success
  exit 0
fi

# --- the new release is not healthy ---
echo "Release $sha is not healthy on $env_name" >&2
compose "$release_env" ps --all >&2 || true

if [[ "$had_release" == false || ! -s "$previous_env" ]]; then
  compose "$release_env" stop app >&2 || true
  rm -f "$release_env"
  record failed
  die 11 'No previous release to restore: the application has been stopped'
fi

echo 'Rolling back to the previous release' >&2
if CLOVER_LOCK_HELD=1 "$rollback" "$env_name"; then
  record rolled_back
  die 10 'Deployment failed; the previous release has been restored'
fi
record failed
die 11 'Deployment failed and the rollback also failed: investigate now'
