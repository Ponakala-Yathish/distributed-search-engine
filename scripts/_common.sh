#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${DSE_PYTHON:-python3}"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DSE_CONFIG_FILE="${DSE_CONFIG_FILE:-$REPO_ROOT/config/cluster.yaml}"
export DSE_SETTINGS_FILE="${DSE_SETTINGS_FILE:-$REPO_ROOT/config/settings.yaml}"
if [[ -f "$REPO_ROOT/config/.env" ]]; then
  set -a
  source "$REPO_ROOT/config/.env"
  set +a
fi
[[ "$DSE_CONFIG_FILE" = /* ]] || DSE_CONFIG_FILE="$REPO_ROOT/$DSE_CONFIG_FILE"
[[ "$DSE_SETTINGS_FILE" = /* ]] || DSE_SETTINGS_FILE="$REPO_ROOT/$DSE_SETTINGS_FILE"
export DSE_CONFIG_FILE DSE_SETTINGS_FILE

require_python() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf 'ERROR: Python executable not found: %s\n' "$PYTHON_BIN" >&2
    exit 1
  fi
  if ! "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
    printf 'ERROR: PyYAML is missing. Run: python3 -m pip install -r requirements/base.txt\n' >&2
    exit 1
  fi
}

load_cluster() {
  require_python
  local exports
  exports="$($PYTHON_BIN -m config.settings --export-shell)"
  eval "$exports"
}

config_value() {
  "$PYTHON_BIN" -m config.settings --get "$1"
}

settings_value() {
  "$PYTHON_BIN" -m config.settings --settings "$DSE_SETTINGS_FILE" --settings-get "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'ERROR: Required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

local_addresses() {
  hostname -I 2>/dev/null || true
}

detect_role() {
  local addresses
  addresses="$(local_addresses)"
  local candidate
  for candidate in ingestion storage compute search; do
    local host
    host="$(config_value "cluster.nodes.$([ "$candidate" = ingestion ] && printf vm1 || { [ "$candidate" = storage ] && printf vm2 || { [ "$candidate" = compute ] && printf vm3 || printf vm4; }; }).host")"
    if printf '%s' "$addresses" | tr ' ' '\n' | grep -Fxq "$host"; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

resolve_role() {
  if [[ -n "${DSE_CURRENT_ROLE:-}" ]]; then
    printf '%s' "$DSE_CURRENT_ROLE"
    return 0
  fi
  detect_role
}

require_role() {
  local expected="$1"
  local actual
  actual="$(resolve_role || true)"
  if [[ "$actual" != "$expected" ]]; then
    printf 'ERROR: Run this command on the %s VM. Detected role: %s\n' "$expected" "${actual:-unknown}" >&2
    exit 1
  fi
}

ensure_iceberg_runtime() {
  local spark_home="${SPARK_HOME:-}"
  if [[ -z "$spark_home" ]]; then
    printf 'ERROR: SPARK_HOME is not set.\n' >&2
    exit 1
  fi
  local jar
  jar="$spark_home/jars/iceberg-spark-runtime-3.3_2.12-1.8.1.jar"
  if [[ ! -s "$jar" ]]; then
    printf 'ERROR: Iceberg runtime is missing. Run scripts/install_iceberg.sh on this VM.\n' >&2
    exit 1
  fi
}
