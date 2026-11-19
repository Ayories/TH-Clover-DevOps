#!/usr/bin/env bash
set -euo pipefail
cd /opt/th-clover
test -s previous.env || { echo 'No previous verified release' >&2; exit 1; }
# Database schema compatibility must be checked before rollback.
set -a; source previous.env; set +a
PRESERVE_PREVIOUS=true ./deploy.sh
