# Viva Preparation

## Architecture

1. Why is VM1 a Spark client rather than a worker?
2. Why does VM4 not query Iceberg on every request?
3. How is a single source of truth maintained for the four addresses?
4. What are the boundaries between ingestion, indexing, export, and serving?
5. Why is the frontend decoupled from the FastAPI service?
6. What data crosses the ZeroTier network for a search request?

## Hadoop and HDFS

1. What are the NameNode and DataNode responsibilities?
2. How does HDFS achieve replication and recovery?
3. Why is replication factor 2 appropriate for VM2 and VM3?
4. What is block placement?
5. Why is `fs.defaultFS` shared by all clients?
6. How do you distinguish a NameNode failure from a DataNode failure?

## Spark

1. How are transformations distributed?
2. Why is `collect()` dangerous for the corpus?
3. What is a shuffle and where does it occur in this project?
4. How do executors receive tasks from the standalone master?
5. What happens when a worker dies?
6. Why is a `local[*]` test not equivalent to two-worker verification?
7. What are narrow and wide transformations in this pipeline?

## Iceberg

1. Why use Iceberg rather than plain Parquet for the mutable document table?
2. What is a snapshot?
3. How does MERGE preserve idempotency?
4. How can an earlier snapshot be inspected after a bad update?
5. Why is HadoopCatalog appropriate here?
6. What metadata does Iceberg store in HDFS?
7. Why are serving exports separate from the Iceberg tables?

## BM25

1. What problem does term-frequency saturation solve?
2. What does the `b` parameter control?
3. How is IDF calculated?
4. Why is the average document length required?
5. Why is posting-list lookup more efficient than scanning all documents?
6. What happens when a query term is absent?

## PageRank

1. What is the damping factor?
2. What is a dangling node?
3. How is dangling probability mass handled?
4. Why must invalid links be removed?
5. Why are at least ten iterations required?
6. How is the implementation distributed?
7. Why is PageRank normalized over the candidate set rather than the whole corpus?

## Hybrid Ranking

1. What is the exact official formula?
2. Why are maximum values computed before pagination?
3. How are zero denominators handled?
4. Why are both raw and normalized scores returned?
5. How can a user understand why a document ranked highly?

## Reliability

1. What makes Phase 0 repeatable?
2. How does a failed export preserve the old version?
3. What is the difference between a failed ingestion and a failed serving switch?
4. How is rollback implemented?
5. Why are exports immutable?
6. What evidence proves Spark fault tolerance?

## Data Engineering

1. How are malformed and missing-field records handled?
2. How is the highest version selected?
3. How are links to nonexistent documents removed?
4. Why are rejections persisted?
5. How would the schema change if the official input added explicit versions?
6. Why is the Phase 1 DELETE operation represented separately?

## Design Trade-offs

1. Why not use Elasticsearch, Redis, or Kafka?
2. What is the cost of rebuilding the full index for every update?
3. How would the system scale beyond 1,000 documents?
4. What would change for a corpus too large for VM4 memory?
5. Why is a full local index acceptable for this assignment but not necessarily at web scale?
6. How would you add incremental posting-list updates without rebuilding the index?

## Demonstration Talking Points

- Show `config/cluster.yaml` as the only address source.
- Show the Phase 0 document count before and after a repeated ingestion.
- Show Iceberg snapshots and a MERGE.
- Show the Spark UI with executors on both workers.
- Show `/version` before and after the Phase 1 switch.
- Demonstrate a deliberately failed export while `index-v0` remains active.
- Present measured benchmark output without claiming unmeasured speedups.
