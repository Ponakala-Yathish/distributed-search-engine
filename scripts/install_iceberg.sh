#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_cluster
require_command curl
require_command sha512sum

if [[ -z "${SPARK_HOME:-}" ]]; then
  printf 'ERROR: SPARK_HOME is not set.\n' >&2
  exit 1
fi

version="$(config_value compatibility.iceberg_version)"
suffix="$(config_value compatibility.iceberg_spark_suffix)"
url="https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-${suffix}/${version}/iceberg-spark-runtime-${suffix}-${version}.jar"
checksum="3ef9ed6b1297a6ad0467483958998e62a9f1207dd93edea577b0b2f53f12b64de84743464460a21751e871c1261d671e452a88b6481284eacefc4defc7cda474"
destination="$SPARK_HOME/jars/iceberg-spark-runtime-${suffix}-${version}.jar"

if [[ -s "$destination" ]]; then
  printf 'Iceberg runtime already exists: %s\n' "$destination"
  exit 0
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl --fail --location --retry 3 --output "$tmp" "$url"
actual="$(sha512sum "$tmp" | cut -d' ' -f1)"
if [[ "$actual" != "$checksum" ]]; then
  printf 'ERROR: Iceberg checksum mismatch.\nExpected: %s\nActual: %s\n' "$checksum" "$actual" >&2
  exit 1
fi
install -m 0644 "$tmp" "$destination"
printf 'Installed Iceberg runtime: %s\n' "$destination"
