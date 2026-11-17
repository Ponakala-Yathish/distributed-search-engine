# Setup Guide

## 1. Clone and Configure

On all four VMs:

```bash
git clone <repository-url> distributed-search-engine
cd distributed-search-engine
cp config/.env.example config/.env
chmod +x scripts/*.sh
```

Do not commit `config/.env`. The committed `config/cluster.yaml` already contains the four ZeroTier addresses.

Prerequisites on every VM are OpenJDK 11, Hadoop 3.3.6, Spark 3.3.4 with Scala 2.12, and Python 3.10 on VM1–VM3. Install Hadoop and Spark under a prefix owned by the service account, or grant that account write access to `/opt/hadoop` and `/opt/spark` before running the setup scripts.

## 2. VM1: Ingestion Client

Install only the client and Python dependencies:

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export SPARK_HOME=/opt/spark
export PATH="$HADOOP_HOME/bin:$SPARK_HOME/bin:$PATH"
bash scripts/install_cluster_dependencies.sh
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/install_iceberg.sh
bash scripts/setup_hdfs.sh
bash scripts/setup_spark.sh
```

Ensure `spark-submit` is available but do not start a Spark master or worker. `setup_hdfs.sh` configures VM1 as an HDFS client without formatting the NameNode or starting daemons. `setup_spark.sh` binds the Spark client to the Python 3.10 cluster environment without starting a daemon.

## 3. VM2: HDFS NameNode and Worker

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export SPARK_HOME=/opt/spark
export PATH="$HADOOP_HOME/bin:$SPARK_HOME/bin:$PATH"
bash scripts/install_cluster_dependencies.sh
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/install_iceberg.sh
bash scripts/setup_hdfs.sh --format
bash scripts/setup_spark.sh
```

`--format` is destructive and must be used only for a new cluster. Never format an existing NameNode during the evaluation.

## 4. VM3: HDFS DataNode and Spark Master

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export SPARK_HOME=/opt/spark
export PATH="$HADOOP_HOME/bin:$SPARK_HOME/bin:$PATH"
bash scripts/install_cluster_dependencies.sh
source "$HOME/.venvs/dse-cluster/bin/activate"
bash scripts/install_iceberg.sh
bash scripts/setup_hdfs.sh
bash scripts/setup_spark.sh
```

VM3 must not format the NameNode.

## 5. VM4: Search and Frontend

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/opt/hadoop
export PATH="$HADOOP_HOME/bin:$PATH"
bash scripts/install_search_dependencies.sh
source "$HOME/.venvs/dse-search/bin/activate"
bash scripts/setup_hdfs.sh
```

Build the frontend:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run typecheck
npm run build
cd ..
```

Set `NEXT_PUBLIC_API_BASE_URL=http://<VM4 ZeroTier IP>:8000` in `frontend/.env.local` when accessing the frontend from another machine. Do not place the IP in frontend source. If `SEARCH_API_TOKEN` is configured in the FastAPI service, set the same value in `frontend/.env.local` so server-side requests can authenticate.

## 6. Start the Cluster

On VM2:

```bash
bash scripts/start_cluster.sh
```

On VM3:

```bash
bash scripts/start_cluster.sh
```

Then on any client VM:

```bash
bash scripts/check_connectivity.sh
```

Expected checks:

- Both DataNodes are live.
- HDFS has two live DataNodes and replication factor 2.
- Spark master lists two workers.
- VM1 and VM4 run no cluster daemons.

## 7. Install the Dataset

On VM1, create the ignored data directory and copy the official files:

```bash
mkdir -p data/datasets
cp /path/to/pages.jsonl data/datasets/pages.jsonl
cp /path/to/changes.jsonl data/datasets/changes.jsonl
```

The currently published official Drive uses `changes.json`. The phase script accepts both names.

## 8. Configure Python on Spark Nodes

Spark workers execute Python tasks. Ensure the worker environment uses the same cluster virtual environment and can import project packages. The setup scripts set Spark hosts and memory; environment activation for the worker service must point to the cluster virtual environment.

After all four VMs are configured, use `docs/verification_checklist.md` before running Phase 0.
