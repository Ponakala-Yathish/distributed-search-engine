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
if ! command -v npm >/dev/null 2>&1; then
  printf 'ERROR: npm is not installed.\n' >&2
  exit 1
fi
frontend_root="$REPO_ROOT/frontend"
if [[ ! -d "$frontend_root/node_modules" || ! -d "$frontend_root/.next" ]]; then
  printf 'ERROR: Install dependencies and build the frontend before installing its service.\n' >&2
  exit 1
fi
npm_path="$(readlink -f "$(command -v npm)")"
unit=/etc/systemd/system/dse-frontend.service
cat >"$unit" <<EOF
[Unit]
Description=Distributed Search Engine Frontend
After=network-online.target dse-search.service
Wants=network-online.target

[Service]
Type=simple
User=$target_user
Group=$(id -gn "$target_user")
WorkingDirectory=$frontend_root
EnvironmentFile=-$frontend_root/.env.local
ExecStart=$npm_path run start -- --hostname 0.0.0.0 --port 3000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now dse-frontend.service
systemctl --no-pager --full status dse-frontend.service
