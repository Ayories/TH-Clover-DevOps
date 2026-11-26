#!/usr/bin/env bash
# Unit checks for health-check.sh, rollback.sh and their hand-over with deploy.sh (AI-assisted).
# Everything is FAKE (docker, curl, releases) in a temporary folder. Output is not project evidence
# of any deployment or timing. Needs bash, flock and python3. Run: bash scripts/ops/test_scripts.sh
# shellcheck disable=SC2016
set -uo pipefail

scripts=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export CLOVER_ROOT=$work/root HEALTH_ATTEMPTS=2 HEALTH_DELAY=0 FAKE_STATE=$work
mkdir -p "$CLOVER_ROOT/bin" "$CLOVER_ROOT/production" "$work/fake"
for name in deploy.sh rollback.sh health-check.sh; do
  tr -d '\r' <"$scripts/$name" >"$CLOVER_ROOT/bin/$name"
  chmod +x "$CLOVER_ROOT/bin/$name"
done
: >"$CLOVER_ROOT/docker-compose.yml"
: >"$CLOVER_ROOT/production/secrets.env"
: >"$work/bad-shas"

cat >"$work/fake/docker" <<'FAKE'
#!/usr/bin/env bash
echo "$*" >>"$FAKE_STATE/docker-calls"
case "$*" in *pg_dump*) echo '-- FAKE dump' ;; esac
exit 0
FAKE
cat >"$work/fake/curl" <<'FAKE'
#!/usr/bin/env bash
url=${!#}
if [[ "$url" == *:9999/* ]]; then echo "$FAKE_RESPONSE"; exit 0; fi
sha=$(sed -n 's/^RELEASE_SHA=//p' "$CLOVER_ROOT/production/release.env")
grep -qx "$sha" "$FAKE_STATE/bad-shas" && exit 22
printf '{"database":"ok","environment":"production","status":"ok","version":"%s"}\n' "$sha"
FAKE
chmod +x "$work/fake/"*
export PATH="$work/fake:$PATH"

failures=0
check() { # check <description> <expected exit code> <command...>
  local name=$1 want=$2 got=0
  shift 2
  timeout 60 "$@" >"$work/output" 2>&1 || got=$?
  if [[ $got -eq $want ]]; then
    echo "ok   - $name"
  else
    echo "FAIL - $name (exit $got, wanted $want)"
    sed 's/^/       /' "$work/output"
    failures=$((failures + 1))
  fi
}

hc=$CLOVER_ROOT/bin/health-check.sh
dp=$CLOVER_ROOT/bin/deploy.sh
rb=$CLOVER_ROOT/bin/rollback.sh
dir=$CLOVER_ROOT/production
sha_of() { printf '%040d' "$1"; }
img_of() { printf 'ghcr.io/ayories/th-clover-devops@sha256:%064d' "$1"; }
live() { sed -n 's/^RELEASE_SHA=//p' "$dir/release.env"; }
last() { tail -n "$1" "$dir/deployments.log" | head -n 1; }

export FAKE_RESPONSE='{"database":"ok","status":"ok","version":"abc"}'
check 'health-check: no arguments is a usage error' 2 "$hc"
check 'health-check: healthy' 0 "$hc" http://x:9999/health
check 'health-check: expected sha matches' 0 "$hc" http://x:9999/health abc
check 'health-check: only part of the sha does not match' 1 "$hc" http://x:9999/health ab
export FAKE_RESPONSE='{"database":"unavailable","status":"error","version":"abc"}'
check 'health-check: error status fails' 1 "$hc" http://x:9999/health abc

check 'rollback: unknown environment' 2 "$rb" test
check 'rollback: nothing recorded' 3 "$rb" production

check 'deploy: first release' 0 "$dp" production "$(img_of 1)" "$(sha_of 1)"
check 'deploy: second release' 0 "$dp" production "$(img_of 2)" "$(sha_of 2)"

sha_of 3 >>"$work/bad-shas"
echo >>"$work/bad-shas"
check 'deploy: bad release exits 10 (rolled back, no deadlock)' 10 "$dp" production "$(img_of 3)" "$(sha_of 3)"
check 'automatic rollback: previous release is live' 0 test "$(live)" = "$(sha_of 2)"
check 'automatic rollback: rollback line, trigger auto' 0 grep -q '"event":"rollback".*"result":"success","trigger":"auto"' <<<"$(last 2)"
check 'automatic rollback: deploy line says rolled_back' 0 grep -q '"event":"deploy".*"result":"rolled_back"' <<<"$(last 1)"
check 'rollback: refuses when already on previous release' 3 "$rb" production

check 'deploy: fourth release' 0 "$dp" production "$(img_of 4)" "$(sha_of 4)"
check 'rollback: lock held by another run' 4 flock "$dir/deploy.lock" "$rb" production
check 'rollback: manual' 0 "$rb" production
check 'manual rollback: previous release is live' 0 test "$(live)" = "$(sha_of 2)"
check 'manual rollback: logged with trigger manual' 0 grep -q '"event":"rollback".*"result":"success","trigger":"manual"' <<<"$(last 1)"

check 'deploy: fifth release' 0 "$dp" production "$(img_of 5)" "$(sha_of 5)"
sha_of 2 >>"$work/bad-shas"
echo >>"$work/bad-shas"
check 'rollback: unhealthy target fails' 1 "$rb" production
check 'rollback failure is logged' 0 grep -q '"event":"rollback".*"result":"failed"' <<<"$(last 1)"

check 'log: every line is valid JSON' 0 python3 -c 'import json,sys; [json.loads(l) for l in open(sys.argv[1])]' "$dir/deployments.log"
check 'rollback never calls deploy.sh' 1 grep -qE '^[^#]*deploy\.sh' "$rb"

echo "failures: $failures"
[[ $failures -eq 0 ]]
