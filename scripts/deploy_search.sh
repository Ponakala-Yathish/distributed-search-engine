#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_role search
require_command hadoop

version=0
while [[ $# -gt 0 ]]; do
  case "$1" in
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
if [[ ! "$version" =~ ^[0-9]+$ ]]; then
  printf 'ERROR: --version must be a non-negative integer.\n' >&2
  exit 1
fi

serving_root="$DSE_SERVING_ROOT"
[[ "$serving_root" = /* ]] || serving_root="$REPO_ROOT/$serving_root"
remote_root="$(config_value paths.hdfs.serving)"
remote_target="$remote_root/index-v$version"
if ! hadoop fs -test -e "$remote_target"; then
  printf 'ERROR: Export does not exist in HDFS: %s\n' "$remote_target" >&2
  exit 1
fi

staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
hadoop fs -get "$remote_target" "$staging/index-v$version"
PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$staging/index-v$version" <<'PY'
import sys
from search_service.index_loader import load_index
snapshot = load_index(sys.argv[1])
print(f"Validated index version {snapshot.version} with {snapshot.document_count} documents")
PY

mkdir -p "$serving_root"
final_target="$serving_root/index-v$version"
if [[ -e "$final_target" ]]; then
  PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$final_target" <<'PY'
import sys
from search_service.index_loader import load_index
load_index(sys.argv[1])
print("Existing local export is valid")
PY
else
  mv "$staging/index-v$version" "$final_target"
fi
ln -sfn "index-v$version" "$serving_root/.current.tmp"
mv -Tf "$serving_root/.current.tmp" "$serving_root/current"
printf 'Activated serving version %s at %s\n' "$version" "$serving_root"
printf 'Restart or start the FastAPI service to load the activated version.\n'
