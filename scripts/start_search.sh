#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_role search

exec "$PYTHON_BIN" -m search_service.main --serve "$@"
