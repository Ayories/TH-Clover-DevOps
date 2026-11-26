#!/usr/bin/env bash
# failure-drill.sh --yes   (TH-CLOVER, AI-assisted)
# Failure-detection drill, run on the host with docker access (sudo). It STOPS THE PRODUCTION APP
# container, times Prometheus and Alertmanager, then starts the same container again.
# Writes one JSON line to $OUT_DIR/failure-drills.log. Email arrival time is not measurable here:
# read it from the received message and record it by hand.
# Exit codes: 0 notification accepted by SNS within LIMIT seconds and app recovered; 1 otherwise; 2 refused.
set -euo pipefail

if [[ $# -ne 1 || "$1" != "--yes" ]]; then
  echo 'Usage: failure-drill.sh --yes   (this stops the production application until the drill ends)' >&2
  exit 2
fi

ROOT=${CLOVER_ROOT:-/opt/th-clover}
PROM_URL=${PROM_URL:-http://127.0.0.1:9090}
AM_URL=${AM_URL:-http://127.0.0.1:9093}
LIMIT=${DRILL_TIMEOUT:-300}
POLL=${DRILL_POLL:-2}
OUT_DIR=${OUT_DIR:-$ROOT/drills}
HEALTH_CHECK=${HEALTH_CHECK:-$ROOT/bin/health-check.sh}

iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }
now() { date +%s; }
log() { echo "$(date -u +%H:%M:%SZ) $*"; }
die() { echo "Refused: $*" >&2; exit 2; }

# Prints inactive|pending|firing for the production CloverAppDown alert, or unknown.
alert_state() {
  curl -fsS --max-time 5 "$PROM_URL/api/v1/alerts" 2>/dev/null | python3 -c '
import json, sys
try:
    alerts = json.load(sys.stdin)["data"]["alerts"]
except Exception:
    print("unknown"); sys.exit()
states = [a["state"] for a in alerts
          if a["labels"].get("alertname") == "CloverAppDown" and a["labels"].get("environment") == "production"]
print("firing" if "firing" in states else states[0] if states else "inactive")
' || echo unknown
}

# Prints the number of active production CloverAppDown alerts held by Alertmanager.
am_active() {
  curl -fsS --max-time 5 "$AM_URL/api/v2/alerts?active=true" 2>/dev/null | python3 -c '
import json, sys
try:
    alerts = json.load(sys.stdin)
except Exception:
    print(0); sys.exit()
print(sum(1 for a in alerts
          if a["labels"].get("alertname") == "CloverAppDown" and a["labels"].get("environment") == "production"))
' || echo 0
}

# Successful SNS publish requests so far = requests minus failed requests.
sns_counts() {
  curl -fsS --max-time 5 "$AM_URL/metrics" 2>/dev/null | awk '
    /^alertmanager_notification_requests_total[{].*integration="sns"/ { total += $NF; seen = 1 }
    /^alertmanager_notification_requests_failed_total[{].*integration="sns"/ { failed += $NF }
    END { if (seen) printf "%d %d\n", total - failed, failed; else exit 1 }'
}

# --- preflight: refuse to start unless the system is healthy and observable ---
command -v docker >/dev/null || die 'docker not found'
[[ -x "$HEALTH_CHECK" ]] || die "health check script not found: $HEALTH_CHECK"
port=$(sed -n 's/^APP_PORT=//p' "$ROOT/production/release.env" | tr -d "\"'\r")
[[ "$port" =~ ^[0-9]+$ ]] || die "APP_PORT missing in $ROOT/production/release.env"
sha=$(sed -n 's/^RELEASE_SHA=//p' "$ROOT/production/release.env" | tr -d "\"'\r")
health_url="http://127.0.0.1:${port}/health"

# Hold the same lock as deploy.sh and rollback.sh, so no release changes during the drill.
exec 9>"$ROOT/production/deploy.lock"
flock -n 9 || die 'a production deployment or rollback is running'

cid=$(docker ps -q --filter label=com.docker.compose.project=clover-production \
  --filter label=com.docker.compose.service=app)
[[ -n "$cid" && "$cid" != *$'\n'* ]] || die 'expected exactly one running production app container'
HEALTH_ATTEMPTS=1 "$HEALTH_CHECK" "$health_url" "$sha" >/dev/null || die 'production is not healthy before the drill'
[[ "$(alert_state)" == inactive ]] || die 'CloverAppDown is already pending or firing, or Prometheus is unreachable'
[[ "$(am_active)" == 0 ]] || die 'Alertmanager still holds a CloverAppDown alert; wait a few minutes'
counts=$(sns_counts) || die 'Alertmanager SNS metrics are not readable'
read -r base_ok base_failed <<<"$counts"
mkdir -p "$OUT_DIR"

restored=0
restore() {
  [[ "$restored" == 1 ]] && return 0
  log "Starting production app container $cid"
  if docker start "$cid" >/dev/null; then
    restored=1
  else
    echo "RESTORE FAILED. Start it by hand: docker start $cid" >&2
  fi
}
trap restore EXIT
trap 'exit 1' HUP INT TERM

# --- inject the failure ---
t0=$(now)
log "T0 stopping production app container $cid"
docker stop "$cid" >/dev/null

t_pending='' t_firing='' t_am='' t_sent=''
failed_requests=0
while (($(now) - t0 < LIMIT)); do
  state=$(alert_state)
  if [[ -z "$t_pending" && ("$state" == pending || "$state" == firing) ]]; then
    t_pending=$(now); log "alert pending (+$((t_pending - t0))s)"
  fi
  if [[ -z "$t_firing" && "$state" == firing ]]; then
    t_firing=$(now); log "alert firing in Prometheus (+$((t_firing - t0))s)"
  fi
  if [[ -z "$t_am" && "$(am_active)" != 0 ]]; then
    t_am=$(now); log "alert active in Alertmanager (+$((t_am - t0))s)"
  fi
  if counts=$(sns_counts); then
    read -r ok failed_now <<<"$counts"
    failed_requests=$((failed_now - base_failed))
    # Count a publish only once this drill's alert is firing.
    if [[ -n "$t_firing" ]] && ((ok > base_ok)); then
      t_sent=$(now); log "SNS accepted the notification (+$((t_sent - t0))s)"
      break
    fi
  fi
  sleep "$POLL"
done
[[ -n "$t_sent" ]] || log "No successful SNS publish within ${LIMIT}s (failed requests: ${failed_requests})"

# --- restore and verify ---
t_restore=$(now)
restore
t_healthy=''
if HEALTH_DELAY=2 HEALTH_ATTEMPTS=60 "$HEALTH_CHECK" "$health_url" "$sha"; then
  t_healthy=$(now); log "production healthy again (+$((t_healthy - t_restore))s after restore began)"
else
  log 'production did NOT become healthy: follow the incident runbook now'
fi

result=fail
if [[ -n "$t_sent" && -n "$t_healthy" ]] && ((t_sent - t0 <= LIMIT)); then result=pass; fi

stamp() { if [[ -n "$1" ]]; then printf '"%s"' "$(iso "$1")"; else printf 'null'; fi; }
secs() { if [[ -n "$1" ]]; then printf '%d' "$(($1 - $2))"; else printf 'null'; fi; }
line=$(printf '{"drill":"failure-detection","env":"production","sha":"%s","t0":"%s","pending":%s,"firing":%s,"alertmanager":%s,"sns_accepted":%s,"restore_started":"%s","healthy":%s,"detect_seconds":%s,"notify_seconds":%s,"restore_seconds":%s,"outage_seconds":%s,"failed_publish_requests":%d,"result":"%s"}' \
  "$sha" "$(iso "$t0")" "$(stamp "$t_pending")" "$(stamp "$t_firing")" "$(stamp "$t_am")" "$(stamp "$t_sent")" \
  "$(iso "$t_restore")" "$(stamp "$t_healthy")" "$(secs "$t_firing" "$t0")" "$(secs "$t_sent" "$t0")" \
  "$(secs "$t_healthy" "$t_restore")" "$(secs "$t_healthy" "$t0")" "$failed_requests" "$result")
echo "$line" | tee -a "$OUT_DIR/failure-drills.log"
echo 'Now record the email arrival time by hand (docs/operations/drills.md).'
[[ "$result" == pass ]]
