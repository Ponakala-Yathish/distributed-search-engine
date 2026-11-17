#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_role compute
require_command spark-submit
require_command hadoop
ensure_iceberg_runtime

phase=0
version=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase)
      [[ $# -ge 2 ]] || { printf 'ERROR: --phase requires a value.\n' >&2; exit 1; }
      phase="$2"
      version="$2"
      shift 2
      ;;
    --version)
      [[ $# -ge 2 ]] || { printf 'ERROR: --version requires a value.\n' >&2; exit 1; }
      version="$2"
      shift 2
      ;;
    *)
      printf 'ERROR: Unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done
if [[ "$phase" != "0" && "$phase" != "1" ]]; then
  printf 'ERROR: --phase must be 0 or 1.\n' >&2
  exit 1
fi
if [[ ! "$version" =~ ^[0-9]+$ ]]; then
  printf 'ERROR: --version must be a non-negative integer.\n' >&2
  exit 1
fi

work_root="$(mktemp -d)"
local_root="$work_root/exports"
mkdir -p "$local_root"
serving_root="$(config_value paths.hdfs.serving)"
remote_target="$serving_root/index-v$version"
stage_root="$serving_root/.staging/index-v$version-$(date +%s%N)"
cleanup() {
  rm -rf "$work_root"
  hadoop fs -rm -rf "$stage_root" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if hadoop fs -test -e "$remote_target"; then
  printf 'ERROR: Immutable export already exists: %s\n' "$remote_target" >&2
  exit 1
fi
hadoop fs -mkdir -p "$stage_root"
PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" spark-submit \
  --master "$DSE_SPARK_MASTER" \
  "$REPO_ROOT/indexing/export.py" \
  --output-root "$local_root" \
  --data-root "$stage_root" \
  --version "$version" \
  --phase "$phase"
hadoop fs -put "$local_root/index-v$version/metadata.json" "$stage_root/metadata.json"
hadoop fs -mv "$stage_root" "$remote_target"
printf 'Published export: %s\n' "$remote_target"
printf 'Run scripts/deploy_search.sh --version %s on VM4.\n' "$version"
