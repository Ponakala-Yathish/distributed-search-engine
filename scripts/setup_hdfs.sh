#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_command hdfs

role="$(resolve_role || true)"
if [[ "$role" != "storage" && "$role" != "compute" && "$role" != "ingestion" && "$role" != "search" ]]; then
  printf 'ERROR: Unable to detect the local VM role.\n' >&2
  exit 1
fi
if [[ -z "${HADOOP_HOME:-}" ]]; then
  printf 'ERROR: HADOOP_HOME is not set.\n' >&2
  exit 1
fi

conf_dir="$HADOOP_HOME/etc/hadoop"
data_root="$HADOOP_HOME/data/$role"
mkdir -p "$conf_dir" "$data_root/namenode" "$data_root/datanode"

cat >"$conf_dir/core-site.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property><name>fs.defaultFS</name><value>$DSE_HDFS_NAMENODE</value></property>
  <property><name>hadoop.tmp.dir</name><value>$HADOOP_HOME/tmp</value></property>
</configuration>
EOF

cat >"$conf_dir/hdfs-site.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <property><name>dfs.replication</name><value>2</value></property>
  <property><name>dfs.namenode.name.dir</name><value>file://$data_root/namenode</value></property>
  <property><name>dfs.datanode.data.dir</name><value>file://$data_root/datanode</value></property>
  <property><name>dfs.permissions.enabled</name><value>false</value></property>
</configuration>
EOF

cat >"$conf_dir/workers" <<EOF
$DSE_VM2_HOST
$DSE_VM3_HOST
EOF

if [[ "$role" == "storage" && "${1:-}" == "--format" ]]; then
  printf 'Formatting the HDFS NameNode on VM2. Existing NameNode data will be replaced.\n'
  hdfs namenode -format -force -nonInteractive
fi
printf 'HDFS configuration written to %s\n' "$conf_dir"
printf 'Run scripts/start_cluster.sh after the NameNode has been formatted on VM2.\n'
