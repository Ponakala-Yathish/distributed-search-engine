#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster

role="$(resolve_role || true)"
if [[ "$role" != "storage" && "$role" != "compute" && "$role" != "ingestion" ]]; then
  printf 'ERROR: Spark configuration must be generated on VM1, VM2, or VM3.\n' >&2
  exit 1
fi
if [[ -z "${SPARK_HOME:-}" ]]; then
  printf 'ERROR: SPARK_HOME is not set.\n' >&2
  exit 1
fi

conf_dir="$SPARK_HOME/conf"
mkdir -p "$conf_dir"
worker_memory="$(config_value services.spark.worker_memory)"
worker_cores="$(config_value services.spark.worker_cores)"
executor_memory="$(settings_value spark.executor_memory)"
executor_cores="$(settings_value spark.executor_cores)"
shuffle_partitions="$(settings_value spark.shuffle_partitions)"
serializer="$(settings_value spark.serializer)"

cat >"$conf_dir/spark-defaults.conf" <<EOF
spark.executor.memory $executor_memory
spark.executor.cores $executor_cores
spark.sql.shuffle.partitions $shuffle_partitions
spark.serializer $serializer
spark.network.timeout 120
spark.executor.heartbeatInterval 10
EOF

local_host="$DSE_VM2_HOST"
[[ "$role" == "compute" ]] && local_host="$DSE_VM3_HOST"
[[ "$role" == "ingestion" ]] && local_host="$DSE_VM1_HOST"
python_path="$(command -v "$PYTHON_BIN")"
cat >"$conf_dir/spark-env.sh" <<EOF
export SPARK_MASTER_HOST=$local_host
export SPARK_WORKER_HOST=$local_host
export SPARK_WORKER_MEMORY=$worker_memory
export SPARK_WORKER_CORES=$worker_cores
export PYSPARK_PYTHON=$python_path
export PYSPARK_DRIVER_PYTHON=$python_path
export JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}
EOF

cat >"$conf_dir/workers" <<EOF
$DSE_VM2_HOST
$DSE_VM3_HOST
EOF

printf 'Spark configuration written to %s\n' "$conf_dir"
ensure_iceberg_runtime
if [[ "$role" == "ingestion" ]]; then
  printf 'Spark client configuration is ready on VM1; no daemon was started.\n'
else
  printf 'Run scripts/start_cluster.sh on VM2 and VM3.\n'
fi
