# Benchmarking

Benchmarks report measured values only. This repository contains no fabricated speedup or latency result.

## Search Latency

After deploying an index:

```bash
python -m benchmarks.run \
  --index data/serving/current \
  --queries "april,august,history,science" \
  --iterations 100 \
  --page-size 10 \
  --output reports/search-benchmark.json
```

The suite reports mean, P50, P95, P99 latency, throughput, and compares posting-list retrieval with naive document scanning over the same index and queries.

## Larger Optional Corpus

The official corpus remains the evaluation dataset. For a scale experiment only:

```bash
python -m benchmarks.generate_corpus --documents 10000 --output data/benchmarks/corpus.jsonl
```

Run the Phase 0 pipeline against that file using `--source` and a separate HDFS path so official data is not overwritten.

## Spark Stage Timing

The Spark UI and history server provide per-stage and per-task duration. Capture:

- Ingestion duration and documents per second.
- Index construction duration.
- PageRank duration and completed iterations.
- Export duration and bytes written.
- Peak executor memory and shuffle size.

The indexing and export CLIs print job summaries, but complete timing should be collected from the Spark UI during the actual run.

## Relevance Evaluation

The manually judged seed set is `benchmarks/judged_queries.json`. Each entry documents a query, relevant official document IDs, and the judgment rationale.

Create a ranked-results mapping:

```json
{
  "april": ["1", "2", "3"]
}
```

Then evaluate:

```bash
python -m benchmarks.evaluate \
  --judgments benchmarks/judged_queries.json \
  --ranked reports/ranked-results.json \
  --k 10
```

The evaluator reports Precision@K and NDCG@K. Expand the judged set only with genuinely reviewed relevance labels.

## Distributed Comparison

For the required single-machine versus distributed comparison:

1. Run Spark with `local[*]` on one worker VM and record stage duration.
2. Run the same job against the two-worker standalone cluster with identical input and configuration.
3. Change only the execution mode and record Spark application IDs.
4. Repeat at least three times and report the distribution, not only the best run.

Naive scanning and inverted retrieval are compared by `benchmarks/run.py`; the same corpus, queries, and index are used for both.
