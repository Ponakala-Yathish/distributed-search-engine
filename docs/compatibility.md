# Compatibility and Environment Audit

## Pinned Baseline

| Component | Required version | Evidence source |
|---|---|---|
| Ubuntu | 24.04 | Team environment |
| Java | OpenJDK 11 | Hadoop 3.3.6 and Spark 3.3.4 compatible baseline |
| Hadoop | 3.3.6 | Team environment |
| Spark / PySpark | 3.3.4 | Team environment |
| Scala | 2.12 | Spark 3.3.4 binary distribution |
| Apache Iceberg | 1.8.1 | Team environment and official Maven artifact |
| Iceberg Spark runtime | `iceberg-spark-runtime-3.3_2.12-1.8.1.jar` | Official Maven Central artifact |

Apache Iceberg 1.8.1 publishes a Spark 3.3 / Scala 2.12 runtime artifact. The runtime must match both the Spark minor line and Scala binary line; do not use the Spark 3.5 artifact with Spark 3.3.4.

## Python Requirement

Use Python 3.10 for VM1, VM2, and VM3. Ubuntu 24.04 can ship Python 3.12 as the system interpreter, but Spark 3.3.4 predates stable Python 3.12 support. A Python 3.10 virtual environment avoids the mismatch.

VM4 does not run Spark and can use Python 3.10, 3.11, or 3.12 with the pinned FastAPI and PyArrow dependencies.

## Iceberg Runtime Installation

On VM1, VM2, and VM3:

```bash
export SPARK_HOME=/opt/spark
bash scripts/install_iceberg.sh
```

The script downloads the official Maven artifact and verifies its SHA-512 checksum. It does not modify Spark or install an unrelated Iceberg version.

## Audit Procedure

Run on every VM:

```bash
git pull
cp config/.env.example config/.env
bash scripts/audit_environment.sh
```

Verify:

- Ubuntu 24.04 and OpenJDK 11 are active.
- `JAVA_HOME` points to OpenJDK 11.
- `HADOOP_HOME` points to Hadoop 3.3.6.
- `SPARK_HOME` points to Spark 3.3.4 built with Scala 2.12.
- PySpark is 3.3.4 in the active Python environment.
- The Iceberg 1.8.1 Spark 3.3 runtime jar exists.
- The VM has sufficient free disk and RAM.
- ZeroTier reports the expected managed address.

Do not reinstall or upgrade software solely because an audit item differs. First determine whether the installed version is compatible and working.

## Dependency Isolation

```bash
# VM1, VM2, VM3
bash scripts/install_cluster_dependencies.sh
source "$HOME/.venvs/dse-cluster/bin/activate"

# VM4
bash scripts/install_search_dependencies.sh
source "$HOME/.venvs/dse-search/bin/activate"
```

The cluster environment pins `cloudpickle==2.2.1` and `numpy==1.26.4` to avoid newer serialization and binary-compatibility changes with Spark 3.3.4.
