#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster

printf 'Distributed Search Engine Environment Audit\n'
printf '=========================================\n'
printf 'Role: %s\n' "$(resolve_role || printf unknown)"
printf 'Repository: %s\n' "$REPO_ROOT"
printf 'Config: %s\n\n' "$DSE_CONFIG_FILE"

printf '[Operating System]\n'
printf 'Host: %s\n' "$(hostname -f 2>/dev/null || hostname)"
printf 'Kernel: %s\n' "$(uname -srmo)"
printf 'Addresses: %s\n' "$(local_addresses)"
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  printf 'Distribution: %s %s\n' "${NAME:-unknown}" "${VERSION_ID:-unknown}"
fi
printf '\n[Python]\n'
"$PYTHON_BIN" --version || true
"$PYTHON_BIN" -m pip --version || true
"$PYTHON_BIN" - <<'PY' || true
try:
    import pyspark
    print(f"PySpark: {pyspark.__version__}")
except Exception as exc:
    print(f"PySpark: unavailable ({exc})")
try:
    import yaml
    print(f"PyYAML: {yaml.__version__}")
except Exception as exc:
    print(f"PyYAML: unavailable ({exc})")
PY

printf '\n[Java]\n'
if command -v java >/dev/null 2>&1; then
  java -version 2>&1 || true
  javac -version 2>&1 || true
  printf 'JAVA_HOME: %s\n' "${JAVA_HOME:-not set}"
else
  printf 'Java: unavailable\n'
fi

printf '\n[Hadoop]\n'
printf 'HADOOP_HOME: %s\n' "${HADOOP_HOME:-not set}"
if command -v hadoop >/dev/null 2>&1; then
  hadoop version 2>&1 || true
  for file in core-site.xml hdfs-site.xml workers; do
    path="${HADOOP_HOME:-/opt/hadoop}/etc/hadoop/$file"
    if [[ -f "$path" ]]; then
      printf '%s: present\n' "$path"
    else
      printf '%s: missing\n' "$path"
    fi
  done
else
  printf 'Hadoop: unavailable\n'
fi

printf '\n[Spark]\n'
printf 'SPARK_HOME: %s\n' "${SPARK_HOME:-not set}"
if command -v spark-submit >/dev/null 2>&1; then
  spark-submit --version 2>&1 || true
else
  printf 'spark-submit: unavailable\n'
fi
if [[ -n "${SPARK_HOME:-}" ]]; then
  for file in spark-defaults.conf spark-env.sh workers; do
    path="$SPARK_HOME/conf/$file"
    if [[ -f "$path" ]]; then
      printf '%s: present\n' "$path"
    else
      printf '%s: missing\n' "$path"
    fi
  done
fi

printf '\n[Apache Iceberg]\n'
if [[ -n "${SPARK_HOME:-}" ]]; then
  for jar in "$SPARK_HOME"/jars/iceberg-spark-runtime-3.3_2.12-1.8.1.jar; do
    if [[ -s "$jar" ]]; then
      printf 'Runtime: %s\n' "$jar"
      sha512sum "$jar" || true
    else
      printf 'Runtime: missing\n'
    fi
  done
else
  printf 'Runtime: SPARK_HOME is not set\n'
fi

printf '\n[ZeroTier]\n'
if command -v zerotier-cli >/dev/null 2>&1; then
  zerotier-cli info || true
  zerotier-cli listnetworks || true
else
  printf 'zerotier-cli: unavailable\n'
fi

printf '\n[Storage and Memory]\n'
df -h "$REPO_ROOT" || true
free -h || true

printf '\n[Configured Cluster]\n'
"$PYTHON_BIN" -m config.settings --json --get cluster.nodes || true
printf '\nAudit complete. Review unavailable or mismatched components before cluster startup.\n'
