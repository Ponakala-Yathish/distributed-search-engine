#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_role ingestion
require_command spark-submit
ensure_iceberg_runtime

source_path="${DSE_PHASE1_INPUT:-}"
if [[ -z "$source_path" ]]; then
  if [[ -f "$REPO_ROOT/data/datasets/changes.jsonl" ]]; then
    source_path="$REPO_ROOT/data/datasets/changes.jsonl"
  elif [[ -f "$REPO_ROOT/data/datasets/changes.json" ]]; then
    source_path="$REPO_ROOT/data/datasets/changes.json"
  fi
fi
if [[ -n "$source_path" && "$source_path" != /* ]]; then
  source_path="$REPO_ROOT/$source_path"
fi
if [[ -z "$source_path" || ! -f "$source_path" ]]; then
  printf 'ERROR: Phase 1 dataset not found. Set DSE_PHASE1_INPUT to changes.jsonl or changes.json.\n' >&2
  exit 1
fi
printf 'Running Phase 1 ingestion from %s\n' "$source_path"
PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" spark-submit \
  --master "$DSE_SPARK_MASTER" \
  "$REPO_ROOT/ingestion/merge_changes.py" \
  --source "$source_path" \
  --upload
printf 'Phase 1 ingestion completed. Run scripts/export_index.sh --phase 1 on VM3.\n'
