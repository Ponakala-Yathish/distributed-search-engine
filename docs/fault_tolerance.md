# Fault Tolerance

Failure experiments are destructive and must never run in routine setup. Run them only during a scheduled demo, after confirming backups and with the team's approval.

## Spark Task Retry

Submit an index job while inspecting the Spark event log or UI. A transient worker failure should cause lost tasks to be retried on another registered worker.

Evidence to capture:

- Spark application ID.
- Failed task and executor ID.
- Retry count and final successful executor.
- Job duration before and after failure.

## Worker Failure

On VM2 or VM3, during a long-running Spark job:

```bash
kill "$(pgrep -f 'org.apache.spark.deploy.worker.Worker' | head -n 1)"
```

Immediately inspect the Spark master UI and job progress. The master should mark the worker dead and the driver should retry affected tasks on the remaining worker.

Restart the worker:

```bash
"$SPARK_HOME/sbin/start-worker.sh"
```

Measure elapsed time from worker death to job completion.

## HDFS DataNode Failure

During a replicated write:

```bash
hdfs --daemon stop datanode
```

Run destructive fault injection only in an isolated evaluation environment with no production traffic.

Verify that HDFS retains the required number of replicas and reconstructs blocks after restart:

```bash
hdfs dfsadmin -report
hdfs fsck / -files -blocks -locations
hdfs --daemon start datanode
```

Use the locally installed command consistently: `hdfs --daemon start datanode`.

## Failed Export

The export script writes to a unique HDFS staging directory and publishes only after validation. To simulate a failure safely, use a deliberately incomplete copied fixture or interrupt an export before publication. Do not damage a published version.

Expected evidence: `index-v0` remains valid and `current` remains unchanged.

## Failed Phase 1

Temporarily provide an invalid Phase 1 file or stop the Spark master while no production traffic is running. The ingestion job must fail visibly rather than publish a partial export. After recovery, repeat Phase 1 and verify that the prior index was served during the failure.

## HDFS Replication Check

```bash
hdfs dfs -setrep 2 /serving/index-v0
hdfs fsck /serving/index-v0 -files -blocks -locations
```

Every sufficiently replicated block should have two DataNode locations.

## Recovery Metrics to Record

| Experiment | Start time | Detection time | Recovery time | Data loss |
|---|---:|---:|---:|---:|
| Worker failure | | | | |
| DataNode failure | | | | |
| Failed export | | | | |
| Failed Phase 1 | | | | |

Do not claim a recovery time that was not measured.
