#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  printf 'ERROR: Run this installer with sudo.\n' >&2
  exit 1
fi
target_user="${SUDO_USER:-}"
if [[ -z "$target_user" ]]; then
  printf 'ERROR: SUDO_USER is not available.\n' >&2
  exit 1
fi
target_user_home="$(getent passwd "$target_user" | cut -d: -f6)"
venv="${DSE_SEARCH_VENV:-$target_user_home/.venvs/dse-search}"
if [[ ! -x "$venv/bin/python" ]]; then
  printf 'ERROR: Search environment not found: %s\n' "$venv" >&2
  exit 1
fi
export PYTHON_BIN="$venv/bin/python"
load_cluster
require_role search
serving_root="$DSE_SERVING_ROOT"
[[ "$serving_root" = /* ]] || serving_root="$REPO_ROOT/$serving_root"
search_host="$(settings_value search.host)"
search_port="$(settings_value search.port)"
search_workers="$(settings_value search.workers)"
unit=/etc/systemd/system/dse-search.service
cat >"$unit" <<EOF
[Unit]
Description=Distributed Search Engine API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$target_user
Group=$(id -gn "$target_user")
WorkingDirectory=$REPO_ROOT
EnvironmentFile=-$REPO_ROOT/config/.env
Environment=DSE_CONFIG_FILE=$REPO_ROOT/config/cluster.yaml
Environment=DSE_SETTINGS_FILE=$REPO_ROOT/config/settings.yaml
Environment=DSE_SERVING_ROOT=$serving_root
ExecStart=$venv/bin/python -m uvicorn search_service.main:app --host $search_host --port $search_port --workers $search_workers
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now dse-search.service
systemctl --no-pager --full status dse-search.service
