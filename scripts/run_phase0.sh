#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_role ingestion
require_command spark-submit
ensure_iceberg_runtime

source_path="${DSE_PHASE0_INPUT:-$REPO_ROOT/data/datasets/pages.jsonl}"
[[ "$source_path" = /* ]] || source_path="$REPO_ROOT/$source_path"
if [[ ! -f "$source_path" ]]; then
  printf 'ERROR: Phase 0 dataset not found: %s\n' "$source_path" >&2
  exit 1
fi
printf 'Running Phase 0 ingestion from %s\n' "$source_path"
PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" spark-submit \
  --master "$DSE_SPARK_MASTER" \
  "$REPO_ROOT/ingestion/pipeline.py" \
  --phase 0 \
  --source "$source_path" \
  --upload
printf 'Phase 0 ingestion completed. Run scripts/export_index.sh --phase 0 on VM3.\n'
