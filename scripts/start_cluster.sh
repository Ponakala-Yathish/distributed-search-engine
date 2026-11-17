#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_command hdfs

role="$(resolve_role || true)"
case "$role" in
  storage)
    if [[ -z "${HADOOP_HOME:-}" ]]; then
      printf 'ERROR: HADOOP_HOME is not set.\n' >&2
      exit 1
    fi
    if [[ ! -d "$HADOOP_HOME/data/storage/namenode/current" ]]; then
      printf 'ERROR: NameNode is not formatted. On VM2 run: bash scripts/setup_hdfs.sh --format\n' >&2
      exit 1
    fi
    hdfs --daemon start namenode
    hdfs --daemon start datanode
    if [[ -z "${SPARK_HOME:-}" ]]; then
      printf 'ERROR: SPARK_HOME is not set.\n' >&2
      exit 1
    fi
    "$SPARK_HOME/sbin/start-worker.sh"
    ;;
  compute)
    if [[ -z "${HADOOP_HOME:-}" ]]; then
      printf 'ERROR: HADOOP_HOME is not set.\n' >&2
      exit 1
    fi
    hdfs --daemon start datanode
    if [[ -z "${SPARK_HOME:-}" ]]; then
      printf 'ERROR: SPARK_HOME is not set.\n' >&2
      exit 1
    fi
    "$SPARK_HOME/sbin/start-master.sh"
    "$SPARK_HOME/sbin/start-worker.sh"
    ;;
  ingestion|search)
    printf 'No cluster daemons are started on the %s VM.\n' "$role"
    ;;
  *)
    printf 'ERROR: Unable to detect the local VM role.\n' >&2
    exit 1
    ;;
esac
printf 'Cluster startup request completed for role: %s\n' "${role:-unknown}"
