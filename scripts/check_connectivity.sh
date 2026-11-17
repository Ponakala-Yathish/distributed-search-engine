#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster

printf 'Distributed Search Engine Connectivity Audit\n'
printf '==========================================\n'
"$PYTHON_BIN" -m config.settings

check_ping() {
  local host="$1"
  local label="$2"
  if ping -c 2 -W 2 "$host" >/dev/null 2>&1; then
    printf 'PASS ping %-8s %s\n' "$label" "$host"
  else
    printf 'FAIL ping %-8s %s\n' "$label" "$host" >&2
    return 1
  fi
}

check_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  if nc -z -w 3 "$host" "$port" >/dev/null 2>&1; then
    printf 'PASS port %-8s %s:%s\n' "$label" "$host" "$port"
    return 0
  fi
  if timeout 3 bash -c "</dev/tcp/$host/$port" >/dev/null 2>&1; then
    printf 'PASS port %-8s %s:%s\n' "$label" "$host" "$port"
    return 0
  fi
  printf 'FAIL port %-8s %s:%s\n' "$label" "$host" "$port" >&2
  return 1
}

status=0
hdfs_rpc_port="$(config_value services.hdfs.rpc_port)"
hdfs_http_port="$(config_value services.hdfs.http_port)"
hdfs_dn_port="$(config_value services.hdfs.datanode_transfer_port)"
spark_master_port="$(config_value services.spark.master_port)"
spark_web_port="$(config_value services.spark.web_ui_port)"
search_port="$(config_value services.search.port)"
for node in vm1 vm2 vm3 vm4; do
  host="$(config_value "cluster.nodes.$node.host")"
  check_ping "$host" "$node" || status=1
done

check_port "$DSE_VM2_HOST" "$hdfs_rpc_port" hdfs-nn || status=1
check_port "$DSE_VM2_HOST" "$hdfs_http_port" hdfs-web || status=1
check_port "$DSE_VM2_HOST" "$hdfs_dn_port" hdfs-dn || status=1
check_port "$DSE_VM3_HOST" "$hdfs_dn_port" hdfs-dn || status=1
check_port "$DSE_VM3_HOST" "$spark_master_port" spark-master || status=1
check_port "$DSE_VM3_HOST" "$spark_web_port" spark-web || status=1
check_port "$DSE_VM4_HOST" "$search_port" search-api || status=1

if command -v hdfs >/dev/null 2>&1; then
  printf '\n[HDFS Report]\n'
  hdfs dfsadmin -report "$DSE_HDFS_NAMENODE" || status=1
fi

if command -v curl >/dev/null 2>&1; then
  printf '\n[Spark Master UI]\n'
  master_json="$(curl --fail --silent --show-error --max-time 5 "http://$DSE_VM3_HOST:$spark_web_port/json/")" || status=1
  printf '%s\n' "$master_json"
  if [[ -n "${master_json:-}" ]]; then
    DSE_VM2_HOST="$DSE_VM2_HOST" DSE_VM3_HOST="$DSE_VM3_HOST" "$PYTHON_BIN" -c '
import json, os, sys
payload = json.load(sys.stdin)
workers = [worker for worker in payload.get("workers", []) if worker.get("state") == "ALIVE"]
hosts = {worker.get("host") for worker in workers}
expected = {os.environ["DSE_VM2_HOST"], os.environ["DSE_VM3_HOST"]}
missing = expected - hosts
if missing:
    print("Missing Spark workers: " + ", ".join(sorted(missing)), file=sys.stderr)
    raise SystemExit(1)
print("PASS Spark workers alive: 2")
' <<<"$master_json" || status=1
  fi
fi

if [[ "$status" -ne 0 ]]; then
  printf '\nConnectivity audit failed.\n' >&2
  exit "$status"
fi
printf '\nConnectivity audit passed.\n'
