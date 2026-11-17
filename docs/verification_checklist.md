# Verification Checklist

Record the command output for every item. Do not mark an item verified from expectation alone.

## VM1: Ingestion

- [ ] `bash scripts/audit_environment.sh` shows Ubuntu 24.04, OpenJDK 11, Spark 3.3.4, PySpark 3.3.4, and Iceberg 1.8.1.
- [ ] `spark-submit --version` succeeds.
- [ ] No NameNode, DataNode, Spark master, or Spark worker process is running.
- [ ] All three other VM addresses respond to ping.
- [ ] `hdfs dfs -ls hdfs://<storage-host>:8020/` succeeds.
- [ ] The Spark master UI lists two workers.
- [ ] `pages.jsonl` and `changes.jsonl` or `changes.json` exist under `data/datasets/`.

## VM2: Storage

- [ ] Audit shows Hadoop 3.3.6, Spark 3.3.4, OpenJDK 11, and Iceberg 1.8.1.
- [ ] NameNode process is running.
- [ ] DataNode process is running.
- [ ] Spark worker process is running.
- [ ] `hdfs dfsadmin -report` shows two live DataNodes and configured replication factor 2.
- [ ] `hdfs dfs -ls /` succeeds from VM1.
- [ ] The Iceberg warehouse directory is writable by the Hadoop service account.

## VM3: Compute

- [ ] Audit shows Hadoop 3.3.6, Spark 3.3.4, OpenJDK 11, and Iceberg 1.8.1.
- [ ] Spark master process is running.
- [ ] Spark worker process is running.
- [ ] HDFS DataNode process is running.
- [ ] Spark master UI lists VM2 and VM3 workers.
- [ ] The Spark UI shows executors on both workers during an index job.

## VM4: Search

- [ ] Audit shows the search Python environment and all required packages.
- [ ] No Spark, NameNode, or DataNode process is running.
- [ ] `data/serving/index-v0` exists after Phase 0 deployment.
- [ ] `data/serving/current` is a relative symlink to `index-v0`.
- [ ] `curl http://localhost:8000/health` returns `status=ok`.
- [ ] `/version` reports the active index.
- [ ] `/stats` reports document, term, and posting counts.
- [ ] `/search?q=april` returns the April document.
- [ ] `/documents/1` returns the document content.
- [ ] The frontend loads from `http://<VM4 ZeroTier IP>:3000` and displays the index version.

## Phase 0 and Phase 1

- [ ] Phase 0 summary records malformed records without aborting the job.
- [ ] Duplicate document IDs resolve to the highest version.
- [ ] Phase 0 export validates before publication.
- [ ] Repeating Phase 0 does not change the logical document count.
- [ ] Phase 1 applies 50 UPSERT and 50 DELETE operations from the official change file.
- [ ] Links to deleted documents are removed.
- [ ] `index-v1` validates and is published.
- [ ] Failed Phase 1 export leaves `current` on `index-v0`.
- [ ] `index-v0` remains available for rollback.

## Verification Levels

Use these labels in the team report:

- **Implemented:** source exists and has been reviewed.
- **Unit-tested:** automated local test passed.
- **Integration-tested:** local Spark/filesystem or API integration test passed.
- **Cluster-verified:** command was executed on the actual four-VM cluster and output was retained.

Only label a requirement **cluster-verified** after the relevant checklist items are completed.
