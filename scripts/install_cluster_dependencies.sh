#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cluster_python="${DSE_PYTHON:-python3.10}"
if ! command -v "$cluster_python" >/dev/null 2>&1; then
  printf 'ERROR: Python 3.10 is required. Install python3.10 and set DSE_PYTHON if needed.\n' >&2
  exit 1
fi
venv="${DSE_CLUSTER_VENV:-$HOME/.venvs/dse-cluster}"
if [[ ! -x "$venv/bin/python" ]]; then
  "$cluster_python" -m venv "$venv"
fi
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install -r "$REPO_ROOT/requirements/cluster.txt"
export PYTHON_BIN="$venv/bin/python"
load_cluster
printf 'Cluster Python environment installed at %s\n' "$venv"
