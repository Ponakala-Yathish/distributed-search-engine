#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_role search

if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet dse-search.service; then
  systemctl restart dse-search.service
  systemctl --no-pager --full status dse-search.service
  exit 0
fi
printf 'The dse-search.service systemd unit is not active.\n'
printf 'Start it with: sudo systemctl enable --now dse-search.service\n'
exit 1
