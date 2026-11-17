#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster

role="$(resolve_role || true)"
case "$role" in
  storage)
    if [[ -n "${SPARK_HOME:-}" ]]; then
      "$SPARK_HOME/sbin/stop-worker.sh" || true
    fi
    if command -v hdfs >/dev/null 2>&1; then
      hdfs --daemon stop datanode || true
      hdfs --daemon stop namenode || true
    fi
    ;;
  compute)
    if command -v hdfs >/dev/null 2>&1; then
      hdfs --daemon stop datanode || true
    fi
    if [[ -n "${SPARK_HOME:-}" ]]; then
      "$SPARK_HOME/sbin/stop-worker.sh" || true
      "$SPARK_HOME/sbin/stop-master.sh" || true
    fi
    ;;
  ingestion|search)
    printf 'No cluster daemons run on the %s VM.\n' "$role"
    ;;
  *)
    printf 'ERROR: Unable to detect the local VM role.\n' >&2
    exit 1
    ;;
esac
