# Deployment Guide

## Phase 0

### 1. Ingest on VM1

```bash
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/run_phase0.sh
```

Expected result: a JSON summary with total, valid, invalid, duplicate, accepted, and rejected counts. The official corpus currently contains malformed and duplicate records, so invalid and duplicate counts are expected to be nonzero.

### 2. Build and Export on VM3

```bash
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/export_index.sh --phase 0
```

Expected result: `hdfs://<storage-host>:8020/serving/index-v0` is published. The export is immutable; rerunning with the same version fails instead of overwriting a working index.

### 3. Deploy on VM4

```bash
source "$HOME/.venvs/dse-search/bin/activate"
bash scripts/deploy_search.sh --version 0
sudo bash scripts/install_search_service.sh
sudo bash scripts/install_frontend_service.sh
```

Expected result: `data/serving/index-v0` exists, `data/serving/current` points to it, and `dse-search.service` is active.

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/version
curl "http://localhost:8000/search?q=april"
```

## Phase 1

### 1. Ingest changes on VM1

```bash
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/run_phase1.sh
```

Expected result: UPSERT records update matching documents and DELETE records remove their documents. The Phase 0 version remains serving during this command.

### 2. Export on VM3

```bash
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/export_index.sh --phase 1
```

Expected result: `index-v1` is published without changing `index-v0`.

### 3. Deploy on VM4

```bash
source "$HOME/.venvs/dse-search/bin/activate"
bash scripts/deploy_search.sh --version 1
sudo systemctl restart dse-search.service
```

Expected result: `data/serving/current` points to `index-v1`. If download or validation fails, the script exits and the previous symlink remains unchanged.

## Idempotency Check

Run Phase 0 a second time and compare logical contents:

```bash
eval "$(python -m config.settings --export-shell)"
hdfs dfs -ls "$DSE_HDFS_NAMENODE/serving"
```

More directly, query the Iceberg table before and after the repeated ingestion:

```bash
spark-sql --master "$DSE_SPARK_MASTER" --jars "$SPARK_HOME/jars/iceberg-spark-runtime-3.3_2.12-1.8.1.jar" \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.dse=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.dse.type=hadoop \
  --conf spark.sql.catalog.dse.warehouse="$DSE_ICEBERG_WAREHOUSE" \
  -e "SELECT count(*) FROM dse.documents"
```

The document count and logical row contents must not change. Audit tables can gain a new run record and can record newly observed rejections; that does not change the logical document table.

## Rollback

Use the version manager from Python:

```bash
python3 - <<'PY'
from search_service.version_manager import VersionManager
manager = VersionManager("data/serving")
manager.rollback()
print(manager.active.version)
PY
sudo systemctl restart dse-search.service
```

The old export remains available because exports are immutable.
