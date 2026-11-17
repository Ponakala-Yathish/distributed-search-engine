#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

search_python="${DSE_PYTHON:-python3}"
if ! command -v "$search_python" >/dev/null 2>&1; then
  printf 'ERROR: Python executable not found: %s\n' "$search_python" >&2
  exit 1
fi
venv="${DSE_SEARCH_VENV:-$HOME/.venvs/dse-search}"
if [[ ! -x "$venv/bin/python" ]]; then
  "$search_python" -m venv "$venv"
fi
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install -r "$REPO_ROOT/requirements/search.txt"
export PYTHON_BIN="$venv/bin/python"
load_cluster
require_role search
printf 'Search service environment installed at %s\n' "$venv"
