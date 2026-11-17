# Troubleshooting

## Configuration Invalid

```bash
bash scripts/validate_config.sh
```

Common causes:

- The four required node IDs or roles are missing.
- Two nodes use the same IP.
- An environment override contains an invalid address.
- HDFS replication was changed from 2.
- PageRank iterations are below 10.

## ZeroTier Ping Fails

```bash
zerotier-cli info
zerotier-cli listnetworks
ip -4 addr
```

Verify that every VM joined the same ZeroTier network and that the managed address matches `config/cluster.yaml`. A physical or public address is not a substitute for the managed address.

## HDFS Reports Only One DataNode

Run `hdfs dfsadmin -report` from VM1. Then inspect VM2 and VM3:

```bash
hdfs --daemon start datanode
```

Confirm `HADOOP_HOME/etc/hadoop/workers` contains both configured addresses and that both services use the same `fs.defaultFS`.

## Spark Master Has No Workers

Inspect `$SPARK_HOME/logs` on both workers. Verify:

- `spark.master` is the configured `spark://...:7077` URL.
- `SPARK_WORKER_HOST` is that VM's ZeroTier address.
- TCP 7077 is reachable.
- Worker and master use compatible Java versions.

## Spark Cannot Import Project Modules

The driver and Python workers need the repository on `PYTHONPATH`. Activate the cluster virtual environment before `spark-submit` and ensure worker services use the same environment.

## Iceberg ClassNotFoundException

The runtime jar must match Spark 3.3 and Scala 2.12:

```bash
bash scripts/install_iceberg.sh
```

Verify that `spark-submit` and the workers receive `$SPARK_HOME/jars/iceberg-spark-runtime-3.3_2.12-1.8.1.jar`.

## MERGE Fails on Spark 3.3.4

Check that Iceberg extensions are enabled and the catalog warehouse is configured. Run the ingestion CLI directly to retain the complete stack trace:

```bash
python -m ingestion.pipeline --phase 0 --source data/datasets/pages.jsonl
```

## Export Validation Fails

Do not publish the export. Inspect:

- `metadata.json` keys and file mapping.
- Parquet schema and nonempty file count.
- `document_count` versus `documents.parquet`.
- One PageRank row for every document.
- The `pagerank` column name.

## VM4 Cannot Load the Export

```bash
python -m search_service.main --validate --serving-root data/serving
```

The service does not query HDFS for each request. A load failure means the local export is missing, incomplete, or inconsistent.

## Search Returns No Results

Confirm query tokenization matches the indexed tokenization. Check `/stats` for a nonzero term count. Query only indexed terms and verify the corresponding posting map contains the expected document IDs.

## Port Already in Use

```bash
ss -ltnp | grep ':8000'
```

Stop the old service or change the configured port. During evaluation, keep the documented port 8000.

## Python 3.12 on Spark Nodes

Spark 3.3.4 should run with Python 3.10. Create the cluster virtual environment with Python 3.10 and configure the Spark workers to use it. VM4 can remain on a newer Python version because it does not run Spark.
